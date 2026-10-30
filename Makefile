PY := .venv/bin/python

.PHONY: setup data data-kalshi data-spot data-deribit test lint

setup:
	python3 -m venv .venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -e ".[dev]"

data: data-spot data-deribit data-kalshi

data-kalshi:
	$(PY) scripts/pull_kalshi.py

data-spot:
	$(PY) scripts/pull_spot.py

data-deribit:
	$(PY) scripts/pull_deribit.py

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check src tests scripts
