# 6. Results: Every Test, Its Method and Its Limits

Every number in the other documents comes from one of the studies below. Each study is one module in `src/pinpricer/research/`. `make results` reruns them all and writes `docs/results/<study>.json`.

**Common rules:**
- **Train / test split.** Anything fitted (volatility weights, time-of-week profile, tail parameter, index offset, blend weights, event bumps) uses data **before 1 May 2026**. Scores use data **from 1 May 2026 to 27 Oct 2026**, which the model never saw.
- **No look-ahead.** At each minute the model sees only data up to that minute. Positioning snapshots are used only from 5 minutes after their timestamp.
- **The expiry is the statistical unit.** Confidence intervals resample whole events, because minutes and fills within one contract are correlated.
- **Index proxy.** Spot is the median of Coinbase and Bitstamp one-minute closes (both BRTI constituents), raised by a +0.38 bp offset fit on training settlements.

---

## 6.1 Calibration: model vs outcomes vs the Kalshi mid (`calibration`)

**Rows:** each contract-minute with a real two-sided Kalshi quote (bid ≥ 1¢, ask ≤ 99¢, spread ≤ 10¢). Ladder minutes are sampled every 5 minutes.

| Test set | Contract-minutes | Events |
|---|---|---|
| 15-minute | 144,255 | 11,517 |
| Hourly | 257,581 | 2,737 |
| Daily | 534,324 | 104 |

**Brier score (lower is better):**

| Model | 15-minute | Hourly | Daily |
|---|---|---|---|
| Baseline: Binance price, recent vol, normal | 0.2447 | 0.1042 | 0.0949 |
| Baseline: options-implied (DVOL Black-Scholes digital) | 0.1757 | 0.0995 | 0.0963 |
| v0 flat 30-day vol, normal | 0.1737 | 0.0992 | 0.0964 |
| v1 EWMA realized vol | 0.1664 | 0.0940 | 0.0948 |
| v2 HAR + time of week | 0.1668 | 0.0937 | 0.0947 |
| v3 + DVOL | 0.1664 | 0.0933 | 0.0939 |
| **v4 + Student-t tails** | **0.1653** | **0.0923** | **0.0925** |
| Kalshi mid | 0.1622 | 0.0920 | 0.0930 |

**Average gap to the Kalshi mid:**

| | 15-minute | Hourly | Daily |
|---|---|---|---|
| v4 | 4.3¢ | 2.2¢ | 1.9¢ |
| Options-implied baseline | 8.4¢ | 6.1¢ | 3.6¢ |
| Binance baseline | 20.9¢ | 6.5¢ | 4.0¢ |

**v4 compared with the alternatives** (Brier difference × 1000, 95% CI by event):

| | 15-minute | Hourly | Daily |
|---|---|---|---|
| v4 − Kalshi mid | +3.0 (+2.4, +3.7) | +0.3 (+0.1, +0.6) | −0.5 (−1.2, +0.1) |
| v4 − options-implied baseline | −10.4 (−11.4, −9.5) | −7.2 (−7.8, −6.5) | −3.8 (−5.8, −1.9) |
| v4 − Binance baseline | −79.5 (−84.4, −74.8) | −11.9 (−13.2, −10.6) | −2.5 (−4.1, −0.7) |

**Blend.** The weight on v4 in mid + w·(v4 − mid) is fit on training data and applied out of sample:

| | Weight on model | Blend Brier | Mid Brier |
|---|---|---|---|
| 15-minute | 0.26 | 0.16232 | 0.16221 |
| Hourly | 0.51 | 0.09191 | 0.09200 |
| Daily | 0.80 | 0.09246 | 0.09300 |

On hourly and daily the blend beats the mid, so the model carries information the book does not.

**Other measurements:**
- **Settlement averaging.** Average gap to mid on 15-minute contracts falls from 13.3¢ to 8.8¢ in the final minute and from 6.6¢ to 5.3¢ with 1–3 minutes left. No effect beyond ~10 minutes.
- **Fat tails.** On cheap contracts 0.5–1.5σ out of the money:
  - Kalshi mid vs what they paid: overpriced by 2.2–2.3¢.
  - Normal model vs the mid: 2.0–3.2¢ *above* it.
  - t-model vs the mid: 0.8–1.4¢ *below* it.
- **Implied vs realized volatility.** The vol multiple of our forecast that best fits the mid is 1.02 / 1.00 / 1.06 (15-min / hourly / daily). The multiple that best fits outcomes is 0.96 / 0.96 / 0.92. The book carries a small volatility premium.
- **Fitted parameters.**
  - ν = 4.5 (15-minute) and 4.2 (1-hour). Standardized excess kurtosis is 9.7 and 8.6.
  - Variance-forecast elasticities: next hour 0.52 / 0.35 / 0.01 / 0.30 (RV 1h / 24h / 7d / DVOL²); next 24h 0.17 / 0.38 / 0.14 / 0.40.
  - Weekday time-of-week variance multipliers: 0.55–0.73 overnight ET; 2.6 at 9–10 AM; 3.0 at 10–11 AM. Weekends 0.67.

**Limits:**
- Kalshi one-minute candles are end-of-minute quotes, not executable fills.
- The proxy is not the licensed index.
- The daily result rests on 104 events.

---

## 6.2 Why 15-minute trails (`index_gap`)

Each quote is inverted for the index level the market must be using, holding our variance and tails fixed. The gap is ln(implied / proxy).

| | 15-minute | Hourly |
|---|---|---|
| Median absolute gap | 0.92 bp | 1.67 bp |
| 90th percentile | 2.8 bp | 6.1 bp |
| Gap growth per 1σ of strike distance | 1.6 bp | 2.6 bp |

**Same minute, two markets (13,376 minutes):**
- The 15-minute gap and the hourly ladder's gap correlate at 0.34.
- Repricing 15-minute contracts on the ladder-implied index level cuts the average gap to mid from 4.45¢ to 4.21¢, but does not improve Brier.

**Reading:**
- Part of the gap is index measurement. Its size matches the proxy's known error, and two separate markets agree on it.
- Part is volatility. The gap grows with strike distance, which is what a faster volatility read would produce.
- Sub-second index replication is necessary for 15-minute markets, and a second-by-second volatility read is the other half.

---

## 6.3 Perp lead (`lead`)

Binance BTC perp vs Binance spot, 100 ms last-trade returns, 2026-10-14 to 10-16.

| Lag | Correlation |
|---|---|
| Perp leads by 100 ms | 0.18 |
| Same 100 ms | 0.62 |
| Spot leads by 100 ms | 0.09 |
| Perp leads by 200 ms / 300 ms | 0.08 / 0.07 |

- 69% of the lead-lag correlation is on the perp-first side.
- The last second of perp-minus-spot movement explains 1.7% of the next second of spot.

**Limits:** three days, and Binance spot only. The lead over USD exchanges (the BRTI constituents) needs synchronized sub-second data from those venues.

---

## 6.4 Perp positioning (`positioning`)

Hourly data, train before May 2026 (4,991 hours), test May–Sep 2026 (4,269 hours; funding data ends 30 Sep).

| Question | Result |
|---|---|
| Direction, all positioning signals (OI change, OI level, funding, basis, top-trader and account long/short, taker ratio, past returns) | Out-of-sample R² −0.4% (1h), −2.0% (4h), −10.8% (24h) |
| Best single signal for the next hour (OI change) | R² +0.05%, correlation 0.03 |
| Volatility: base forecast (HAR + time of week + DVOL) | Out-of-sample R² 0.63 on next-hour log variance |
| Volatility: positioning added to the base forecast's error | Out-of-sample R² −0.04 (no help) |
| Tails, most vs least crowded long third (4-hour moves beyond 2σ) | Down: 1.7% vs 2.5%. Up: 3.0% vs 1.7% |
| OI story quadrants, next 4 hours | Largest \|t\| = 1.35; none significant |
| Liquidation-like hours (OI −2%, price ±1%; n = 77) | Next 4h after a down-flush +16 bp (t = 0.96) |

**Case: 10–11 Oct 2025.** Before the cascade, OI was +0.8σ vs its 30-day mean and funding was 0.4 bp. In the crash hour (21:00–22:00 UTC), realized volatility was 334 bp vs a 119 bp forecast. OI fell 18.6% that hour and 37.7% over 24 hours. BTC was down about 9% over the day.

**Methodology note:** with snapshots used at their own timestamp, OI change appeared to predict the next hour (R² 0.9%). Using each snapshot only from 5 minutes after its timestamp removed the effect.

---

## 6.5 BTC beta (`beta`)

Binance USDT spot, Nov 2025–Oct 2026.

| | β (1m / 1h / 1d) | R² (1m / 1h / 1d) | β in BTC's top 1% hours | Same direction in those hours | Annualized vol |
|---|---|---|---|---|---|
| ETH | 1.17 / 1.21 / 1.26 | 0.74 / 0.79 / 0.82 | 1.20 | 100% | 61% |
| SOL | 1.24 / 1.26 / 1.26 | 0.65 / 0.70 / 0.76 | 1.21 | 100% | 68% |
| BTC | 1 | 1 | 1 | – | 45% |

---

## 6.6 Macro releases (`events`)

Releases from `configs/events.csv`, verified against federalreserve.gov and bls.gov schedules, including shutdown-delayed dates: 11 CPI, 12 payrolls, 8 FOMC. Realized variance after each release is compared with the forecast made one minute before. That ratio is then divided by the same ratio at the same weekday and time on non-release days (±1 and ±2 weeks), because the time-of-week profile already averages some release days in.

| | First 5 minutes | First hour | Minutes 5–60 |
|---|---|---|---|
| CPI | 21.5× | 4.2× | 1.1× |
| FOMC | 21.2× | 6.6× | 4.3× |
| Payrolls | 7.6× | 3.3× | 1.8× |
| Pooled, fit on 16 training releases | 7.5× | – | 2.1× |

**Applying the pooled bump** to test-period hourly contracts whose remaining window spans a release (2,036 contract-minutes, 18 event-hours):

| | Brier |
|---|---|
| v4 | 0.1275 |
| v4 + bump | 0.1265 |
| Mid | 0.1275 |

- Bump − mid: 95% CI −7.2 to +4.6 (× 1000).
- The direction is right, but there are too few releases to call it significant.

---

## 6.7 Attention and crowd error (`sentiment`)

**Attention proxy:** daily English-Wikipedia pageviews of "Bitcoin", as a shock vs the trailing 30 days.

| Test (out of sample) | Result |
|---|---|
| Next-day realized volatility | R² 0.487 (daily HAR) vs 0.464 (+ attention) |
| Next 7-day return | R² 1.0%, correlation −0.12 (overlapping windows) |

**Crowd error:** mid − outcome on cheap contracts (model and mid both under 30% for that side), Kalshi hourly and daily ladders, full period. 6,470 events.

| | Overpriced by | 95% CI |
|---|---|---|
| Upside longshots | 2.0¢ | 0.6 to 3.3 |
| Downside longshots | 1.9¢ | 0.5 to 3.2 |
| Downside, after BTC's strongest 7-day third | 3.6¢ | 2.0 to 5.1 |
| Downside, after BTC's weakest 7-day third | −0.2¢ | −3.5 to 2.7 |
| Downside, highest attention third | 0.0¢ | −3.0 to 2.6 |
| Downside, lowest attention third | 3.1¢ | 1.4 to 4.7 |

The split by sentiment is descriptive: the groups were cut on the full sample, and the extreme groups' intervals overlap.

---

## 6.8 Maker markouts (`markouts`)

Sample: random test-period events from `configs/data.yaml` (`kalshi.trades_sample`): 250 fifteen-minute windows, 120 hourly events, 20 daily events. Ladder strikes are those within ±1% of settlement; strike selection uses the outcome only to bound the download, and every quantity below conditions on information at the fill. 7.8M fills, each with price, size and taker side.

Per contract, maker side: settlement P&L s·(p − Y); spread capture s·(p − mid) against the prior minute's mid; one- and five-minute markouts s·(p − mid_{t+k}); model edge s·(p − FV). Makers pay no fee on these series.

| | 15-minute | Hourly | Daily |
|---|---|---|---|
| Contracts | 405M | 181M | 41M |
| Maker settlement P&L | 0.48¢ (0.17 to 0.78) | 0.61¢ (0.17 to 1.07) | 0.65¢ (0.08 to 1.20) |
| Spread capture vs prior-minute mid | −0.43¢ | +0.63¢ | +0.85¢ |
| 1-minute markout | −0.00¢ | −0.03¢ | +0.34¢ |
| Taker fee (paid to Kalshi) | 0.95¢ | 1.06¢ | 1.02¢ |
| Fills with model edge ≥ 1¢ | 1.15¢ (−0.78 to 3.11) | 1.85¢ (0.51 to 3.23) | 0.15¢ (−3.10 to 3.25) |
| Fills with model edge < 0 | −0.03¢ | −0.79¢ | 1.04¢ |

Hourly, by model edge for the maker:

| Edge | Maker P&L (95% CI) |
|---|---|
| < −5¢ | −1.58¢ (−3.41 to 0.31) |
| −5 to −2¢ | −0.79¢ (−2.18 to 0.53) |
| −2 to 0¢ | +0.28¢ (−0.58 to 1.18) |
| 0 to 2¢ | +0.69¢ (−0.09 to 1.42) |
| 2 to 5¢ | +1.04¢ (−0.37 to 2.44) |
| > 5¢ | +2.74¢ (0.79 to 4.76) |

The 15-minute spread capture is measured against a mid up to a minute old, which is stale at that tenor; settlement P&L is the reliable measure. Limits: fills went to whichever makers were at the front of the queue, so the model-filtered numbers assume those fills would have been ours. Full breakdowns (by fill size, price and time left) are in `docs/results/markouts.json` and [`04_MARKET_MAKING.md`](04_MARKET_MAKING.md).

---

## 6.9 What is not tested

| Item | Why not | How to close it |
|---|---|---|
| Sub-second index replica and volatility read for 15-minute markets | Needs live or historical order books from all seven exchanges | Phase 1 of the roadmap: record books and Kalshi's BRTI stream |
| Polymarket (Chainlink, Binance-candle markets) | Needs Polymarket history and Chainlink stream history | Pull both and run the same calibration; handle the mid-2026 rule change |
| Weekly to year-end contracts and touch markets | Needs Deribit option-chain history | Tardis.dev history; options-implied pricing (§1.11) |
| A full queue-position replay of market-making P&L | Needs order-book history for Kalshi | Record Kalshi WebSocket books; replay with latency |
| News defense | Needs licensed real-time X data | Enterprise X or vendor feed; measure markouts around classified posts |
