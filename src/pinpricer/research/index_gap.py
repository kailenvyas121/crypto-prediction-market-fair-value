"""Why does the 15-minute model trail the Kalshi mid? Test: index measurement vs volatility.

Invert each quote for the index level the market must be using ("implied spot"), holding our
variance and tails fixed. If our volatility were wrong, the implied-spot gap would grow with the
strike distance. If our index reading is wrong, the gap is a level error that is the same for
every contract at that minute, so two separate markets (the 15-minute contract and the hourly
ladder) should imply the same gap at the same minute.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from pinpricer.model import fv
from pinpricer.model.vol import VolModel, proxy_minutes
from pinpricer.research import calibration as cal


def implied_gap_bp(d: pd.DataFrame, var: np.ndarray, nu: np.ndarray) -> np.ndarray:
    """ln(S_implied / S_model) in bp, where S_implied makes the model price equal the mid."""
    zq = stats.t.isf(d["mid"].to_numpy(), nu) * np.sqrt((nu - 2) / nu)
    s_impl = d["floor_strike"].to_numpy() / np.exp(zq * np.sqrt(var))
    return 1e4 * np.log(s_impl / d["spot"].to_numpy())


def run() -> dict:
    px = proxy_minutes()
    vm = VolModel(px, cal.TRAIN_END)
    nu = cal.fit_tails(px, vm)["nu"]
    basis = cal.fit_basis(px)
    rows = pd.concat([cal.load_rows("KXBTC15M", px), cal.load_rows("KXBTCD", px)], ignore_index=True)
    rows["spot"] *= np.exp(basis)
    d = rows[rows["quoted"] & ~rows["train"] & rows["mid"].between(0.15, 0.85)].copy()
    d["p"], var = cal.price(d, vm, "har_iv", True, True, nu)
    nus = np.where(d["tau"] <= 30, nu["15m"], nu["60m"])
    d["gap_bp"] = implied_gap_bp(d, var, nus)
    d["x_sigma"] = np.log(d["floor_strike"] / d["spot"]) / np.sqrt(var)

    res: dict = {}
    for cad in ["fifteen_min", "hourly"]:
        g = d[(d.cadence == cad) & (d.tau >= 2)]
        slope = float(np.polyfit(g["x_sigma"], g["gap_bp"], 1)[0])
        res[cad] = {"n": len(g), "median_abs_gap_bp": float(g["gap_bp"].abs().median()),
                    "p90_abs_gap_bp": float(g["gap_bp"].abs().quantile(0.9)),
                    "slope_gap_bp_per_sigma_of_distance": slope}

    # Same minute, two markets: the 15-minute contract vs the median over near-money hourly strikes
    h = d[(d.cadence == "hourly") & (d.tau >= 5)].groupby("ts")["gap_bp"].median().rename("hourly_gap")
    q = d[(d.cadence == "fifteen_min") & (d.tau >= 2)].set_index("ts")[["gap_bp"]].join(h, how="inner").dropna()
    res["same_minute"] = {"n_minutes": len(q), "corr_15m_vs_hourly_gap": float(q["gap_bp"].corr(q["hourly_gap"])),
                          "median_abs_15m_gap_bp": float(q["gap_bp"].abs().median()),
                          "median_abs_15m_minus_hourly_bp": float((q["gap_bp"] - q["hourly_gap"]).abs().median())}

    # Reprice 15-minute contracts on the index level the hourly ladder implies at that minute
    f = d[d.cadence == "fifteen_min"].merge(h, left_on="ts", right_index=True)
    f = f[f["tau"] >= 2]
    base_var = cal.price(f, vm, "har_iv", True, True, nu)[1]
    p_lad = fv.prob_above(f["spot"] * np.exp(f["hourly_gap"] / 1e4), f["floor_strike"], base_var, nu["15m"])
    res["reprice_15m_on_ladder_implied_index"] = {
        "n": len(f), "mae_vs_mid_cents_model": float(100 * np.mean(np.abs(f["p"] - f["mid"]))),
        "mae_vs_mid_cents_ladder_index": float(100 * np.mean(np.abs(p_lad - f["mid"]))),
        "brier_model": cal.brier(f["p"], f["y"]), "brier_ladder_index": cal.brier(p_lad, f["y"]),
        "brier_mid": cal.brier(f["mid"], f["y"])}
    return res
