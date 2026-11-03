"""Variance forecasts on the BRTI proxy, all in per-minute log-variance units.

Built on the 1-minute USD composite (median of Coinbase and Bitstamp, both BRTI constituents),
which tracks Kalshi's settlement to about 1 bp. Every feature at minute t uses data up to t only.

Forecasters, simplest first:
  flat    trailing 30-day mean of r²
  ewma    exponentially weighted r², 60-minute half-life
  har     log-HAR on deseasonalized r² (1h / 24h / 7d), times the ET half-hour-of-week profile
  har_iv  har plus Deribit DVOL as a regressor
"""

from __future__ import annotations

from typing import ClassVar

import numpy as np
import pandas as pd

from pinpricer.config import RAW_DIR
from pinpricer.data import store

MIN_PER_YEAR = 525_600


def proxy_minutes() -> pd.Series:
    """Index level at each minute boundary: median close of Coinbase and Bitstamp, keyed by bar end."""
    cb = store.read_parts(RAW_DIR / "spot" / "coinbase_BTC-USD_1m").set_index("ts")["close"]
    bs = store.read_parts(RAW_DIR / "spot" / "bitstamp_btcusd_1m").set_index("ts")["close"]
    px = pd.concat([cb, bs], axis=1).median(axis=1)
    grid = pd.date_range(px.index.min(), px.index.max(), freq="min", tz="UTC")
    px = px.reindex(grid).ffill()
    px.index = px.index + pd.Timedelta(minutes=1)
    return px


def dvol_minutes(index: pd.DatetimeIndex) -> pd.Series:
    """Latest hourly DVOL close known at each minute, as a per-minute variance."""
    d = store.read_parts(RAW_DIR / "deribit" / "dvol_BTC_3600s")
    known = pd.Series(d["close"].to_numpy(), index=d["ts"] + pd.Timedelta(hours=1)).sort_index()
    iv = known.reindex(index, method="ffill")
    return (iv / 100) ** 2 / MIN_PER_YEAR


def season_bucket(index: pd.DatetimeIndex) -> np.ndarray:
    """ET half-hour-of-week, 0..335. ET because US data releases and the US open drive the profile."""
    et = index.tz_convert("America/New_York")
    return np.asarray(et.dayofweek * 48 + et.hour * 2 + et.minute // 30)


def _trailing_mean(x: np.ndarray, n: int) -> np.ndarray:
    c = np.concatenate([[0.0], np.cumsum(x)])
    out = np.full(len(x), np.nan)
    out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def _leading_mean(x: np.ndarray, n: int) -> np.ndarray:
    """Mean of x over the n minutes after each point (the forecast target)."""
    m = _trailing_mean(x, n)
    return np.concatenate([m[n:], np.full(n, np.nan)])


class VolModel:
    """Fits the seasonal profile and HAR weights on [.., train_end) and forecasts window variance anywhere."""

    HORIZONS: ClassVar[dict[str, int]] = {"1h": 60, "24h": 1440}

    def __init__(self, px: pd.Series, train_end: pd.Timestamp):
        self.px, self.train_end = px, train_end
        idx = px.index
        r = np.log(px).diff().fillna(0.0).to_numpy()
        # return of the bar ending at idx[i]; clip one-off print errors at 2% per minute
        self.r2 = np.minimum(r**2, 0.02**2)
        self.bucket = season_bucket(idx - pd.Timedelta(minutes=1))
        train = np.asarray(idx < train_end)

        prof = pd.Series(self.r2[train]).groupby(self.bucket[train]).mean()
        prof = prof.reindex(range(336)).interpolate().bfill().ffill()
        self.season = (prof / self.r2[train].mean()).to_numpy()
        self.s = self.season[self.bucket]
        self.s_cum = np.concatenate([[0.0], np.cumsum(self.s)])

        u = self.r2 / self.s
        self.feat = pd.DataFrame({
            "rv_1h": _trailing_mean(u, 60), "rv_24h": _trailing_mean(u, 1440),
            "rv_7d": _trailing_mean(u, 10080), "iv": dvol_minutes(idx).to_numpy(),
        }, index=idx)
        self.flat = _trailing_mean(self.r2, 30 * 1440)
        self.ewma = pd.Series(self.r2).ewm(halflife=60).mean().to_numpy()

        self.coef: dict[tuple[str, bool], np.ndarray] = {}
        hourly = np.asarray(idx.minute == 0)
        for h, n in self.HORIZONS.items():
            y = _leading_mean(u, n)
            for with_iv in (False, True):
                X = self._design(with_iv)
                ok = train & hourly & np.isfinite(y) & np.isfinite(X).all(1) & (y > 0)
                b, *_ = np.linalg.lstsq(X[ok], np.log(y[ok]), rcond=None)
                smear = np.mean(np.exp(np.log(y[ok]) - X[ok] @ b))
                self.coef[(h, with_iv)] = np.append(b, smear)

    def _design(self, with_iv: bool) -> np.ndarray:
        cols = ["rv_1h", "rv_24h", "rv_7d"] + (["iv"] if with_iv else [])
        X = np.log(np.maximum(self.feat[cols].to_numpy(), 1e-14))
        return np.column_stack([np.ones(len(X)), X])

    def weights(self) -> pd.DataFrame:
        names = ["const", "log RV 1h", "log RV 24h", "log RV 7d", "log DVOL²", "smearing"]
        rows = {}
        for (h, iv), b in self.coef.items():
            rows[f"{h}{' + DVOL' if iv else ''}"] = dict(zip([n for n in names if iv or n != "log DVOL²"], b))
        return pd.DataFrame(rows).T

    def window_variance(self, t_pos: np.ndarray, tau_min: np.ndarray, kind: str):
        """(variance to expiry, variance of the final minute) for windows starting at index positions t_pos."""
        # returns over the window are those of bars ending at positions t_pos+1 .. t_pos+τ
        end = np.minimum(t_pos + tau_min, len(self.s) - 1)
        if kind in ("flat", "ewma"):
            lvl = (self.flat if kind == "flat" else self.ewma)[t_pos]
            return lvl * tau_min, lvl
        seas_sum = self.s_cum[end + 1] - self.s_cum[t_pos + 1]
        seas_last = self.s[end]
        with_iv = kind == "har_iv"
        X = self._design(with_iv)[t_pos]
        lvl = np.empty(len(t_pos))
        short = tau_min <= 120
        for h, mask in (("1h", short), ("24h", ~short)):
            b = self.coef[(h, with_iv)]
            lvl[mask] = np.exp(X[mask] @ b[:-1]) * b[-1]
        return lvl * seas_sum, lvl * seas_last
