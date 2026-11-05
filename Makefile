PY := .venv/bin/python

.PHONY: setup data data-kalshi data-trades data-spot data-deribit results test lint check

setup:
	python3 -m venv .venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -e ".[dev]"

data: data-spot data-deribit data-kalshi data-trades

data-kalshi:
	$(PY) scripts/pull_kalshi.py --stages markets candles

data-trades:
	$(PY) scripts/pull_kalshi.py --stages trades

data-spot:
	$(PY) scripts/pull_spot.py

data-deribit:
	$(PY) scripts/pull_deribit.py

results:
	$(PY) scripts/run_studies.py

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check src tests scripts

check: lint test
