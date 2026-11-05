"""Kalshi public market-data client and pull jobs.

Kalshi splits data at a cutoff (`/historical/cutoff`): markets that settled before it, and their
candles, are served only by `/historical/*`. Newer ones are on the live endpoints, which also
offer a 100-ticker batch candle call. The client picks the tier per market.

Unauthenticated reads are capped at about 5 req/s. If `KALSHI_API_KEY_ID` and
`KALSHI_PRIVATE_KEY_PATH` are set, requests are signed (RSA-PSS), which raises the cap to the
account tier (Basic: about 20 req/s).
"""

from __future__ import annotations

import base64
import json
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import pandas as pd
from tqdm import tqdm

from pinpricer.config import RAW_DIR, load_config, study_window
from pinpricer.data import store
from pinpricer.data.http import HttpClient

UNAUTH_RPS = 4.5
MAX_BATCH_TICKERS = 100
MAX_BATCH_CANDLES = 9_000  # the API caps a batch response at 10k candles


# ---------------------------------------------------------------- client


class KalshiClient:
    def __init__(self, base_url: str, rate: float | None = None):
        self._signer = _load_signer()
        rate = rate if rate is not None else (18.0 if self._signer else UNAUTH_RPS)
        if not self._signer:
            rate = min(rate, UNAUTH_RPS)
        self.http = HttpClient(base_url, rate=rate)
        self._prefix = urlparse(base_url).path.rstrip("/")
        self._cutoff: pd.Timestamp | None = None

    def get(self, path: str, params: dict | None = None, **kw) -> dict | None:
        headers = self._signer(self._prefix + path) if self._signer else None
        return self.http.get_json(path, params, headers=headers, **kw)

    @property
    def cutoff(self) -> pd.Timestamp:
        """Markets settled before this are only on /historical/*."""
        if self._cutoff is None:
            self._cutoff = pd.Timestamp(self.get("/historical/cutoff")["market_settled_ts"])
        return self._cutoff

    def markets_page(self, series: str, historical: bool, cursor: str | None,
                     min_close: pd.Timestamp | None = None, max_close: pd.Timestamp | None = None) -> dict:
        """One page (≤1000) of a series' markets. The historical tier pages newest-first."""
        params = {"series_ticker": series, "limit": 1000}
        if not historical:
            params |= {"min_close_ts": int(min_close.timestamp()), "max_close_ts": int(max_close.timestamp())}
        if cursor:
            params["cursor"] = cursor
        return self.get("/historical/markets" if historical else "/markets", params)

    def candles_historical(self, ticker: str, start: int, end: int, minutes: int = 1) -> list[dict]:
        d = self.get(f"/historical/markets/{ticker}/candlesticks",
                     {"start_ts": start, "end_ts": end, "period_interval": minutes}, allow_404=True)
        return (d or {}).get("candlesticks") or []

    def trades_page(self, ticker: str, historical: bool, cursor: str | None) -> dict:
        params = {"ticker": ticker, "limit": 1000} | ({"cursor": cursor} if cursor else {})
        return self.get("/historical/trades" if historical else "/markets/trades", params)

    def candles_batch(self, tickers: list[str], start: int, end: int, minutes: int = 1) -> dict[str, list[dict]]:
        d = self.get("/markets/candlesticks", {"market_tickers": ",".join(tickers), "start_ts": start,
                                               "end_ts": end, "period_interval": minutes})
        return {m["market_ticker"]: m.get("candlesticks") or [] for m in d.get("markets", [])}


def _load_signer():
    key_id = os.environ.get("KALSHI_API_KEY_ID")
    key_path = os.environ.get("KALSHI_PRIVATE_KEY_PATH")
    if not (key_id and key_path):
        return None
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    with open(os.path.expanduser(key_path), "rb") as f:
        key = serialization.load_pem_private_key(f.read(), password=None)

    def sign(path: str) -> dict:
        ts = str(int(time.time() * 1000))
        sig = key.sign((ts + "GET" + path).encode(),
                       padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
                       hashes.SHA256())
        return {"KALSHI-ACCESS-KEY": key_id, "KALSHI-ACCESS-TIMESTAMP": ts,
                "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode()}

    return sign


# ---------------------------------------------------------------- parsing


def _f(x) -> float:
    """Kalshi sends numbers as strings, sometimes with thousands separators ("79,604.96")."""
    if x is None or x == "":
        return math.nan
    return float(x.replace(",", "")) if isinstance(x, str) else float(x)


def cadence(hours_open: pd.Series) -> pd.Series:
    """Classify contracts by how long they trade: 15-min, hourly, daily, or longer."""
    bins = [0, 0.3, 1.1, 36, float("inf")]
    return pd.cut(hours_open, bins, labels=["fifteen_min", "hourly", "daily", "weekly_plus"]).astype(str)


def parse_market(m: dict) -> dict:
    return {
        "ticker": m["ticker"],
        "event_ticker": m["event_ticker"],
        "open_time": pd.Timestamp(m["open_time"]),
        "close_time": pd.Timestamp(m["close_time"]),
        "strike_type": m.get("strike_type"),
        "floor_strike": _f(m.get("floor_strike")),
        "cap_strike": _f(m.get("cap_strike")),
        "expiration_value": _f(m.get("expiration_value")),
        "result": m.get("result"),
        "volume": _f(m.get("volume_fp")),
        "open_interest": _f(m.get("open_interest_fp")),
        "price_level_structure": m.get("price_level_structure"),
        "status": m.get("status"),
    }


def parse_candles(ticker: str, candles: list[dict]) -> list[dict]:
    """One row per minute: end-of-minute YES bid/ask, last-trade stats, volume, open interest."""
    rows = []
    for c in candles:
        bid, ask, px = c.get("yes_bid") or {}, c.get("yes_ask") or {}, c.get("price") or {}
        rows.append({
            "ticker": ticker,
            "ts": pd.Timestamp(c["end_period_ts"], unit="s", tz="UTC"),
            "yes_bid": _f(bid.get("close")),
            "yes_ask": _f(ask.get("close")),
            "yes_bid_low": _f(bid.get("low")),
            "yes_ask_high": _f(ask.get("high")),
            "last_price": _f(px.get("close")),
            "vwap": _f(px.get("mean")),
            "volume": _f(c.get("volume")),
            "open_interest": _f(c.get("open_interest")),
        })
    return rows


# ---------------------------------------------------------------- strike selection


def reference_prices(markets: pd.DataFrame) -> pd.Series:
    """Hourly BRTI 60s-average settlements (one per event close), indexed by close time."""
    ref = markets.dropna(subset=["expiration_value"]).groupby("close_time")["expiration_value"].first()
    return ref.sort_index()


def select_strikes(markets: pd.DataFrame, refs: pd.Series, band_pct: float, max_band_pct: float = 6.0) -> pd.DataFrame:
    """Keep ladder strikes within ±band of the last settlement known when each event opened.

    The band widens with sqrt(hours open), so a 24h daily event keeps about ±5x the hourly band
    (capped). Strikes are chosen from information available at the open, so the selection is
    not conditioned on the outcome.
    """
    if markets.empty:
        return markets
    m = markets.copy()
    opens = m["open_time"].dt.tz_convert(None).to_numpy().astype("datetime64[ns]")
    ref_idx = refs.index.tz_convert(None).to_numpy().astype("datetime64[ns]")
    pos = ref_idx.searchsorted(opens, side="right") - 1
    m["ref_price"] = [refs.iloc[p] if p >= 0 else math.nan for p in pos]
    hours = (m["close_time"] - m["open_time"]).dt.total_seconds() / 3600
    band = (band_pct * hours.clip(lower=1) ** 0.5).clip(upper=max_band_pct) / 100
    keep = (m["floor_strike"] - m["ref_price"]).abs() <= band * m["ref_price"]
    return m[keep & m["ref_price"].notna()]


# ---------------------------------------------------------------- pull jobs


def _series_dir(series: str):
    return RAW_DIR / "kalshi" / series


def page_markets(client: KalshiClient, series: str, historical: bool) -> None:
    """Page a series' markets into raw page files, checkpointing the cursor so a rerun resumes.

    The historical tier returns newest first, so paging stops once a page reaches past the study
    start. The live tier is filtered server-side by close time.
    """
    start, end = study_window()
    tier = "hist" if historical else "live"
    out = _series_dir(series) / "pages" / tier
    ckpt = out / "_checkpoint.json"
    state = json.loads(ckpt.read_text()) if ckpt.exists() else {"cursor": None, "page": 0, "done": False}
    bar = tqdm(desc=f"{series} markets ({tier})", unit="page", initial=state["page"])
    while not state["done"]:
        d = client.markets_page(series, historical, state["cursor"], min_close=client.cutoff, max_close=end)
        rows = [parse_market(m) for m in d.get("markets") or []]
        if rows:
            store.write_part(pd.DataFrame(rows), out, f"page-{state['page']:05d}")
        state["cursor"] = d.get("cursor") or None
        state["page"] += 1
        oldest = min((r["close_time"] for r in rows), default=None)
        state["done"] = not state["cursor"] or (historical and oldest is not None and oldest < start)
        out.mkdir(parents=True, exist_ok=True)
        ckpt.write_text(json.dumps(state))
        bar.update(1)
        bar.set_postfix_str(f"oldest close {oldest:%Y-%m-%d}" if oldest is not None else "")
    bar.close()


def build_markets(series: str, cadences: list[str]) -> pd.DataFrame:
    """Merge page files into one deduplicated, window-filtered markets table with a cadence label."""
    start, end = study_window()
    sdir = _series_dir(series)
    df = pd.concat([store.read_parts(sdir / "pages" / t) for t in ("hist", "live")], ignore_index=True)
    df = df.drop_duplicates("ticker", keep="last")
    df = df[(df["close_time"] >= start) & (df["close_time"] < end)].copy()
    # Classify by event, not by strike: Kalshi adds strikes to an event intraday, so the 5 PM ET
    # daily event mixes day-old strikes with ones listed an hour before close.
    event_open = df.groupby("event_ticker")["open_time"].transform("min")
    df["cadence"] = cadence((df["close_time"] - event_open).dt.total_seconds() / 3600)
    df = df[df["cadence"].isin(cadences)].sort_values(["close_time", "floor_strike"]).reset_index(drop=True)
    store.write_part(df, sdir, "markets")
    return df


def pull_candles(client: KalshiClient, series: str, markets: pd.DataFrame, minutes: int, workers: int) -> None:
    out = _series_dir(series) / "candles"
    markets = markets.assign(day=markets["close_time"].dt.strftime("%Y-%m-%d"))
    todo = [(d, g) for d, g in markets.groupby("day") if not store.is_done(out, d)]
    hist_n = sum(int((g["close_time"] < client.cutoff).sum()) for _, g in todo)
    eta_h = hist_n / client.http.limiter.rate / 3600
    print(f"{series}: {sum(len(g) for _, g in todo):,} markets over {len(todo)} days to pull "
          f"({hist_n:,} one-call historical, ≈{eta_h:.1f} h at {client.http.limiter.rate:g} req/s)")

    def hist_one(row) -> list[dict]:
        start, end = int(row.open_time.timestamp()), int(row.close_time.timestamp())
        return parse_candles(row.ticker, client.candles_historical(row.ticker, start, end, minutes))

    def live_batch(rows: list) -> list[dict]:
        start = int(min(r.open_time for r in rows).timestamp())
        end = int(max(r.close_time for r in rows).timestamp())
        got = client.candles_batch([r.ticker for r in rows], start, end, minutes)
        return [c for t, cs in got.items() for c in parse_candles(t, cs)]

    with ThreadPoolExecutor(workers) as ex:
        # Newest days first, so a partial pull already covers the most recent, most liquid period.
        for day, g in tqdm(todo[::-1], desc=f"{series} candles", unit="day"):
            hist = g[g["close_time"] < client.cutoff]
            live = g[g["close_time"] >= client.cutoff]
            jobs = [ex.submit(hist_one, r) for r in hist.itertuples()]
            for _, eg in live.groupby("event_ticker"):
                rows = list(eg.itertuples())
                n_min = max(1, int((eg["close_time"].max() - eg["open_time"].min()).total_seconds() // 60 / minutes))
                step = max(1, min(MAX_BATCH_TICKERS, MAX_BATCH_CANDLES // n_min))
                jobs += [ex.submit(live_batch, rows[i:i + step]) for i in range(0, len(rows), step)]
            out_rows = [r for j in jobs for r in j.result()]
            if out_rows:
                store.write_part(pd.DataFrame(out_rows), out, day)


def parse_trades(trades: list[dict]) -> pd.DataFrame:
    """One row per fill. `taker_side` is the outcome the taker bought; the maker holds the other side."""
    df = pd.DataFrame([{"ticker": x["ticker"], "ts": x["created_time"], "yes_price": _f(x["yes_price_dollars"]),
                        "count": _f(x["count_fp"]), "taker_side": x["taker_side"]} for x in trades])
    if not df.empty:
        df["ts"] = pd.to_datetime(df["ts"], utc=True, format="ISO8601")
    return df


def trade_sample(markets: pd.DataFrame, cadence_: str, n_events: int, band_pct: float, seed: int,
                 start: pd.Timestamp) -> pd.DataFrame:
    """Random events of one cadence closing after `start`, with ladder strikes chosen at the open.

    Strikes are kept within ±band_pct·sqrt(hours open) of the last settlement known when the event
    opened (`select_strikes`), so the sample never depends on where BTC finished. Every 15-minute
    window has a single contract, which is always kept.
    """
    m = markets[(markets["cadence"] == cadence_) & (markets["close_time"] >= start)].dropna(subset=["floor_strike"])
    events = m["event_ticker"].drop_duplicates().sample(n=min(n_events, m["event_ticker"].nunique()),
                                                         random_state=seed)
    m = m[m["event_ticker"].isin(events)]
    if cadence_ == "fifteen_min":
        return m
    return select_strikes(m, reference_prices(markets), band_pct)


def sample_for_study(series: str) -> pd.DataFrame:
    """The configured fill sample for one series (the markets whose trades the markout study uses)."""
    cfg = load_config()["kalshi"]
    tcfg = cfg["trades_sample"]
    markets = pd.read_parquet(_series_dir(series) / "markets.parquet")
    start = pd.Timestamp(tcfg["start"], tz="UTC")
    return pd.concat([trade_sample(markets, c, n, tcfg["strike_band_pct"], tcfg["seed"], start)
                      for c, n in tcfg["events"].items() if c in cfg["series"][series]["cadences"]])


def pull_trades(client: KalshiClient, series: str, sample: pd.DataFrame, workers: int) -> None:
    out = _series_dir(series) / "trades"

    def one(row) -> None:
        if store.is_done(out, row.ticker):
            return
        rows, cursor, hist = [], None, row.close_time < client.cutoff
        while True:
            d = client.trades_page(row.ticker, hist, cursor)
            rows += d.get("trades", [])
            cursor = d.get("cursor")
            if not cursor or not d.get("trades"):
                break
        store.write_part(parse_trades(rows) if rows else pd.DataFrame(columns=["ticker"]), out, row.ticker)

    with ThreadPoolExecutor(workers) as ex:
        list(tqdm(ex.map(one, sample.itertuples()), total=len(sample), desc=f"{series} trades", unit="mkt"))


def run_trades(series_names: list[str] | None = None) -> None:
    cfg = load_config()["kalshi"]
    client = KalshiClient(cfg["base_url"], rate=cfg.get("requests_per_second"))
    for series in series_names or list(cfg["series"]):
        sample = sample_for_study(series)
        print(f"{series}: {len(sample):,} markets in the trade sample")
        pull_trades(client, series, sample, cfg["workers"])


def run(series_names: list[str] | None = None, *, stages=("markets", "candles")) -> None:
    cfg = load_config()["kalshi"]
    client = KalshiClient(cfg["base_url"], rate=cfg.get("requests_per_second"))
    mode = "signed" if client._signer else "unauthenticated"
    print(f"Kalshi: {mode}, {client.http.limiter.rate:g} req/s, historical cutoff {client.cutoff}")
    for series in series_names or list(cfg["series"]):
        scfg = cfg["series"][series]
        if "markets" in stages:
            page_markets(client, series, historical=True)
            page_markets(client, series, historical=False)
            markets = build_markets(series, scfg["cadences"])
            print(f"{series}: {len(markets):,} markets, {markets['event_ticker'].nunique():,} events, "
                  f"{markets['close_time'].min()} → {markets['close_time'].max()}")
        if "candles" in stages:
            markets = pd.read_parquet(_series_dir(series) / "markets.parquet")
            if "strike_band_pct" in scfg:
                markets = select_strikes(markets, reference_prices(markets), scfg["strike_band_pct"])
            pull_candles(client, series, markets, scfg["candle_minutes"], cfg["workers"])
