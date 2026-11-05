"""Calibration study: score each fair-value layer against Kalshi outcomes and the Kalshi mid.

Train (vol weights, seasonal profile, tail ν, blend weight): contracts closing before TRAIN_END.
Test: contracts closing on or after it. Every row is one contract-minute with a two-sided Kalshi
quote; the model sees only data up to that minute.

    python scripts/run_studies.py calibration      # writes docs/results/calibration.json
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pinpricer.config import RAW_DIR
from pinpricer.data import store
from pinpricer.model import fv
from pinpricer.model.vol import VolModel, proxy_minutes

TRAIN_END = pd.Timestamp("2026-05-01", tz="UTC")
LADDER_EVERY_MIN = 5          # subsample ladder minutes (15.9M rows → ~3M)
MAX_SPREAD = 0.10
RNG = np.random.default_rng(0)

MODELS = {  # name: (vol forecaster, tails, settlement averaging)
    "baseline: options-implied (DVOL Black-Scholes digital)": ("dvol", False, False),
    "v0 flat vol, normal": ("flat", False, True),
    "v1 EWMA vol, normal": ("ewma", False, True),
    "v2 HAR + seasonal, normal": ("har", False, True),
    "v3 v2 + DVOL, normal": ("har_iv", False, True),
    "v4 v3 + Student-t tails": ("har_iv", True, True),
    "v4 without averaging adj.": ("har_iv", True, False),
}
BEST = "v4 v3 + Student-t tails"
OPTIONS = "baseline: options-implied (DVOL Black-Scholes digital)"
BINANCE = "baseline: Binance price, EWMA vol, normal"
BINANCE_BC = "variant: Binance price minus trailing USDT basis, v4 model"


def load_rows(series: str, px: pd.Series) -> pd.DataFrame:
    m = pd.read_parquet(RAW_DIR / "kalshi" / series / "markets.parquet",
                        columns=["ticker", "event_ticker", "close_time", "floor_strike", "result", "cadence"])
    c = store.read_parts(RAW_DIR / "kalshi" / series / "candles")[["ticker", "ts", "yes_bid", "yes_ask"]]
    if series == "KXBTCD":
        c = c[c["ts"].dt.minute % LADDER_EVERY_MIN == 0]
    d = c.merge(m.dropna(subset=["floor_strike"]), on="ticker")
    d = d[d["cadence"].isin(["fifteen_min", "hourly", "daily"]) & d["result"].isin(["yes", "no"])]
    d["tau"] = ((d["close_time"] - d["ts"]).dt.total_seconds() // 60).astype(int)
    pos = px.index.get_indexer(d["ts"])
    d = d[(d["tau"] >= 1) & (pos >= 0)].copy()
    d["t_pos"] = px.index.get_indexer(d["ts"])
    d["spot"] = px.to_numpy()[d["t_pos"]]
    d["y"] = (d["result"] == "yes").astype(float)
    d["mid"] = (d["yes_bid"] + d["yes_ask"]) / 2
    d["quoted"] = (d["yes_bid"] >= 0.01) & (d["yes_ask"] <= 0.99) & (d["yes_ask"] - d["yes_bid"] <= MAX_SPREAD)
    d["train"] = d["close_time"] < TRAIN_END
    return d.reset_index(drop=True)


def price(d: pd.DataFrame, vm: VolModel, kind: str, tails: bool, averaging: bool, nu: dict, scale=1.0):
    t_pos, tau = d["t_pos"].to_numpy(), d["tau"].to_numpy()
    v_tot, v_last = vm.window_variance(t_pos, tau, kind)
    var = fv.averaged_variance(v_tot, v_last, averaging) * scale**2
    nus = np.where(tau <= 30, nu["15m"], nu["60m"]) if tails else None
    return fv.prob_above(d["spot"].to_numpy(), d["floor_strike"].to_numpy(), var, nus), var


def fit_basis(px: pd.Series) -> float:
    """Median log gap between Kalshi's BRTI settlements and the proxy at the same minute, train only."""
    gaps = []
    for series in ("KXBTC15M", "KXBTCD"):
        m = pd.read_parquet(RAW_DIR / "kalshi" / series / "markets.parquet",
                            columns=["event_ticker", "close_time", "expiration_value"])
        m = m.dropna().drop_duplicates("event_ticker")
        m = m[m["close_time"] < TRAIN_END]
        gaps.append(np.log(m["expiration_value"].to_numpy() / px.reindex(m["close_time"]).to_numpy()))
    return float(np.nanmedian(np.concatenate(gaps)))


def fit_tails(px: pd.Series, vm: VolModel) -> dict:
    """ν of the unit-variance t on train returns standardized by the v3 forecast, non-overlapping."""
    lp = np.log(px.to_numpy())
    out, kurt = {}, {}
    for name, h in (("15m", 15), ("60m", 60)):
        pos = np.arange(10080, np.searchsorted(px.index, TRAIN_END) - h, h)
        v, _ = vm.window_variance(pos, np.full(len(pos), h), "har_iv")
        z = (lp[pos + h] - lp[pos]) / np.sqrt(v)
        z = z[np.isfinite(z)]
        out[name] = fv.fit_student_t_nu(z)
        kurt[name] = float(pd.Series(z).kurt())
    return {"nu": out, "excess_kurtosis_standardized": kurt}


def brier(p, y):
    return float(np.mean((p - y) ** 2))


def logloss(p, y):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def day_bootstrap(d: pd.DataFrame, a: str, b: str, n=2000) -> tuple[float, float]:
    """95% CI of Brier(a) − Brier(b), resampling whole UTC days of contract closes.

    Days, not events, are the resampling unit: hourly and 15-minute contracts closing on the same
    day share one BTC price path, so treating them as independent would make intervals too narrow.
    """
    day = d["close_time"].dt.floor("D")
    g = d.assign(da=(d[a] - d["y"]) ** 2 - (d[b] - d["y"]) ** 2, day=day).groupby("day")["da"].agg(["sum", "count"])
    s, c = g["sum"].to_numpy(), g["count"].to_numpy()
    idx = RNG.integers(0, len(g), size=(n, len(g)))
    stats_ = s[idx].sum(1) / c[idx].sum(1)
    return float(np.percentile(stats_, 2.5)), float(np.percentile(stats_, 97.5))


def tau_bucket(cadence: str, tau: pd.Series) -> pd.Series:
    edges = {"fifteen_min": [0, 1, 3, 6, 10, 15], "hourly": [0, 2, 5, 15, 30, 60],
             "daily": [0, 60, 240, 720, 1440]}[cadence]
    return pd.cut(tau, edges, right=True).astype(str)


def run() -> dict:
    px = proxy_minutes()
    vm = VolModel(px, TRAIN_END)
    tails = fit_tails(px, vm)
    basis = fit_basis(px)
    nu = tails["nu"]
    res: dict = {"train_end": str(TRAIN_END.date()), "basis_bp": 1e4 * basis, "vol_weights": vm.weights().round(4).to_dict("index"),
                 "tails": tails, "season_profile_et": {}}
    prof = pd.Series(vm.season, index=pd.MultiIndex.from_product([range(7), range(48)]))
    res["season_profile_et"] = {
        "weekday_by_hour": prof.loc[0:4].groupby(level=1).mean().groupby(lambda i: i // 2).mean().round(2).tolist(),
        "weekend_mean": round(float(prof.loc[5:6].mean()), 2), "weekday_mean": round(float(prof.loc[0:4].mean()), 2)}

    rows = pd.concat([load_rows("KXBTC15M", px), load_rows("KXBTCD", px)], ignore_index=True)
    rows["spot_raw"] = rows["spot"]
    rows["spot"] = rows["spot_raw"] * np.exp(basis)  # proxy → BRTI level
    rows["v4 without basis adj."], _ = price(rows.assign(spot=rows["spot_raw"]), vm, "har_iv", True, True, nu)
    # A common bot setup: price off Binance BTC/USDT (not the settlement index), EWMA vol, normal, point settlement
    bn = store.read_parts(RAW_DIR / "binance" / "spot_BTCUSDT_1m").set_index("ts")["close"]
    bn = bn[~bn.index.duplicated()].sort_index()
    bn.index = bn.index + pd.Timedelta(minutes=1)  # keyed by bar end, like the proxy
    bn_px = bn.reindex(px.index).ffill()
    rows[BINANCE], _ = price(rows.assign(spot=bn_px.to_numpy()[rows["t_pos"]]), vm, "ewma", False, False, nu)
    # Fairer Binance version: remove a trailing 24h median USDT basis, then the full v4 model
    gap = np.log(bn_px / px).rolling(1440, min_periods=720).median().to_numpy()
    spot_bc = bn_px.to_numpy()[rows["t_pos"]] * np.exp(-gap[rows["t_pos"]] + basis)
    rows[BINANCE_BC], _ = price(rows.assign(spot=spot_bc), vm, "har_iv", True, True, nu)
    for name, (kind, t, avg) in MODELS.items():
        rows[name], var = price(rows, vm, kind, t, avg, nu)
        if name == BEST:
            rows["z"] = np.log(rows["floor_strike"] / rows["spot"]) / np.sqrt(var)

    q = rows[rows["quoted"]]
    test, train = q[~q["train"]], q[q["train"]]
    res["rows"] = {c: {"train": int((train.cadence == c).sum()), "test": int((test.cadence == c).sum()),
                       "test_events": int(test[test.cadence == c].event_ticker.nunique())}
                   for c in ["fifteen_min", "hourly", "daily"]}

    cols = [BINANCE, BINANCE_BC, *MODELS, "v4 without basis adj.", "mid"]
    res["overall"], res["by_tau"], res["by_distance"], res["vs_mid"], res["blend"], res["vol_scale"] = {}, {}, {}, {}, {}, {}
    for cad in ["fifteen_min", "hourly", "daily"]:
        d = test[test.cadence == cad]
        res["overall"][cad] = {c: {"brier": brier(d[c], d.y), "logloss": logloss(d[c], d.y),
                                   "mae_vs_mid_cents": float(100 * np.mean(np.abs(d[c] - d["mid"])))} for c in cols}
        res["vs_mid"][cad] = {"brier_best_minus_mid": brier(d[BEST], d.y) - brier(d["mid"], d.y),
                              "ci95": day_bootstrap(d, BEST, "mid")}
        res.setdefault("vs_baselines", {})[cad] = {
            b: {"brier_best_minus_baseline": brier(d[BEST], d.y) - brier(d[b], d.y), "ci95": day_bootstrap(d, BEST, b)}
            for b in (BINANCE, BINANCE_BC, OPTIONS)}
        bt = tau_bucket(cad, d["tau"])
        res["by_tau"][cad] = {b: {"n": len(g), "model": brier(g[BEST], g.y), "mid": brier(g["mid"], g.y),
                                  "mae_cents": float(100 * np.mean(np.abs(g[BEST] - g["mid"]))),
                                  "no_avg_mae_cents": float(100 * np.mean(np.abs(g["v4 without averaging adj."] - g["mid"])))}
                              for b, g in d.groupby(bt)}
        dz = pd.cut(d["z"].abs(), [0, 0.5, 1.0, 1.5, 2.5, np.inf]).astype(str)
        res["by_distance"][cad] = {
            b: {"n": len(g), "normal_minus_mid_cents": float(100 * np.mean(g["v3 v2 + DVOL, normal"] - g["mid"])),
                "t_minus_mid_cents": float(100 * np.mean(g[BEST] - g["mid"])),
                "brier_normal": brier(g["v3 v2 + DVOL, normal"], g.y), "brier_t": brier(g[BEST], g.y),
                "brier_mid": brier(g["mid"], g.y)}
            for b, g in d.groupby(dz)}
        # Blend weight fit on train only: y − mid = w (model − mid)
        tr = train[train.cadence == cad]
        x, yy = (tr[BEST] - tr["mid"]).to_numpy(), (tr.y - tr["mid"]).to_numpy()
        w = float(x @ yy / (x @ x))
        blend = np.clip(d["mid"] + w * (d[BEST] - d["mid"]), 0, 1)
        res["blend"][cad] = {"w_model": w, "brier_blend": brier(blend, d.y), "brier_mid": brier(d["mid"], d.y),
                             "ci95_blend_minus_mid": day_bootstrap(d.assign(blend=blend), "blend", "mid")}
        # vol scale the market implies vs what outcomes reward
        s = d.sample(min(len(d), 300_000), random_state=0)
        grid = np.round(np.arange(0.6, 1.61, 0.02), 2)
        fit_mid, fit_y = [], []
        for c in grid:
            p, _ = price(s, vm, "har_iv", True, True, nu, scale=c)
            fit_mid.append(np.mean((p - s["mid"]) ** 2))
            fit_y.append(brier(p, s.y))
        res["vol_scale"][cad] = {"market_implied": float(grid[np.argmin(fit_mid)]),
                                 "outcome_optimal": float(grid[np.argmin(fit_y)])}

    # Folded distance check: model − mid on the contract's far side (P < 0.5 by the model)
    far = test[test[BEST] < 0.5]
    zb = pd.cut(far["z"].abs(), [0, 0.5, 1.0, 1.5, 2.5, np.inf]).astype(str)
    res["far_side_cents"] = {b: {"n": len(g), "normal_minus_mid": float(100 * np.mean(g["v3 v2 + DVOL, normal"] - g["mid"])),
                                 "t_minus_mid": float(100 * np.mean(g[BEST] - g["mid"])),
                                 "realized_minus_mid": float(100 * np.mean(g.y - g["mid"]))}
                             for b, g in far.groupby(zb)}

    return res
