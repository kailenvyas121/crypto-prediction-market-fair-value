"""Offline tests for the data layer: parsing, strike selection, storage, rate limiting."""

import io
import math
import time
import zipfile

import pandas as pd
import pytest

from pinpricer.data import kalshi, spot, store
from pinpricer.data.http import RateLimiter

T = pd.Timestamp


# ---------------------------------------------------------------- kalshi parsing


def test_number_parsing_handles_strings_commas_and_blanks():
    assert kalshi._f("79,604.96") == pytest.approx(79604.96)
    assert kalshi._f("0.5900") == pytest.approx(0.59)
    assert kalshi._f(71799.99) == pytest.approx(71799.99)
    assert math.isnan(kalshi._f(None)) and math.isnan(kalshi._f(""))


def test_parse_candles_reads_end_of_minute_quotes():
    c = {"end_period_ts": 1784136660, "open_interest": "71159.54", "volume": "9844.44",
         "price": {"close": "0.5900", "mean": "0.5521"},
         "yes_bid": {"close": "0.5700", "low": "0.4900"}, "yes_ask": {"close": "0.5900", "high": "0.5900"}}
    (row,) = kalshi.parse_candles("KXBTCD-26JUL1514-T64999.99", [c])
    assert row["ts"] == T("2026-07-15 17:31", tz="UTC")
    assert (row["yes_bid"], row["yes_ask"]) == (pytest.approx(0.57), pytest.approx(0.59))
    assert row["volume"] == pytest.approx(9844.44)


def test_parse_candles_tolerates_missing_quotes():
    (row,) = kalshi.parse_candles("X", [{"end_period_ts": 0, "price": {"close": None}}])
    assert math.isnan(row["yes_bid"]) and math.isnan(row["last_price"])


@pytest.mark.parametrize("hours,label", [(0.25, "fifteen_min"), (1.0, "hourly"), (24, "daily"),
                                         (31, "daily"), (168, "weekly_plus")])
def test_cadence_from_trading_duration(hours, label):
    assert kalshi.cadence(pd.Series([hours])).iloc[0] == label


# ---------------------------------------------------------------- strike selection


def _ladder(open_t, close_t, strikes):
    return pd.DataFrame({"ticker": [f"K{k}" for k in strikes], "event_ticker": "E",
                         "open_time": T(open_t, tz="UTC"), "close_time": T(close_t, tz="UTC"),
                         "floor_strike": strikes})


def test_select_strikes_uses_settlement_known_at_open_not_outcome():
    refs = pd.Series([100_000.0, 200_000.0],
                     index=[T("2026-07-15 17:00", tz="UTC"), T("2026-07-15 18:00", tz="UTC")])
    m = _ladder("2026-07-15 17:00", "2026-07-15 18:00", [98_000.0, 99_000.0, 100_000.0, 101_400.0, 103_000.0])
    kept = kalshi.select_strikes(m, refs, band_pct=1.5)
    # Reference is the 17:00 settle (100k); the 18:00 value (this event's own outcome) is never used.
    assert kept["ref_price"].unique().tolist() == [100_000.0]
    assert kept["floor_strike"].tolist() == [99_000.0, 100_000.0, 101_400.0]


def test_select_strikes_band_widens_with_sqrt_time_and_caps():
    refs = pd.Series([100_000.0], index=[T("2026-07-14 21:00", tz="UTC")])
    m = _ladder("2026-07-14 21:00", "2026-07-15 21:00", [93_000.0, 95_000.0, 107_000.0])  # 24h event
    kept = kalshi.select_strikes(m, refs, band_pct=1.5, max_band_pct=6.0)
    # 1.5% * sqrt(24) = 7.3% → capped at 6%: 95k and 107k are out (−5% in, +7% out), 93k out.
    assert kept["floor_strike"].tolist() == [95_000.0]


def test_select_strikes_drops_events_with_no_prior_reference():
    refs = pd.Series([100_000.0], index=[T("2026-07-15 18:00", tz="UTC")])
    m = _ladder("2026-07-15 17:00", "2026-07-15 18:00", [100_000.0])
    assert kalshi.select_strikes(m, refs, band_pct=1.5).empty


# ---------------------------------------------------------------- binance bulk files


def _zip_csv(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("f.csv", text)
    return buf.getvalue()


@pytest.mark.parametrize("ts,header", [(1784073600000, False), (1784073600000000, False), (1784073600000, True)])
def test_parse_binance_klines_ms_us_and_header(ts, header):
    row = f"{ts},65000,65010,64990,65005,12.5,{ts + 59999},812000,431,6.1,396000,0\n"
    head = "open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,taker_buy_quote_volume,ignore\n"
    df = spot.parse_binance_klines(_zip_csv((head if header else "") + row))
    assert df["ts"].iloc[0] == T("2026-07-15", tz="UTC")
    assert df["close"].iloc[0] == 65005 and df["trades"].iloc[0] == 431


def test_vision_urls():
    base = "https://data.binance.vision/data"
    assert spot._vision_url(base, "futures/um/BTCUSDT", "monthly", "klines", "BTCUSDT", "1m", "2026-01") == \
        f"{base}/futures/um/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2026-01.zip"
    assert spot._vision_url(base, "futures/um/BTCUSDT", "monthly", "fundingRate", "BTCUSDT", None, "2026-07") == \
        f"{base}/futures/um/monthly/fundingRate/BTCUSDT/BTCUSDT-fundingRate-2026-07.zip"


# ---------------------------------------------------------------- storage and rate limiting


def test_store_roundtrip_and_resume(tmp_path):
    assert not store.is_done(tmp_path, "2026-07-15")
    store.write_part(pd.DataFrame({"a": [1, 2]}), tmp_path, "2026-07-15")
    store.write_part(pd.DataFrame({"a": [3]}), tmp_path, "2026-07-16")
    assert store.is_done(tmp_path, "2026-07-15")
    assert store.read_parts(tmp_path)["a"].tolist() == [1, 2, 3]
    assert not list(tmp_path.glob("*.tmp"))


def test_day_keys_end_exclusive():
    days = store.day_keys(T("2026-07-15", tz="UTC"), T("2026-07-18", tz="UTC"))
    assert [d.day for d in days] == [15, 16, 17]


def test_rate_limiter_enforces_rate():
    lim = RateLimiter(rate=50, burst=1)
    t = time.monotonic()
    for _ in range(11):
        lim.acquire()
    assert time.monotonic() - t >= 0.19  # 10 waits at 20 ms each


# ---------------------------------------------------------------- positioning, trades, events


def test_parse_binance_metrics():
    head = ("create_time,symbol,sum_open_interest,sum_open_interest_value,count_toptrader_long_short_ratio,"
            "sum_toptrader_long_short_ratio,count_long_short_ratio,sum_taker_long_short_vol_ratio\n")
    row = "2026-07-15 00:05:00,BTCUSDT,105529.04,6858159902.67,1.28,1.47,1.19,0.74\n"
    df = spot.parse_binance_metrics(_zip_csv(head + row))
    assert df["ts"].iloc[0] == T("2026-07-15 00:05", tz="UTC")
    assert df["oi_btc"].iloc[0] == pytest.approx(105529.04) and df["taker_buy_sell_vol"].iloc[0] == 0.74


@pytest.mark.parametrize("ts,header", [(1784073600000, True), (1784073600000000, False)])
def test_parse_binance_aggtrades_spot_and_futures(ts, header):
    head = "agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,is_buyer_maker\n"
    row = f"1,65000.5,0.25,10,12,{ts},true\n"
    df = spot.parse_binance_aggtrades(_zip_csv((head if header else "") + row))
    assert df["ts"].iloc[0] == T("2026-07-15", tz="UTC") and bool(df["buyer_maker"].iloc[0])


def test_parse_trades_keeps_taker_side_and_price():
    raw = [{"ticker": "X", "created_time": "2026-07-15T21:44:58.151266Z", "yes_price_dollars": "0.4100",
            "count_fp": "1,250.00", "taker_side": "no"}]
    row = kalshi.parse_trades(raw).iloc[0]
    assert row["yes_price"] == pytest.approx(0.41) and row["count"] == 1250 and row["taker_side"] == "no"


def test_events_calendar_converts_et_to_utc():
    from pinpricer.research.events import load_events
    e = load_events()
    cpi = e[(e.event == "CPI") & (e.date == "2026-07-14")].ts.iloc[0]
    assert cpi == T("2026-07-14 12:30", tz="UTC")  # 8:30 EDT
    assert set(e.event) == {"CPI", "NFP", "FOMC"}


def test_trade_sample_does_not_depend_on_outcome():
    # Two hourly events; the second's settlement is the outcome and must not affect which strikes are kept.
    rows = []
    for close, settle in (("2026-07-15 17:00", 100_000.0), ("2026-07-15 18:00", 100_000.0)):
        for k in (99_000.0, 99_800.0, 100_200.0, 101_000.0):
            rows.append({"ticker": f"{close}-{k}", "event_ticker": close, "cadence": "hourly",
                         "open_time": T(close, tz="UTC") - pd.Timedelta(hours=1), "close_time": T(close, tz="UTC"),
                         "floor_strike": k, "expiration_value": settle})
    m = pd.DataFrame(rows)
    kept = kalshi.trade_sample(m, "hourly", 2, 0.5, 0, T("2026-07-15", tz="UTC"))
    m2 = m.copy()
    m2.loc[m2.event_ticker == "2026-07-15 18:00", "expiration_value"] = 101_000.0  # different outcome
    kept2 = kalshi.trade_sample(m2, "hourly", 2, 0.5, 0, T("2026-07-15", tz="UTC"))
    assert kept[kept.event_ticker == "2026-07-15 18:00"].ticker.tolist() == \
        kept2[kept2.event_ticker == "2026-07-15 18:00"].ticker.tolist() == ["2026-07-15 18:00-99800.0", "2026-07-15 18:00-100200.0"]
