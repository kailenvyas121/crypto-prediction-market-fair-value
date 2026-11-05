"""Do market makers make money on Kalshi BTC contracts, and can the model tell good fills from bad?

Every fill has a taker and a maker. From the maker's side, per contract:
  settlement P&L   s·(p − Y)          exact and model-free (Y = 1 if YES settled)
  spread capture   s·(p − mid)        vs the Kalshi mid at the end of the prior minute
  model edge       s·(p − FV)         vs our fair value at the prior minute
  markout ~k min   s·(p − mid)        vs the mid at the end of the minute k+1 after the fill's
                                      minute, i.e. between k and k+1 minutes after the fill
where s = +1 if the maker sold YES (taker bought YES) and −1 if the maker bought YES. Kalshi
charges these series no maker fee (fee_type "quadratic"); the taker pays ceil(0.07·C·P(1−P)).
Sample: random test-period events (configs/data.yaml: kalshi.trades_sample), ladder strikes chosen
from the price known at each event's open, so the sample does not depend on outcomes.
Taker fees are computed per fill as ceil(0.07·C·P(1−P)) dollars, rounded up to the cent.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pinpricer.config import RAW_DIR
from pinpricer.data import kalshi, store
from pinpricer.model.vol import VolModel, proxy_minutes
from pinpricer.research import calibration as cal

RNG = np.random.default_rng(0)


def maker_sign(taker_side: pd.Series) -> np.ndarray:
    """+1 when the maker sold YES (the taker bought YES), −1 when the maker bought YES."""
    return np.where(taker_side == "yes", 1.0, -1.0)


def _load(series: str, px: pd.Series) -> pd.DataFrame:
    tdir = RAW_DIR / "kalshi" / series / "trades"
    sample = set(kalshi.sample_for_study(series)["ticker"])
    t = pd.concat([pd.read_parquet(f) for f in tdir.glob("*.parquet") if f.stem in sample], ignore_index=True)
    t = t.dropna(subset=["yes_price"])
    m = pd.read_parquet(RAW_DIR / "kalshi" / series / "markets.parquet",
                        columns=["ticker", "event_ticker", "close_time", "floor_strike", "result", "cadence"])
    t = t.merge(m, on="ticker")
    t = t[t["result"].isin(["yes", "no"]) & (t["ts"] < t["close_time"])].copy()
    t["y"] = (t["result"] == "yes").astype(float)
    t["s"] = maker_sign(t["taker_side"])
    t["minute"] = t["ts"].dt.floor("min")
    t["tau"] = np.ceil((t["close_time"] - t["minute"]).dt.total_seconds() / 60).astype(int)
    t["t_pos"] = px.index.get_indexer(t["minute"])
    t = t[(t["t_pos"] >= 0) & (t["tau"] >= 1)]

    c = store.read_parts(RAW_DIR / "kalshi" / series / "candles")
    c = c[c["ticker"].isin(t["ticker"].unique())][["ticker", "ts", "yes_bid", "yes_ask"]]
    c["mid"] = (c["yes_bid"] + c["yes_ask"]) / 2
    c.loc[(c["yes_bid"] <= 0) | (c["yes_ask"] >= 1), "mid"] = np.nan
    mids = c.set_index(["ticker", "ts"])["mid"]
    # candle ts is the minute's end; the fill's own minute ends at minute + 1
    for k, col in ((0, "mid_0"), (2, "mid_1m"), (6, "mid_5m")):
        key = pd.MultiIndex.from_arrays([t["ticker"], t["minute"] + pd.Timedelta(minutes=k)])
        t[col] = mids.reindex(key).to_numpy()
    return t.reset_index(drop=True)


def _wmean(x: pd.Series, w: pd.Series) -> float:
    ok = x.notna()
    return float((x[ok] * w[ok]).sum() / w[ok].sum()) if ok.any() else float("nan")


def _ci(d: pd.DataFrame, col: str, n: int = 2000) -> tuple[float, float]:
    """95% CI of the contract-weighted mean, resampling whole UTC days (events on one day share a price path)."""
    g = d.assign(v=d[col] * d["count"], day=d["close_time"].dt.floor("D")).groupby("day")[["v", "count"]].sum()
    v, w = g["v"].to_numpy(), g["count"].to_numpy()
    idx = RNG.integers(0, len(g), size=(n, len(g)))
    s = v[idx].sum(1) / w[idx].sum(1)
    return float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5))


def _summary(d: pd.DataFrame) -> dict:
    w = d["count"]
    return {"fills": len(d), "contracts": float(w.sum()), "events": int(d["event_ticker"].nunique()),
            "settlement_pnl_c": 100 * _wmean(d["pnl"], w), "ci95_c": [100 * x for x in _ci(d, "pnl")],
            "spread_capture_c": 100 * _wmean(d["capture"], w),
            "markout_1m_c": 100 * _wmean(d["mo_1m"], w), "markout_5m_c": 100 * _wmean(d["mo_5m"], w),
            "taker_fee_paid_c": 100 * _wmean(d["taker_fee"], w)}


def run() -> dict:
    px = proxy_minutes()
    vm = VolModel(px, cal.TRAIN_END)
    nu = cal.fit_tails(px, vm)["nu"]
    basis = cal.fit_basis(px)
    t = pd.concat([_load("KXBTC15M", px), _load("KXBTCD", px)], ignore_index=True)
    t["spot"] = px.to_numpy()[t["t_pos"]] * np.exp(basis)
    t["fv"], _ = cal.price(t, vm, "har_iv", True, True, nu)

    p = t["yes_price"]
    t["pnl"] = t["s"] * (p - t["y"])
    t["capture"] = t["s"] * (p - t["mid_0"])
    t["mo_1m"] = t["s"] * (p - t["mid_1m"])
    t["mo_5m"] = t["s"] * (p - t["mid_5m"])
    t["edge"] = t["s"] * (p - t["fv"])
    t["taker_fee"] = np.ceil(100 * 0.07 * t["count"] * p * (1 - p) - 1e-9) / 100 / t["count"]

    res: dict = {"note": "cents per contract, contract-weighted; maker side; CIs resample whole days"}
    res["all"] = {cad: _summary(g) for cad, g in t.groupby("cadence")}

    # Does the model separate good fills from toxic ones? Bucket fills by the model's edge for the maker.
    eb = pd.cut(t["edge"], [-1, -0.05, -0.02, 0, 0.02, 0.05, 1],
                labels=["< −5¢", "−5 to −2¢", "−2 to 0¢", "0 to 2¢", "2 to 5¢", "> 5¢"])
    res["by_model_edge"] = {cad: {str(b): _summary(gg) for b, gg in g.groupby(eb[g.index], observed=True)}
                            for cad, g in t.groupby("cadence")}
    # A maker who only keeps fills the model calls favorable (edge ≥ 1¢)
    res["model_filtered_edge_ge_1c"] = {cad: _summary(g[g["edge"] >= 0.01]) for cad, g in t.groupby("cadence")}
    res["model_filtered_edge_lt_0"] = {cad: _summary(g[g["edge"] < 0]) for cad, g in t.groupby("cadence")}

    # Who is on the other side: small (retail-sized) vs large fills, and longshot prices
    sb = pd.cut(t["count"], [0, 10, 100, 1000, np.inf], labels=["≤10", "10–100", "100–1k", ">1k"])
    res["by_fill_size"] = {cad: {str(b): _summary(gg) for b, gg in g.groupby(sb[g.index], observed=True)}
                           for cad, g in t.groupby("cadence")}
    pb = pd.cut(p, [0, 0.1, 0.3, 0.7, 0.9, 1.0], labels=["<10¢", "10–30¢", "30–70¢", "70–90¢", ">90¢"])
    res["by_price"] = {cad: {str(b): _summary(gg) for b, gg in g.groupby(pb[g.index], observed=True)}
                       for cad, g in t.groupby("cadence")}
    tb = {"fifteen_min": [0, 1, 3, 6, 10, 15], "hourly": [0, 5, 15, 30, 60], "daily": [0, 60, 240, 720, 1440]}
    res["by_time_left_min"] = {cad: {str(b): _summary(gg) for b, gg in
                                     g.groupby(pd.cut(g["tau"], tb[cad]).astype(str))}
                               for cad, g in t.groupby("cadence")}
    res["volume_per_event_contracts"] = {cad: float(g.groupby("event_ticker")["count"].sum().mean())
                                         for cad, g in t.groupby("cadence")}
    res["volume_note"] = "mean contracts traded per event within the sampled strikes"
    return res
