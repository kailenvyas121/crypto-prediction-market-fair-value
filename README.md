# Crypto Prediction Markets: Fair Value and Market Making

[![ci](https://github.com/kailenvyas121/crypto-prediction-market-fair-value/actions/workflows/ci.yml/badge.svg)](https://github.com/kailenvyas121/crypto-prediction-market-fair-value/actions/workflows/ci.yml)

How to price crypto event contracts on Kalshi and Polymarket (15-minute up/down, hourly and daily strike ladders, range buckets, long-dated and touch markets) and how to make markets in them. The repo has three parts:
- a plain-language framework
- a working pricing model
- tests against a year of Kalshi data: settled outcomes, Kalshi's own quotes and 7.6 million real fills

By Kailen Vyas.

## The idea in one paragraph

A crypto prediction contract is a **digital option on a published index**. Its fair value is the probability that the settlement value lands on the paying side. That probability comes from three things: the distance to the strike, how far the index can move before settlement (volatility × √time, adjusted for averaged settlement), and how fat the tails are. Bitcoin has no cash flows, so over minutes to days every input that matters is public market data, which makes this a numbers problem. The edge is not predicting direction. It is pricing about as accurately as the market, never being stale, and collecting the spread and the crowd's longshot premium.

## Results at a glance

Accuracy tests are out of sample: fit before May 2026, scored May–October 2026. Descriptive studies (crowd error, the open-interest "story", implied-vs-realized volatility) use the full sample and are labeled that way. Intervals resample whole days or weeks. Details in [`docs/06_RESULTS.md`](docs/06_RESULTS.md).

| Question | Answer |
|---|---|
| Does the model beat the common public approaches? | **Yes, at every tenor.** Options-implied (DVOL Black-Scholes) and naive Binance-price models both lose, with 95% intervals excluding zero. The naive Binance model misses the 15-minute market by 21¢ because it prices the wrong index |
| How close is it to Kalshi's own prices? | **Hourly:** within 0.3 thousandths of Brier, statistically slightly behind. **Daily:** slightly ahead, not significant (104 events). **15-minute:** behind, a 4.3¢ average gap that one-minute data from two exchanges cannot close |
| Do market makers make money on these contracts? | **Yes.** Makers earn +0.48¢ (15-min), +0.74¢ (hourly) and +0.83¢ (daily) per contract at settlement, all with intervals excluding zero |
| Does the model help a maker? | **On hourly, yes.** Fills it rates favorable earn **+1.82¢** per contract (0.29 to 3.36), about 2.5× the average. On 15-minute the direction is the same but not significant |
| Do open interest, funding or long/short ratios predict BTC? | **No.** Out-of-sample R² is below zero at 1h, 4h and 24h, and they add nothing to the volatility forecast. They describe risk; they don't forecast it |
| Does sentiment help? | **As defense and as crowd error, not as direction.** Cheap contracts are overpriced by about 2¢ on both sides (6,475 events, 44 weeks). X-driven news defense protects quotes. Retail attention didn't forecast volatility or returns |
| What matters most in the model? | A realized-volatility forecast, then the right index (mainly for 15-minute contracts), then fat tails. Time-of-day volatility helps hourly and daily. Settlement averaging matters in the final minutes |

## Read in this order

| | Document | For |
|---|---|---|
| 1 | [`docs/01_PRICING_GUIDE.md`](docs/01_PRICING_GUIDE.md) | **Start here.** Pricing from zero: what the contracts are, why crypto suits quantitative pricing, the step-by-step recipe, worked examples, tenors, venues, long-dated and touch markets, comparison with other approaches |
| 2 | [`docs/02_MARKET_SIGNALS.md`](docs/02_MARKET_SIGNALS.md) | Every spot and derivatives metric (perps, basis, funding, open interest and the "OI story", liquidations, options, BTC beta): what each tells you and what our data says |
| 3 | [`docs/03_SENTIMENT_AND_NEWS.md`](docs/03_SENTIMENT_AND_NEWS.md) | X as crypto's newswire, news defense, the crowd-error edge in longer-dated markets, what didn't work |
| 4 | [`docs/04_MARKET_MAKING.md`](docs/04_MARKET_MAKING.md) | Maker economics from real fills, quoting rules, risk, liquidity-provider programs |
| 5 | [`docs/05_SYSTEM_ROADMAP.md`](docs/05_SYSTEM_ROADMAP.md) | How the live system works (one loop at three speeds), data and tools, phased build with gates |
| 6 | [`docs/06_RESULTS.md`](docs/06_RESULTS.md) | Every test: method, numbers, limits, what is not tested yet |
| – | [`docs/memo.html`](docs/memo.html) | A memo version with flowcharts |
| – | [`docs/GLOSSARY.md`](docs/GLOSSARY.md) · [`docs/DATA.md`](docs/DATA.md) | Terms; data inventory and schemas |

## Reproduce

```bash
make setup     # create .venv and install (Python ≥ 3.11)
make data      # pull all public data (resumable; several hours unauthenticated, see docs/DATA.md)
make results   # run every study → docs/results/*.json
make check     # lint + tests (no network or data needed)
```

No API keys are needed. Setting `KALSHI_API_KEY_ID` and `KALSHI_PRIVATE_KEY_PATH` makes the Kalshi pulls about 4× faster.

## Repository layout

```
configs/            study window, data sources, fill sample, macro release calendar
docs/               the framework (01–06), glossary, data dictionary, memo, results/*.json
scripts/            pull_*.py (data), run_studies.py (all studies)
src/pinpricer/
  data/             resumable, rate-limited clients: Kalshi, Coinbase, Bitstamp, Binance, Deribit, Wikipedia
  model/            variance forecast (vol.py) and digital pricing on averaged settlement (fv.py)
  research/         one module per study: proxy, calibration, index_gap, lead, positioning, beta, events, sentiment, markouts
tests/              offline tests: pricing invariants, parsers, sign conventions
```

## Evidence standard

Every number in the docs is tagged **[Tested]** (produced by `make results`), **[Source]** (rulebooks, venue documentation and papers, fact-checked 4 Nov 2026) or **[Judgment]**. Known limits are listed in [`docs/06_RESULTS.md`](docs/06_RESULTS.md) §6.10. The two main ones: the 15-minute test used one-minute data from two exchanges rather than sub-second data from all seven, and maker P&L is measured on fills that happened rather than on a queue-position replay.
