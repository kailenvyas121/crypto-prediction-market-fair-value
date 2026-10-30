"""Parquet storage helpers. Jobs write one file per partition (usually a UTC day) so reruns resume."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def part_path(root: Path, key: str) -> Path:
    return root / f"{key}.parquet"


def is_done(root: Path, key: str) -> bool:
    return part_path(root, key).exists()


def write_part(df: pd.DataFrame, root: Path, key: str) -> Path:
    """Atomically write one partition (tmp file + rename), so a killed job never leaves a half file."""
    root.mkdir(parents=True, exist_ok=True)
    path = part_path(root, key)
    tmp = path.with_suffix(".parquet.tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(path)
    return path


def read_parts(root: Path) -> pd.DataFrame:
    files = sorted(root.glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    return pd.concat((pd.read_parquet(f) for f in files), ignore_index=True)


def day_keys(start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    """UTC midnights covering [start, end)."""
    return list(pd.date_range(start.normalize(), end - pd.Timedelta(seconds=1), freq="D", tz="UTC"))
