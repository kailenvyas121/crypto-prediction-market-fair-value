# Data

Every dataset is pulled by `make data` (or the individual `scripts/pull_*.py`) into `data/raw/`. `make results` then runs every study in [`06_RESULTS.md`](06_RESULTS.md). Pulls are resumable: finished partitions are skipped, and long paginations checkpoint their cursor. No API keys are required. The study window and every source setting live in [`configs/data.yaml`](../configs/data.yaml).

**Study window:** contract closes from 2025-11-01 up to 2026-10-28 (exclusive). Spot and vol history starts 35 days earlier as model warm-up.

## Inventory

| Dataset | Path (`data/raw/…`) | Source | Grain | Used for |
|---|---|---|---|---|
| Kalshi 15-min up/down markets | `kalshi/KXBTC15M/markets.parquet` | Kalshi `/historical/markets` + `/markets` | 1 row per contract | Labels (`result`), strike, settlement value |
| Kalshi 15-min candles | `kalshi/KXBTC15M/candles/{day}` | `/historical/markets/{t}/candlesticks`, batch `/markets/candlesticks` | 1 min × contract | Market bid/ask to benchmark against |
| Kalshi hourly/daily ladders | `kalshi/KXBTCD/markets.parquet` | same | 1 row per strike | Labels, strikes, hourly BRTI settlements |
| Kalshi ladder candles | `kalshi/KXBTCD/candles/{day}` | same | 1 min × strike | Market bid/ask, implied vol |
| Coinbase BTC-USD | `spot/coinbase_BTC-USD_1m/{day}` | Coinbase Advanced Trade public candles | 1 min | BRTI proxy (constituent), realized vol |
| Bitstamp BTC/USD | `spot/bitstamp_btcusd_1m/{day}` | Bitstamp OHLC API | 1 min | BRTI proxy (constituent) |
| Binance BTCUSDT spot | `binance/spot_BTCUSDT_1m/{month}` | data.binance.vision | 1 min, with taker-buy volume | Flow features, cross-check |
| Binance BTCUSDT perp | `binance/futures_um_BTCUSDT_1m/{month}` | data.binance.vision | 1 min | Perp lead and basis |
| Binance BTCUSDT spot, 1s | `binance/spot_BTCUSDT_1s/{day}` | data.binance.vision | 1 s, last 60 days | Settlement-minute and in-window studies |
| Binance perp funding | `binance/futures_um_BTCUSDT_fundingRate/{month}` | data.binance.vision | 8 h, published monthly (ends at the last full month) | State variable (vol and jump regime) |
| Deribit DVOL | `deribit/dvol_BTC_3600s/{month}`, `deribit/dvol_BTC_60s/{month}` | Deribit `get_volatility_index_data` | 1 h for the full window; 1 min for the last ~6 months (Deribit's retention) | Implied-vol input |
| Kalshi fill sample | `kalshi/{KXBTC15M,KXBTCD}/trades/{ticker}` | `/historical/trades`, `/markets/trades` | 1 row per fill, with taker side | Maker markout study |
| Binance perp positioning | `binance/futures_um_BTCUSDT_metrics/{day}` | data.binance.vision | 5 min: open interest, long/short ratios, taker buy/sell | Positioning study |
| Binance perp and spot trades | `binance/{futures_um,spot}_BTCUSDT_aggTrades/{day}` | data.binance.vision | every trade, 3 weekdays | Perp lead study |
| Binance ETH, SOL spot | `binance/spot_{ETH,SOL}USDT_1m/{month}` | data.binance.vision | 1 min | BTC-beta study |
| Wikipedia pageviews | `attention/wikipedia_{Bitcoin,Cryptocurrency}` | Wikimedia REST API | daily | Retail-attention proxy |
| Macro calendar | `configs/events.csv` (in git) | federalreserve.gov, bls.gov | event | CPI, payrolls, FOMC variance bumps |

## Schemas

**Kalshi markets**:
- `ticker`, `event_ticker`, `open_time`, `close_time` (UTC)
- `cadence`: fifteen_min, hourly or daily, from trading duration
- `strike_type`: `greater` for ladders, `greater_or_equal` for 15M, where a tie pays YES
- `floor_strike`, `cap_strike`
- `expiration_value`: the official 60-second BRTI average at close
- `result`: yes or no
- `volume`, `open_interest`, `price_level_structure`, `status`

**Kalshi candles**: `ticker`, `ts` (end of the minute, UTC), `yes_bid`, `yes_ask` (end-of-minute quotes, in dollars), `yes_bid_low`, `yes_ask_high`, `last_price`, `vwap`, `volume`, `open_interest`.

**Spot candles**: `ts` (bar open, UTC), `open`, `high`, `low`, `close`, `volume`. Binance adds `quote_volume`, `taker_buy_volume` and `trades`.

## Pulled snapshot (2026-11-05)

| Dataset | Rows | Range | Coverage | Size |
|---|---|---|---|---|
| Kalshi KXBTC15M markets | 30,005 | 2025-12-10 → 2026-10-27 | every listed window | 3 MB |
| Kalshi KXBTCD markets | 1,154,378 strikes / 7,852 events (7,541 hourly, 311 daily) | 2025-11-01 → 2026-10-27 | every listed event | 28 MB |
| Kalshi KXBTC15M candles | 447,675 contract-minutes | 2025-12-10 → 2026-10-27 | 29,901 of 30,005 contracts (99.7%) | 16 MB |
| Kalshi KXBTCD candles | 15,850,060 strike-minutes | 2025-11-01 → 2026-10-27 | 143,206 of 143,304 selected strikes (99.9%) | 107 MB |
| Coinbase BTC-USD 1m | 569,408 | 2025-09-27 → 2026-10-27 | 99.9% | 24 MB |
| Bitstamp BTC/USD 1m | 570,240 | 2025-09-27 → 2026-10-27 | 100% | 21 MB |
| Binance spot / perp 1m | 607,680 each | 2025-09-01 → 2026-10-27 | 100% | 66 MB |
| Binance spot 1s | 5,184,000 | 2026-08-29 → 2026-10-27 | 100% | 161 MB |
| Binance funding | 1,185 | 2025-09-01 → 2026-09-30 | 100% | <1 MB |
| Deribit DVOL 1h / 1m | 9,504 / 263,298 | 2025-09-27 / 2026-04-27 → 2026-10-27 | 99.9% | 4 MB |
| Kalshi fill sample (used by the study) | 5,380,621 (KXBTC15M, 250 windows) + 2,181,604 (KXBTCD, 1,171 strikes in 140 events, chosen from the price at each event's open) | 2026-05-01 → 2026-10-27 | every fill in sampled markets | ~75 MB |
| Binance perp metrics (5 min) | 114,048 | 2025-09-27 → 2026-10-27 | 100% | 9 MB |
| Binance ETH, SOL 1m | 613,440 each | 2025-09-01 → 2026-10-31 | 100% | 65 MB |
| Binance perp + spot trades | 4,293,905 (perp) and spot equivalent | 2026-10-14 → 2026-10-16 | 3 weekdays | 50 MB |
| Wikipedia pageviews | 397 days × 2 articles | 2025-09-27 → 2026-10-28 | 100% | <1 MB |

**First data-quality check: the USD proxy vs the official settlement.** We compare each source's last 1-minute close before every hourly close with Kalshi's 60-second BRTI settlement, over n = 7,816 hours:

| Source | Median diff | Median abs diff | p95 abs diff |
|---|---|---|---|
| Coinbase | −0.57 bp | 1.40 bp | 6.2 bp |
| Bitstamp | −0.45 bp | 1.09 bp | 5.6 bp |
| Median(Coinbase, Bitstamp) | −0.52 bp | 1.18 bp | 5.8 bp |
| Binance BTCUSDT | **+4.94 bp** | 5.50 bp | 15.0 bp |

The free USD composite tracks the settlement index to about a basis point. Binance's USDT price carries a ~5 bp basis, which is why it serves only as a lead and flow feature, never as the pricing reference.

## Choices and caveats

- **Settlement labels are exact.** `expiration_value` is Kalshi's own 60-second BRTI average, so labels need no reconstruction. Verified on 27,093 consecutive 15M windows: each window's strike equals the previous window's `expiration_value` to the cent.
- **The hourly settlement series is a free, exact BRTI sample.** One `expiration_value` per hour, used to measure the basis of the Coinbase/Bitstamp proxy.
- **Ladder strike selection has no look-ahead.** For candles, we keep strikes within ±1.5%·√(hours open), capped at 6%, of the **last hourly settlement known when the event opened**. That is about ±3σ of an hour's move. Strikes outside it trade at 0 or 1 and carry no information.
- **BRTI itself is licensed.** Real-time and intra-minute BRTI is available through Kalshi's `cfbenchmarks_value` stream with an API key (entitlement still to be confirmed). Until then, the USD proxy is a composite of BRTI constituents (Coinbase and Bitstamp). Binance is **not** a constituent and is USDT-quoted. It is used only for lead and flow features.
- **Rate limits.** Kalshi allows about 5 req/s unauthenticated. Setting `KALSHI_API_KEY_ID` and `KALSHI_PRIVATE_KEY_PATH` signs requests and raises the cap to the account tier (about 20 req/s), which shortens the candle pulls about 4×.
- **Coverage gaps.** KXBTC15M starts 2025-12-10 (series launch). No contracts expire during the Thursday 3–5 AM ET maintenance pause. Kalshi's historical archive covers contracts settled before its cutoff (currently 2026-08-31); later contracts come from the live endpoints.
