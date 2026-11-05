"""What perp positioning (open interest, funding, basis, long/short ratios, taker flow) tells a pricer.

Three questions, each answered out of sample (fit before TRAIN_END, scored after):
  1. Direction: do these predict BTC's next 1h / 4h / 24h return?
  2. Volatility: do they improve next-hour variance beyond HAR + time of week + DVOL?
  3. Tails: is the downside tail fatter when longs are crowded?
Plus the "OI story" table: what price moves with rising vs falling OI are followed by.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pinpricer.config import RAW_DIR
from pinpricer.data import store
from pinpricer.model.vol import VolModel, proxy_minutes
from pinpricer.research.calibration import TRAIN_END


def _hourly_features(px: pd.Series, vm: VolModel) -> pd.DataFrame:
    met = store.read_parts(RAW_DIR / "binance" / "futures_um_BTCUSDT_metrics").set_index("ts").sort_index()
    met = met[~met.index.duplicated()].replace(0, np.nan)  # zeros are missing values in these files
    # A snapshot stamped t may summarize the 5 minutes after t; use it only from t + 5 min.
    met.index = met.index + pd.Timedelta(minutes=5)
    fund = store.read_parts(RAW_DIR / "binance" / "futures_um_BTCUSDT_fundingRate").set_index("ts").sort_index()
    perp = store.read_parts(RAW_DIR / "binance" / "futures_um_BTCUSDT_1m").set_index("ts")["close"]
    spot = store.read_parts(RAW_DIR / "binance" / "spot_BTCUSDT_1m").set_index("ts")["close"]
    basis = (1e4 * np.log(perp / spot)).rolling("60min").mean()

    hours = px.index[(px.index.minute == 0) & (px.index >= met.index.min() + pd.Timedelta(days=8))]
    hours = hours[hours <= min(met.index.max(), fund.index.max(), px.index[-1] - pd.Timedelta(hours=25))]
    m = met.reindex(hours, method="ffill")
    oi = np.log(met["oi_usd"])
    oi_h = oi.reindex(hours, method="ffill")
    lp = np.log(px)
    f = pd.DataFrame(index=hours)
    f["ret_1h"] = 1e4 * (lp.reindex(hours) - lp.reindex(hours - pd.Timedelta(hours=1)).to_numpy())
    f["ret_24h"] = 1e4 * (lp.reindex(hours) - lp.reindex(hours - pd.Timedelta(hours=24)).to_numpy())
    f["d_oi_1h"] = 100 * (oi_h - oi.reindex(hours - pd.Timedelta(hours=1), method="ffill").to_numpy())
    f["d_oi_24h"] = 100 * (oi_h - oi.reindex(hours - pd.Timedelta(hours=24), method="ffill").to_numpy())
    oi_btc = np.log(met["oi_btc"])
    f["oi_vs_30d"] = (oi_btc - oi_btc.rolling("30D").mean()).reindex(hours, method="ffill") / \
        oi_btc.rolling("30D").std().reindex(hours, method="ffill")
    f["funding_bp"] = 1e4 * fund["funding_rate"].reindex(hours, method="ffill")
    f["basis_bp"] = basis.reindex(hours, method="ffill")
    f["top_ls"] = np.log(m["top_ls_positions"])
    f["acct_ls"] = np.log(m["ls_accounts"])
    f["taker_ratio"] = np.log(met["taker_buy_sell_vol"].rolling("60min").mean().reindex(hours, method="ffill"))

    pos = px.index.get_indexer(hours)
    for h in (1, 4, 24):
        f[f"fwd_{h}h"] = 1e4 * (lp.to_numpy()[np.minimum(pos + 60 * h, len(lp) - 1)] - lp.to_numpy()[pos])
    v1, _ = vm.window_variance(pos, np.full(len(pos), 60), "har_iv")
    v4, _ = vm.window_variance(pos, np.full(len(pos), 240), "har_iv")
    f["sd_1h_bp"], f["sd_4h_bp"] = 1e4 * np.sqrt(v1), 1e4 * np.sqrt(v4)
    r2 = vm.r2
    c = np.concatenate([[0.0], np.cumsum(r2)])
    f["rv_next_1h"] = c[pos + 61] - c[pos + 1]
    f["log_rv_ratio"] = np.log(np.maximum(f["rv_next_1h"], 1e-12) / v1)
    f["train"] = hours < TRAIN_END
    return f.iloc[:-24].replace([np.inf, -np.inf], np.nan).dropna()


SIGNALS = ["d_oi_1h", "d_oi_24h", "oi_vs_30d", "funding_bp", "basis_bp", "top_ls", "acct_ls", "taker_ratio",
           "ret_1h", "ret_24h"]


def _oos_r2(X_tr, y_tr, X_te, y_te) -> float:
    X_tr, X_te = np.column_stack([np.ones(len(X_tr)), X_tr]), np.column_stack([np.ones(len(X_te)), X_te])
    b, *_ = np.linalg.lstsq(X_tr, y_tr, rcond=None)
    return float(1 - np.sum((y_te - X_te @ b) ** 2) / np.sum((y_te - y_tr.mean()) ** 2))


def _tstat(x: pd.Series) -> float:
    return float(x.mean() / (x.std() / np.sqrt(len(x)))) if len(x) > 2 else float("nan")


def run() -> dict:
    px = proxy_minutes()
    vm = VolModel(px, TRAIN_END)
    f = _hourly_features(px, vm)
    tr, te = f[f.train], f[~f.train]
    z = lambda s: (s - tr[s.name].mean()) / tr[s.name].std()
    res: dict = {"hours": {"train": len(tr), "test": len(te)}, "test_from": str(TRAIN_END.date())}

    # 1. Direction. Each target is sampled every hour, so 4h and 24h windows overlap; the
    #    out-of-sample R² is still honest, the t-stats in the OI table are not used for these.
    res["direction_oos_r2"] = {}
    for h in (1, 4, 24):
        y = f"fwd_{h}h"
        res["direction_oos_r2"][f"{h}h"] = {
            "all_signals": _oos_r2(tr[SIGNALS], tr[y], te[SIGNALS], te[y]),
            **{s: _oos_r2(tr[[s]], tr[y], te[[s]], te[y]) for s in SIGNALS}}
        res["direction_oos_r2"][f"{h}h"]["corr_test"] = {s: float(te[s].corr(te[y])) for s in SIGNALS}

    # 2. Volatility: does positioning explain the HAR forecast's error?
    y_tr, y_te = tr["log_rv_ratio"], te["log_rv_ratio"]
    feats = ["d_oi_1h", "d_oi_24h", "oi_vs_30d", "funding_bp", "basis_bp", "top_ls", "acct_ls", "taker_ratio"]
    absf = lambda d: np.column_stack([d[feats].to_numpy(), np.abs(d[["d_oi_1h", "ret_1h", "basis_bp"]].to_numpy())])
    base_te = np.log(np.maximum(te["rv_next_1h"], 1e-12))
    res["volatility"] = {
        "har_dvol_season_oos_r2_log_rv": float(1 - np.sum((base_te - (base_te - y_te)) ** 2) /
                                               np.sum((base_te - base_te.mean()) ** 2)),
        "positioning_oos_r2_of_har_error": _oos_r2(absf(tr), y_tr, absf(te), y_te),
        "corr_test_with_har_error": {s: float(te[s].corr(y_te)) for s in feats} |
                                    {"abs_d_oi_1h": float(te["d_oi_1h"].abs().corr(y_te)),
                                     "abs_ret_1h": float(te["ret_1h"].abs().corr(y_te))},
    }

    # 3. Tails: standardized next-4h returns by long-crowding tercile (funding + OI build + top L/S)
    crowd = z(f["funding_bp"]) + z(f["d_oi_24h"]) + z(f["top_ls"])
    f = f.assign(crowd=crowd, zr=f["fwd_4h"] / f["sd_4h_bp"])
    f["crowd_bin"] = pd.qcut(f["crowd"], 3, labels=["least crowded long", "middle", "most crowded long"])
    g = f[~f.train].groupby("crowd_bin", observed=True)["zr"]
    res["tails_4h_by_long_crowding"] = {
        str(k): {"n": len(v), "mean": float(v.mean()), "p_down_2sd": float((v < -2).mean()),
                 "p_up_2sd": float((v > 2).mean()), "skew": float(v.skew()), "std": float(v.std())}
        for k, v in g}

    # 4. The OI story: last-hour price direction × OI direction, what follows (whole sample, non-overlapping 4h)
    big = f["d_oi_1h"].abs() > f["d_oi_1h"].abs().quantile(0.5)
    f["story"] = np.select(
        [(f.ret_1h > 0) & (f.d_oi_1h > 0), (f.ret_1h > 0) & (f.d_oi_1h < 0),
         (f.ret_1h < 0) & (f.d_oi_1h > 0), (f.ret_1h < 0) & (f.d_oi_1h < 0)],
        ["price up, OI up (new longs)", "price up, OI down (shorts covering)",
         "price down, OI up (new shorts)", "price down, OI down (longs exiting / liquidated)"], "flat")
    s = f[big & (f.index.hour % 4 == 0)]
    res["oi_story_baseline"] = {"n": len(f[f.index.hour % 4 == 0]),
                                "next_1h_vol_vs_forecast": float(np.exp(f["log_rv_ratio"].median())),
                                "next_4h_mean_return_bp": float(f.loc[f.index.hour % 4 == 0, "fwd_4h"].mean())}
    res["oi_story"] = {
        k: {"n": len(v), "next_1h_vol_vs_forecast": float(np.exp(v["log_rv_ratio"].median())),
            "next_4h_mean_return_bp": float(v["fwd_4h"].mean()), "t_stat": _tstat(v["fwd_4h"])}
        for k, v in s.groupby("story") if k != "flat"}
    # Liquidation-like hours: OI falls > 2% in an hour with a > 1% price move
    liq = f[(f.d_oi_1h < -2) & (f.ret_1h.abs() > 100)]
    res["liquidation_like_hours"] = {"n": len(liq),
                                     "next_1h_vol_vs_forecast": float(np.exp(liq["log_rv_ratio"].median())),
                                     "n_down": int((liq.ret_1h < 0).sum()), "n_up": int((liq.ret_1h > 0).sum()),
                                     "next_4h_mean_return_bp_after_down": float(liq[liq.ret_1h < 0]["fwd_4h"].mean()),
                                     "t_after_down": _tstat(liq[liq.ret_1h < 0]["fwd_4h"]),
                                     "next_4h_mean_return_bp_after_up": float(liq[liq.ret_1h > 0]["fwd_4h"].mean()),
                                     "t_after_up": _tstat(liq[liq.ret_1h > 0]["fwd_4h"])}
    # The largest OI flush in the sample, as a worked case
    w = f["d_oi_24h"].idxmin()
    res["largest_oi_flush"] = {"hour": str(w), "d_oi_24h_pct": float(f.loc[w, "d_oi_24h"]),
                               "ret_24h_bp": float(f.loc[w, "ret_24h"]), "funding_bp": float(f.loc[w, "funding_bp"])}
    # Case: the 10–11 Oct 2025 liquidation cascade, hour by hour (UTC)
    case = f.loc["2025-10-10 12:00":"2025-10-11 04:00"]
    res["case_2025_10_10"] = [
        {"hour": str(h), "ret_1h_bp": round(float(r.ret_1h), 1), "d_oi_1h_pct": round(float(r.d_oi_1h), 1),
         "oi_vs_30d_z": round(float(r.oi_vs_30d), 1), "funding_bp": round(float(r.funding_bp), 2),
         "forecast_next_1h_sd_bp": round(float(r.sd_1h_bp), 1),
         "realized_next_1h_sd_bp": round(float(1e4 * np.sqrt(r.rv_next_1h)), 1)}
        for h, r in case.iterrows()]
    res["signal_summary_test"] = {s: {"mean": float(te[s].mean()), "std": float(te[s].std())} for s in SIGNALS}
    return res
