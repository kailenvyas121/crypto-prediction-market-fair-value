"""Scheduled macro releases: how much extra variance they add, and whether a bump helps pricing.

For each release, compare realized variance over the next 5 and 60 minutes with what the
HAR + time-of-week + DVOL forecast expected one minute before. Fit one multiplier per event type
on releases before TRAIN_END, apply it to hourly contracts spanning a release after it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pinpricer.config import CONFIG_DIR
from pinpricer.model import fv
from pinpricer.model.vol import VolModel, proxy_minutes
from pinpricer.research import calibration as cal


def load_events() -> pd.DataFrame:
    e = pd.read_csv(CONFIG_DIR / "events.csv", comment="#")
    e["ts"] = pd.to_datetime(e["date"] + " " + e["time_et"]).dt.tz_localize("America/New_York").dt.tz_convert("UTC")
    return e


def run() -> dict:
    px = proxy_minutes()
    vm = VolModel(px, cal.TRAIN_END)
    ev = load_events()
    ev = ev[(ev.ts > px.index[0] + pd.Timedelta(days=8)) & (ev.ts < px.index[-1] - pd.Timedelta(hours=2))].copy()
    c = np.concatenate([[0.0], np.cumsum(vm.r2)])
    pos = px.index.get_indexer(ev.ts)  # forecast made at the release time; windows start with the release minute
    win = {"5m": (0, 5), "60m": (0, 60), "after_5m": (5, 60)}

    def ratios(p0: np.ndarray) -> dict[str, np.ndarray]:
        out = {}
        for k, (a, b) in win.items():
            fc = vm.window_variance(p0 + a, np.full(len(p0), b - a), "har_iv")[0]
            out[k] = (c[p0 + b + 1] - c[p0 + a + 1]) / fc
        return out

    for k, v in ratios(pos).items():
        ev[f"ratio_{k}"] = v
    ev["train"] = ev.ts < cal.TRAIN_END

    # Control: same weekday and time one and two weeks either side, on non-release days. The
    # time-of-week profile already averages some release days in, so the bump is measured
    # relative to these controls, not to 1.
    ev_ts = set(ev.ts)
    lo_ok, hi_ok = px.index[0] + pd.Timedelta(days=8), px.index[-1] - pd.Timedelta(hours=2)
    ctrl = pd.DataFrame([{"event": r.event, "ts": r.ts + pd.Timedelta(days=k), "train": r.train}
                         for r in ev.itertuples() for k in (-14, -7, 7, 14)
                         if r.ts + pd.Timedelta(days=k) not in ev_ts and lo_ok < r.ts + pd.Timedelta(days=k) < hi_ok])
    for k, v in ratios(px.index.get_indexer(ctrl.ts)).items():
        ctrl[f"ratio_{k}"] = v

    def bump(e: pd.DataFrame, cc: pd.DataFrame, k: str) -> float:
        return float(max(1.0, e[f"ratio_{k}"].median() / cc[f"ratio_{k}"].median()))

    res: dict = {"by_event": {}}
    for name, g in ev.groupby("event"):
        cg = ctrl[ctrl.event == name]
        res["by_event"][name] = {
            "n": len(g), **{f"bump_{k}": bump(g, cg, k) for k in win},
            "releases": [{"date": str(r.ts.date()), "ratio_5m": round(float(r.ratio_5m), 2),
                          "ratio_60m": round(float(r.ratio_60m), 2)} for r in g.itertuples()]}
    # Pooled bumps fit on train releases only (few releases per type, so pool them)
    fit = {k: bump(ev[ev.train], ctrl[ctrl.train], k) for k in ("5m", "after_5m")}
    res["pooled_train_fit"] = {"n_releases": int(ev.train.sum()), "bump_first_5m": fit["5m"],
                               "bump_minutes_5_to_60": fit["after_5m"]}

    # Apply to test-period hourly contracts whose remaining window contains a release
    nu = cal.fit_tails(px, vm)["nu"]
    basis = cal.fit_basis(px)
    rows = cal.load_rows("KXBTCD", px)
    rows["spot"] *= np.exp(basis)
    d = rows[rows.quoted & ~rows.train & (rows.cadence == "hourly")].copy()
    tev = ev[~ev.train]
    hit = np.zeros(len(d), bool)
    extra = np.zeros(len(d))
    t_pos, tau = d["t_pos"].to_numpy(), d["tau"].to_numpy()
    end_pos = np.minimum(t_pos + tau, len(vm.s) - 1)
    level = vm.window_variance(t_pos, tau, "har_iv")[0] / (vm.s_cum[end_pos + 1] - vm.s_cum[t_pos + 1])
    for r in tev.itertuples():
        e_pos = px.index.get_loc(r.ts)
        for (a, b), m in (((0, 5), fit["5m"]), ((5, 60), fit["after_5m"])):
            lo, hi = np.maximum(t_pos, e_pos + a), np.minimum(t_pos + tau, e_pos + b)
            ov = hi > lo
            extra[ov] += (m - 1) * level[ov] * (vm.s_cum[hi[ov] + 1] - vm.s_cum[lo[ov] + 1])
            hit |= ov
    g = d[hit]
    v_tot, v_last = vm.window_variance(g.t_pos.to_numpy(), g.tau.to_numpy(), "har_iv")
    nus = np.where(g.tau <= 30, nu["15m"], nu["60m"])
    p0 = fv.prob_above(g.spot, g.floor_strike, fv.averaged_variance(v_tot, v_last), nus)
    p1 = fv.prob_above(g.spot, g.floor_strike, fv.averaged_variance(v_tot + extra[hit], v_last), nus)
    res["test_hourly_contracts_spanning_a_release"] = {
        "n_rows": len(g), "n_events": int(g.event_ticker.nunique()),
        "brier_v4": cal.brier(p0, g.y), "brier_v4_plus_bump": cal.brier(p1, g.y), "brier_mid": cal.brier(g.mid, g.y),
        "mae_vs_mid_cents_v4": float(100 * np.mean(np.abs(p0 - g.mid))),
        "mae_vs_mid_cents_bump": float(100 * np.mean(np.abs(p1 - g.mid))),
        "ci95_bump_minus_mid": cal.day_bootstrap(g.assign(p_bump=p1), "p_bump", "mid"),
        "ci95_bump_minus_v4": cal.day_bootstrap(g.assign(p_bump=p1, p_v4=p0), "p_bump", "p_v4")}
    return res
