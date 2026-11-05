"""Does the Binance perp lead Binance spot? Cross-correlation of 100 ms returns on aggTrades days."""

from __future__ import annotations

import numpy as np
import pandas as pd

from pinpricer.config import RAW_DIR
from pinpricer.data import store

STEP_MS = 100
MAX_LAG = 30  # ±3 s


def _grid(trades: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> np.ndarray:
    px = trades.set_index("ts")["price"].groupby(level=0).last()
    grid = pd.date_range(start, end, freq=f"{STEP_MS}ms", inclusive="left")
    return np.log(px.reindex(grid, method="ffill").to_numpy())


def run() -> dict:
    perp = RAW_DIR / "binance" / "futures_um_BTCUSDT_aggTrades"
    spot = RAW_DIR / "binance" / "spot_BTCUSDT_aggTrades"
    days = sorted(p.stem for p in perp.glob("*.parquet"))
    lags = np.arange(-MAX_LAG, MAX_LAG + 1)
    xc, r2_next = [], []
    for day in days:
        d0 = pd.Timestamp(day, tz="UTC") + pd.Timedelta(minutes=1)
        d1 = d0 + pd.Timedelta(hours=24) - pd.Timedelta(minutes=2)
        f = np.diff(_grid(pd.read_parquet(store.part_path(perp, day)), d0, d1))
        s = np.diff(_grid(pd.read_parquet(store.part_path(spot, day)), d0, d1))
        f, s = np.nan_to_num(f), np.nan_to_num(s)
        # corr(perp return at t, spot return at t + lag): a peak at lag > 0 means the perp moves first
        xc.append([np.corrcoef(f[max(0, -k):len(f) - max(0, k)], s[max(0, k):len(s) - max(0, -k)])[0, 1]
                   for k in lags])
        # how much of the next 1 s of spot is predicted by the last 1 s of perp minus spot
        w = 1000 // STEP_MS
        cf, cs = np.cumsum(f), np.cumsum(s)
        past_gap = (cf[w:-w] - cf[:-2 * w]) - (cs[w:-w] - cs[:-2 * w])
        next_spot = cs[2 * w:] - cs[w:-w]
        r2_next.append(np.corrcoef(past_gap, next_spot)[0, 1] ** 2)
    xc = np.mean(xc, axis=0)
    peak = int(lags[np.argmax(xc)])
    return {"days": days, "step_ms": STEP_MS,
            "xcorr": {int(k * STEP_MS): round(float(c), 4) for k, c in zip(lags, xc) if abs(k) <= 10},
            "peak_lag_ms": peak * STEP_MS,
            "share_of_lead_lag_corr_at_positive_lags": float(xc[lags > 0].clip(0).sum() /
                                                             (xc[lags > 0].clip(0).sum() + xc[lags < 0].clip(0).sum())),
            "r2_next_1s_spot_from_last_1s_perp_gap": float(np.mean(r2_next))}
