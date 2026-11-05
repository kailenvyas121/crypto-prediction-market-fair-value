"""Crypto as a one-factor market: how much of ETH and SOL is just BTC?

Beta and R² of each coin's log returns on BTC's, at 1 minute, 1 hour and 1 day, in the
study window (Binance USDT spot). Also: does the relationship hold in BTC's biggest moves?
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pinpricer.config import RAW_DIR, study_window
from pinpricer.data import store


def _close(sym: str) -> pd.Series:
    s = store.read_parts(RAW_DIR / "binance" / f"spot_{sym}_1m").set_index("ts")["close"]
    return s[~s.index.duplicated()].sort_index()


def run() -> dict:
    start, end = study_window()
    px = pd.concat({s: _close(s) for s in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]}, axis=1).loc[start:end].ffill()
    res: dict = {"window": [str(start.date()), str(end.date())]}
    for label, rule in (("1m", None), ("1h", "1h"), ("1d", "1D")):
        p = px if rule is None else px.resample(rule).last()
        r = np.log(p).diff().dropna()
        btc = r["BTCUSDT"]
        out = {}
        for c in ["ETHUSDT", "SOLUSDT"]:
            beta = float(np.cov(r[c], btc)[0, 1] / btc.var())
            corr = float(r[c].corr(btc))
            out[c] = {"beta": beta, "r2": corr**2, "vol_ratio_to_btc": float(r[c].std() / btc.std())}
            if label == "1h":
                big = btc.abs() > btc.abs().quantile(0.99)
                out[c]["beta_in_top1pct_btc_hours"] = float(np.cov(r[c][big], btc[big])[0, 1] / btc[big].var())
                out[c]["same_sign_share_top1pct"] = float((np.sign(r[c][big]) == np.sign(btc[big])).mean())
        res[label] = out
    ann = np.log(px).diff().std() * np.sqrt(525_600)
    res["annualized_vol_1m"] = {k: float(v) for k, v in ann.items()}
    return res
