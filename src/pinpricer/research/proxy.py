"""How well do free exchange prices track Kalshi's official settlement index (BRTI)?

Each source's price at every hourly close (its 1-minute close ending at the settlement time)
is compared with Kalshi's 60-second BRTI settlement value for that hour.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pinpricer.config import RAW_DIR
from pinpricer.data import store


def _bar_end(path: str) -> pd.Series:
    s = store.read_parts(RAW_DIR / path).set_index("ts")["close"]
    s = s[~s.index.duplicated()].sort_index()
    s.index = s.index + pd.Timedelta(minutes=1)
    return s


def run() -> dict:
    m = pd.read_parquet(RAW_DIR / "kalshi" / "KXBTCD" / "markets.parquet",
                        columns=["event_ticker", "close_time", "expiration_value"])
    m = m.dropna().drop_duplicates("event_ticker").set_index("close_time")["expiration_value"].sort_index()
    m = m[~m.index.duplicated()]
    src = {"coinbase": _bar_end("spot/coinbase_BTC-USD_1m"), "bitstamp": _bar_end("spot/bitstamp_btcusd_1m"),
           "binance_usdt": _bar_end("binance/spot_BTCUSDT_1m")}
    src["median_coinbase_bitstamp"] = pd.concat([src["coinbase"], src["bitstamp"]], axis=1).median(axis=1)
    res: dict = {"settlements": len(m)}
    for name, s in src.items():
        d = (1e4 * np.log(s.reindex(m.index) / m)).dropna()
        res[name] = {"n": len(d), "median_diff_bp": float(d.median()), "median_abs_bp": float(d.abs().median()),
                     "p95_abs_bp": float(d.abs().quantile(0.95))}
    return res
