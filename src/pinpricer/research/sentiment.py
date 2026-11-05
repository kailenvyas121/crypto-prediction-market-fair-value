"""Attention and crowd sentiment: what they forecast, and whether they move the crowd's pricing error.

Attention proxy: daily Wikipedia pageviews of "Bitcoin" (a published retail-attention measure; X data
needs an enterprise licence). Euphoria proxy: BTC's trailing 7-day return.
  1. Does an attention shock predict next-day realized volatility beyond a daily HAR? (out of sample)
  2. Does it predict BTC's next 7-day return? (out of sample)
  3. Are Kalshi's far-from-the-money contracts more overpriced on the side the crowd is excited about?
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pinpricer.config import RAW_DIR
from pinpricer.data import store
from pinpricer.model.vol import VolModel, proxy_minutes
from pinpricer.research import calibration as cal
from pinpricer.research.positioning import _oos_r2

RNG = np.random.default_rng(1)


def _daily(px: pd.Series, vm: VolModel) -> pd.DataFrame:
    views = pd.read_parquet(store.part_path(RAW_DIR / "attention", "wikipedia_Bitcoin")).set_index("date")["views"]
    lv = np.log(views)
    d = pd.DataFrame({"att_shock": (lv - lv.rolling(30).mean()) / lv.rolling(30).std()})
    r2 = pd.Series(vm.r2, index=px.index - pd.Timedelta(minutes=1)).resample("1D")
    rv = r2.sum().where(r2.count() >= 1380)  # full days only
    close = np.log(px).resample("1D").last()
    d = d.join(np.log(rv).rename("lrv")).join(close.rename("lp"))
    d["lrv_7"], d["lrv_30"] = d["lrv"].rolling(7).mean(), d["lrv"].rolling(30).mean()
    d["y_lrv_next"] = d["lrv"].shift(-1)
    d["ret_7d_fwd"] = 1e4 * (d["lp"].shift(-7) - d["lp"])
    d["ret_7d_past"] = 1e4 * (d["lp"] - d["lp"].shift(7))
    d["train"] = d.index < cal.TRAIN_END
    return d


def _ci(g: pd.DataFrame, col: str, n: int = 2000) -> list[float]:
    e = g.groupby("event_ticker")[col].agg(["sum", "count"])
    s, c = e["sum"].to_numpy(), e["count"].to_numpy()
    idx = RNG.integers(0, len(e), size=(n, len(e)))
    b = s[idx].sum(1) / c[idx].sum(1)
    return [float(100 * np.percentile(b, 2.5)), float(100 * np.percentile(b, 97.5))]


def run() -> dict:
    px = proxy_minutes()
    vm = VolModel(px, cal.TRAIN_END)
    d = _daily(px, vm)
    res: dict = {}

    v = d.dropna(subset=["att_shock", "lrv", "lrv_7", "lrv_30", "y_lrv_next"])
    tr, te = v[v.train], v[~v.train]
    base, plus = ["lrv", "lrv_7", "lrv_30"], ["lrv", "lrv_7", "lrv_30", "att_shock"]
    res["attention_vs_next_day_vol"] = {
        "days_train": len(tr), "days_test": len(te),
        "oos_r2_har": _oos_r2(tr[base], tr.y_lrv_next, te[base], te.y_lrv_next),
        "oos_r2_har_plus_attention": _oos_r2(tr[plus], tr.y_lrv_next, te[plus], te.y_lrv_next),
        "corr_attention_with_next_day_log_rv_test": float(te.att_shock.corr(te.y_lrv_next))}
    w = d.dropna(subset=["att_shock", "ret_7d_fwd"])
    tr, te = w[w.train], w[~w.train]
    res["attention_vs_next_7d_return"] = {
        "oos_r2": _oos_r2(tr[["att_shock"]], tr.ret_7d_fwd, te[["att_shock"]], te.ret_7d_fwd),
        "corr_test": float(te.att_shock.corr(te.ret_7d_fwd)),
        "note": "daily samples with overlapping 7-day targets; R² is out of sample"}

    # 3. Crowd error on the far side of the ladder, by euphoria and by attention
    nu = cal.fit_tails(px, vm)["nu"]
    basis = cal.fit_basis(px)
    rows = cal.load_rows("KXBTCD", px)
    rows = rows[rows.quoted].copy()
    rows["spot"] *= np.exp(basis)
    rows["p"], _ = cal.price(rows, vm, "har_iv", True, True, nu)
    # Cheap side as both model and market see it. "YES above K" is cheap when K is well above spot
    # (an upside longshot); when K is well below spot its NO side is the cheap downside longshot.
    up = rows[(rows.p < 0.3) & (rows.mid < 0.5)].assign(side="upside (BTC must rise)")
    up["over"] = up.mid - up.y
    dn = rows[(rows.p > 0.7) & (rows.mid > 0.5)].assign(side="downside (BTC must fall)")
    dn["over"] = (1 - dn.mid) - (1 - dn.y)
    far = pd.concat([up, dn])
    day = far.ts.dt.floor("D") - pd.Timedelta(days=1)  # yesterday's values are known today
    far["ret_7d_past"] = d["ret_7d_past"].reindex(day).to_numpy()
    far["att"] = d["att_shock"].reindex(day).to_numpy()
    far = far.dropna(subset=["ret_7d_past", "att"])
    res["crowd_error"] = {"rows": len(far), "events": int(far.event_ticker.nunique()),
                          "note": "mid − outcome on cheap (P<0.3) contracts, cents; >0 means the crowd overpays"}
    for name, col in (("by_trailing_7d_return", "ret_7d_past"), ("by_attention_shock", "att")):
        b = pd.qcut(far[col], 3, labels=["low", "mid", "high"])
        res["crowd_error"][name] = {
            f"{side} | {lvl}": {"n": len(g), "overpricing_c": float(100 * g.over.mean()), "ci95_c": _ci(g, "over")}
            for (side, lvl), g in far.groupby(["side", b], observed=True)}
    res["crowd_error"]["all"] = {s: {"n": len(g), "overpricing_c": float(100 * g.over.mean()), "ci95_c": _ci(g, "over")}
                                 for s, g in far.groupby("side")}
    return res
