# pinpricer — Fair Value and Market Making for Crypto Prediction Markets

A research prototype for pricing short-dated crypto event contracts in real time and quoting around that price: Kalshi's BTC 15-minute up/down markets, hourly strike ladders, daily markets and range buckets. Built as a take-home for PinPredict.

> **Thesis.** These contracts are Asian-style digital options on a published index (CF Benchmarks BRTI). A desk's edge is not a directional signal. It comes from pricing at least as accurately as the market (exact settlement mechanics, intraday-seasonal volatility, fat tails), never quoting stale, and running one risk book across every strike and expiry. See [`docs/RESEARCH_OUTLINE.md`](docs/RESEARCH_OUTLINE.md).

## Status
| Stage | State |
|---|---|
| Research and design | done: [`docs/RESEARCH_OUTLINE.md`](docs/RESEARCH_OUTLINE.md) |
| Data pipeline | in progress: [`docs/DATA.md`](docs/DATA.md) |
| Fair-value engine (v0–v4) | planned |
| Calibration study vs Kalshi mid | planned |
| Quoting and risk design | planned |
| Memo | planned |

## Quickstart
```bash
make setup        # create .venv and install the package with dev extras
make data         # pull all raw data (resumable; see docs/DATA.md for sizes and times)
make test         # run the test suite
```
Requires Python ≥ 3.11. No API keys are needed for the historical data.

## Repository layout
```
configs/            date ranges, series and data-source settings (data.yaml)
data/               local data cache (gitignored): raw/ → interim/ → processed/
docs/               research outline, data dictionary, memo
notebooks/          calibration study, ablations, live model-vs-book view
scripts/            thin CLI entry points (pull_*.py)
src/pinpricer/
  data/             resumable, rate-limited clients: Kalshi, spot exchanges, Deribit
tests/              offline unit tests (no network)
```
