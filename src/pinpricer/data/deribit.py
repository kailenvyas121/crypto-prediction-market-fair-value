"""Deribit DVOL (30-day implied-vol index) history. Public API, no key needed."""

from __future__ import annotations

import pandas as pd

from pinpricer.config import RAW_DIR, load_config, study_window
from pinpricer.data import store
from pinpricer.data.http import HttpClient


def dvol_range(http: HttpClient, currency: str, start: pd.Timestamp, end: pd.Timestamp, resolution: int) -> pd.DataFrame:
    """DVOL OHLC bars in [start, end). Follows the `continuation` cursor, which walks backwards from end."""
    rows, t_end = [], int(end.timestamp() * 1000) - 1
    t_start = int(start.timestamp() * 1000)
    while t_end > t_start:
        r = http.get_json("/public/get_volatility_index_data", {
            "currency": currency, "start_timestamp": t_start, "end_timestamp": t_end, "resolution": resolution})["result"]
        rows += r["data"]
        if not r.get("continuation") or r["continuation"] >= t_end:
            break
        t_end = r["continuation"]
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)


def run() -> None:
    cfg = load_config()["deribit"]
    start, end = study_window(with_warmup=True)
    http = HttpClient(cfg["base_url"], rate=cfg["requests_per_second"])
    out = RAW_DIR / "deribit" / f"dvol_{cfg['dvol_currency']}_{cfg['dvol_resolution_seconds']}s"
    months = pd.date_range(start.normalize().replace(day=1), end, freq="MS", tz="UTC")
    for m0 in months:
        key = m0.strftime("%Y-%m")
        if store.is_done(out, key):
            continue
        m1 = min(m0 + pd.offsets.MonthBegin(1), end)
        df = dvol_range(http, cfg["dvol_currency"], max(m0, start), m1, cfg["dvol_resolution_seconds"])
        store.write_part(df, out, key)
        print(f"dvol {key}: {len(df):,} bars")
