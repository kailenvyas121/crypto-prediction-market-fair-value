"""Project paths and config loading."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "configs"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"


@lru_cache
def load_config(name: str = "data") -> dict:
    with open(CONFIG_DIR / f"{name}.yaml") as f:
        return yaml.safe_load(f)


def study_window(cfg: dict | None = None, *, with_warmup: bool = False) -> tuple[pd.Timestamp, pd.Timestamp]:
    """(start, end) of the study as tz-aware UTC timestamps; end is exclusive."""
    s = (cfg or load_config())["study"]
    start = pd.Timestamp(s["start"], tz="UTC")
    end = pd.Timestamp(s["end"], tz="UTC")
    if with_warmup:
        start -= pd.Timedelta(days=s["warmup_days"])
    return start, end
