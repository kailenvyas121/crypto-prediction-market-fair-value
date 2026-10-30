"""Pull raw Kalshi data (markets → candles) into data/raw/kalshi/. Resumable.

    python scripts/pull_kalshi.py                       # all configured series, all stages
    python scripts/pull_kalshi.py --series KXBTC15M --stages markets
"""

import argparse

from pinpricer.data import kalshi

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--series", nargs="*", help="series tickers (default: all in configs/data.yaml)")
    p.add_argument("--stages", nargs="*", default=["markets", "candles"],
                   choices=["markets", "candles"])
    a = p.parse_args()
    kalshi.run(a.series, stages=a.stages)
