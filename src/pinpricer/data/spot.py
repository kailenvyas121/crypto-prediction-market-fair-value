"""Spot and perp price history: Coinbase and Bitstamp 1m candles (USD, BRTI constituents) and
Binance bulk files from data.binance.vision (USDT spot and perp klines, 1s spot klines, funding).

Binance.com's REST API returns HTTP 451 from US IPs. The data.binance.vision bulk files are not
geo-blocked, so we use them read-only.

All candle tables share the schema: ts (UTC bar open), open, high, low, close, volume, plus
Binance's extra flow columns where available.
"""

from __future__ import annotations

import io
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
from tqdm import tqdm

from pinpricer.config import RAW_DIR, load_config, study_window
from pinpricer.data import store
from pinpricer.data.http import HttpClient

OHLCV = ["ts", "open", "high", "low", "close", "volume"]
BINANCE_KLINE_COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
                      "quote_volume", "trades", "taker_buy_volume", "taker_buy_quote_volume", "ignore"]


# ---------------------------------------------------------------- Coinbase / Bitstamp


def coinbase_day(http: HttpClient, product: str, granularity: str, day: pd.Timestamp) -> pd.DataFrame:
    """One UTC day of 1m candles. The endpoint returns at most 350 bars per call."""
    url = f"https://api.coinbase.com/api/v3/brokerage/market/products/{product}/candles"
    frames, t, end = [], int(day.timestamp()), int((day + pd.Timedelta(days=1)).timestamp())
    while t < end:
        t2 = min(end, t + 300 * 60)
        d = http.get_json(url, {"start": t, "end": t2 - 60, "granularity": granularity, "limit": 350})
        if d.get("candles"):
            frames.append(pd.DataFrame(d["candles"]))
        t = t2
    if not frames:
        return pd.DataFrame(columns=OHLCV)
    df = pd.concat(frames).rename(columns={"start": "ts"})
    df["ts"] = pd.to_datetime(df["ts"].astype("int64"), unit="s", utc=True)
    df = df[OHLCV].astype({c: float for c in OHLCV[1:]})
    return df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)


def bitstamp_day(http: HttpClient, pair: str, step: int, day: pd.Timestamp) -> pd.DataFrame:
    url = f"https://www.bitstamp.net/api/v2/ohlc/{pair}/"
    frames, t, end = [], int(day.timestamp()), int((day + pd.Timedelta(days=1)).timestamp())
    # With both start and end set, Bitstamp returns the *last* `limit` bars, so keep windows ≤ limit.
    while t < end:
        t2 = min(end, t + 1000 * step)
        d = http.get_json(url, {"step": step, "limit": 1000, "start": t, "end": t2 - step})
        bars = d.get("data", {}).get("ohlc", [])
        if bars:
            frames.append(pd.DataFrame(bars))
        t = t2
    if not frames:
        return pd.DataFrame(columns=OHLCV)
    df = pd.concat(frames).rename(columns={"timestamp": "ts"})
    df["ts"] = pd.to_datetime(df["ts"].astype("int64"), unit="s", utc=True)
    df = df[OHLCV].astype({c: float for c in OHLCV[1:]})
    return df[df["ts"] < day + pd.Timedelta(days=1)].drop_duplicates("ts").sort_values("ts").reset_index(drop=True)


def _pull_daily(name: str, fetch, days: list[pd.Timestamp], workers: int = 4) -> None:
    out = RAW_DIR / "spot" / name
    todo = [d for d in days if not store.is_done(out, d.strftime("%Y-%m-%d"))]

    def job(day):
        store.write_part(fetch(day), out, day.strftime("%Y-%m-%d"))

    with ThreadPoolExecutor(workers) as ex:
        list(tqdm(ex.map(job, todo), total=len(todo), desc=name, unit="day"))


# ---------------------------------------------------------------- Binance bulk files


def parse_binance_klines(raw: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(raw)) as z, z.open(z.namelist()[0]) as f:
        df = pd.read_csv(f, header=None, names=BINANCE_KLINE_COLS)
    if not str(df.iloc[0, 0]).isdigit():  # futures files carry a header row
        df = df.iloc[1:]
    t = df["open_time"].astype("int64")
    # Spot files switched from millisecond to microsecond timestamps in 2025.
    unit = "us" if t.iloc[0] > 10**14 else "ms"
    out = pd.DataFrame({"ts": pd.to_datetime(t, unit=unit, utc=True)})
    for c in ["open", "high", "low", "close", "volume", "quote_volume", "taker_buy_volume"]:
        out[c] = df[c].astype(float).values
    out["trades"] = df["trades"].astype("int64").values
    return out


def parse_binance_funding(raw: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(raw)) as z, z.open(z.namelist()[0]) as f:
        df = pd.read_csv(f)
    return pd.DataFrame({
        "ts": pd.to_datetime(df["calc_time"].astype("int64"), unit="ms", utc=True),
        "funding_interval_hours": df["funding_interval_hours"].astype(int),
        "funding_rate": df["last_funding_rate"].astype(float),
    })


def _vision_url(base: str, market: str, freq: str, kind: str, symbol: str, interval: str | None, date: str) -> str:
    # e.g. {base}/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2026-01.zip
    root, sym = market.rsplit("/", 1)
    if interval:
        return f"{base}/{root}/{freq}/{kind}/{sym}/{interval}/{sym}-{interval}-{date}.zip"
    return f"{base}/{root}/{freq}/{kind}/{sym}/{sym}-{kind}-{date}.zip"


def pull_binance_monthly(http: HttpClient, base: str, market: str, kind: str, interval: str | None,
                         start: pd.Timestamp, end: pd.Timestamp, parser) -> None:
    """Whole months as monthly files; the trailing partial month from daily files."""
    name = f"{market.replace('/', '_')}_{interval or kind}"
    out = RAW_DIR / "binance" / name
    months = pd.period_range(start.tz_localize(None), (end - pd.Timedelta(seconds=1)).tz_localize(None), freq="M")
    last_full = (pd.Timestamp.now(tz="UTC").tz_localize(None).to_period("M") - 1)
    for m in tqdm(months, desc=name, unit="mo"):
        key = str(m)
        if store.is_done(out, key):
            continue
        if m <= last_full:
            raw = http.get_bytes(_vision_url(base, market, "monthly", kind, market.rsplit("/", 1)[1], interval, key), allow_404=True)
            frames = [parser(raw)] if raw else []
        else:  # current month: daily files up to `end`
            days = pd.date_range(m.start_time, min(m.end_time, end.tz_localize(None) - pd.Timedelta(days=1)), freq="D")
            frames = []
            for d in days:
                raw = http.get_bytes(_vision_url(base, market, "daily", kind, market.rsplit("/", 1)[1], interval, d.strftime("%Y-%m-%d")), allow_404=True)
                if raw:
                    frames.append(parser(raw))
        if frames:
            store.write_part(pd.concat(frames, ignore_index=True), out, key)


def pull_binance_1s(http: HttpClient, base: str, days: list[pd.Timestamp], workers: int = 4) -> None:
    out = RAW_DIR / "binance" / "spot_BTCUSDT_1s"
    todo = [d for d in days if not store.is_done(out, d.strftime("%Y-%m-%d"))]

    def job(day):
        key = day.strftime("%Y-%m-%d")
        raw = http.get_bytes(_vision_url(base, "spot/BTCUSDT", "daily", "klines", "BTCUSDT", "1s", key), allow_404=True)
        if raw:
            store.write_part(parse_binance_klines(raw), out, key)

    with ThreadPoolExecutor(workers) as ex:
        list(tqdm(ex.map(job, todo), total=len(todo), desc="spot_BTCUSDT_1s", unit="day"))


# ---------------------------------------------------------------- entry point


def run() -> None:
    cfg = load_config()["spot"]
    start, end = study_window(with_warmup=True)
    days = store.day_keys(start, end)

    cb = cfg["coinbase"]
    http_cb = HttpClient(rate=cb["requests_per_second"])
    _pull_daily(f"coinbase_{cb['product']}_1m", lambda d: coinbase_day(http_cb, cb["product"], cb["granularity"], d), days)

    bs = cfg["bitstamp"]
    http_bs = HttpClient(rate=bs["requests_per_second"])
    _pull_daily(f"bitstamp_{bs['pair']}_1m", lambda d: bitstamp_day(http_bs, bs["pair"], bs["step_seconds"], d), days, workers=2)

    bv = cfg["binance_vision"]
    http_bv = HttpClient(rate=10)
    for market in bv["klines_1m"]:
        pull_binance_monthly(http_bv, bv["base_url"], market, "klines", "1m", start, end, parse_binance_klines)
    pull_binance_monthly(http_bv, bv["base_url"], bv["funding"], "fundingRate", None, start, end, parse_binance_funding)
    pull_binance_1s(http_bv, bv["base_url"], days[-bv["klines_1s_days"]:])
