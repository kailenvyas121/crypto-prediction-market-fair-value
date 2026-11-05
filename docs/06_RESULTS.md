# 6. Results: Every Test, Its Method and Its Limits

Every number in the other documents comes from one of the studies below. Each study is one module in `src/pinpricer/research/`. `make results` reruns them all and writes `docs/results/<study>.json`.

**Common rules:**
- **Train / test split.** Anything fitted (volatility weights, time-of-week profile, tail parameter, index offset, blend weights, event bumps) uses data **before 1 May 2026**. Accuracy is scored **from 1 May to 27 Oct 2026**, which the model never saw. Studies that only describe the data (crowd error, the OI story, implied-vs-realized volatility, per-type event ratios) use the full sample and say so.
- **No look-ahead.** At each minute the model sees only data up to that minute. Binance bars are keyed by their close. Positioning snapshots are used only from 5 minutes after their timestamp.
- **Honest intervals.** Confidence intervals resample whole **UTC days**, or **weeks** for the sentiment study. Contracts closing on the same day share one price path, so treating events as independent would make intervals too narrow.
- **Index proxy.** Spot is the median of Coinbase and Bitstamp one-minute closes (both BRTI constituents), raised by a +0.38 bp offset fit on training settlements.

---

## 6.1 Index proxy vs the official settlement (`proxy`)

Each source's one-minute close ending at each hourly settlement, compared with Kalshi's 60-second BRTI settlement value (7,816 hours):

| Source | Median difference | Median absolute | 95th percentile absolute |
|---|---|---|---|
| Coinbase | −0.57 bp | 1.40 bp | 6.2 bp |
| Bitstamp | −0.45 bp | 1.09 bp | 5.6 bp |
| Median of the two (the proxy) | −0.52 bp | 1.18 bp | 5.8 bp |
| Binance BTC/USDT | +4.94 bp | 5.50 bp | 15.0 bp |

The free USD composite tracks the settlement index to about a basis point. Binance's USDT price carries a ~5 bp basis.

---

## 6.2 Calibration: model vs outcomes vs the Kalshi mid (`calibration`)

**Rows:** each contract-minute with a real two-sided Kalshi quote (bid ≥ 1¢, ask ≤ 99¢, spread ≤ 10¢). Ladder minutes are sampled every 5 minutes.

| Test set | Contract-minutes | Events |
|---|---|---|
| 15-minute | 144,255 | 11,517 |
| Hourly | 257,581 | 2,737 |
| Daily | 534,324 | 104 |

**Brier score (lower is better):**

| Model | 15-minute | Hourly | Daily |
|---|---|---|---|
| Naive baseline: Binance price, EWMA vol, normal, no averaging | 0.2447 | 0.1042 | 0.0949 |
| Baseline: options-implied (DVOL Black-Scholes digital) | 0.1757 | 0.0995 | 0.0963 |
| Variant: Binance price minus trailing 24h USDT basis, full v4 model | 0.1689 | 0.0924 | 0.0924 |
| v0 flat 30-day vol, normal | 0.1737 | 0.0992 | 0.0964 |
| v1 EWMA realized vol | 0.1664 | 0.0940 | 0.0948 |
| v2 HAR + time of week | 0.1668 | 0.0937 | 0.0947 |
| v3 + DVOL | 0.1664 | 0.0933 | 0.0939 |
| **v4 + Student-t tails** | **0.1652** | **0.0923** | **0.0925** |
| Kalshi mid | 0.1622 | 0.0920 | 0.0930 |

All rows except the options-implied baseline and the naive Binance row include the averaging adjustment; all except naive Binance include the proxy offset.

**Average gap to the Kalshi mid:** v4 4.3¢ / 2.2¢ / 1.9¢ (15m / hourly / daily). Options-implied baseline 8.4 / 6.1 / 3.6¢. Naive Binance 20.9 / 6.5 / 4.0¢.

**v4 compared with the alternatives** (Brier difference × 1000, 95% CI by day):

| | 15-minute | Hourly | Daily |
|---|---|---|---|
| v4 − Kalshi mid | +3.0 (+2.4, +3.8) | +0.3 (+0.1, +0.6) | −0.5 (−1.2, +0.1) |
| v4 − options-implied | −10.4 (−12.4, −8.7) | −7.2 (−8.6, −5.8) | −3.8 (−5.9, −1.9) |
| v4 − naive Binance | −79.5 (−92.4, −66.2) | −11.9 (−14.1, −9.7) | −2.5 (−4.0, −0.8) |
| v4 − basis-corrected Binance | −3.7 (−4.9, −2.5) | −0.1 (−0.3, +0.1) | 0.0 (−0.1, +0.1) |

**Reading the comparison:**
- **Kalshi mid.** On hourly, v4 is statistically behind, but by a tiny margin. On daily it is ahead but not significantly. On 15-minute it is clearly behind.
- **Public baselines.** v4 beats the options-implied and naive Binance baselines everywhere.
- **Basis-corrected Binance.** It matches v4 on hourly and daily, so a careful Binance-based index is as good as the USD composite there. It loses on 15-minute contracts, where the intraday basis matters.

**Blend.** The weight on v4 in mid + w·(v4 − mid) is fit on training data:
- Weights: 0.26 (15-min), 0.51 (hourly), 0.80 (daily).
- Out of sample, the blend − mid Brier difference (× 1000, 95% CI) is −0.05 to +0.25 (15-min), −0.21 to +0.04 (hourly) and −1.11 to +0.03 (daily).
- The hourly and daily point estimates favor the blend, but **none is significant**. The model is close to the mid; it is not shown to carry extra information.

**Other measurements:**
- **Settlement averaging.** Average gap to mid on 15-minute contracts falls from 13.3¢ to 8.8¢ in the final minute, and from 6.6¢ to 5.3¢ with 1–3 minutes left. There is no effect beyond ~10 minutes.
- **Layer gains** (Brier × 1000, 15m / hourly / daily):
  - flat → realized vol: 7.3 / 5.2 / 1.6
  - adding fat tails: 1.2 / 1.0 / 1.4
  - HAR + time of week vs EWMA: −0.4 / 0.3 / 0.1 (worse on 15-minute)
- **Fat tails on cheap contracts** 0.5–1.5σ out of the money (full test set):
  - The Kalshi mid sits 2.2–2.3¢ above what these contracts actually paid.
  - The normal model sits 2.0–3.2¢ above the mid.
  - The t-model sits 0.8–1.4¢ below the mid.
- **Implied vs realized volatility** (descriptive, fit on the test set). The vol multiple of our forecast that best fits the mid is 1.02 / 1.00 / 1.06; the multiple that best fits outcomes is 0.96 / 0.96 / 0.92.
- **Fitted parameters:**
  - ν = 4.5 (15-minute) and 4.2 (1-hour), with standardized excess kurtosis of 9.7 and 8.6. Daily contracts reuse the 1-hour ν, and whether kurtosis decays by 24 hours is untested.
  - Variance-forecast elasticities: next hour 0.52 / 0.35 / 0.01 / 0.30 (RV 1h / 24h / 7d / DVOL²); next 24h 0.17 / 0.38 / 0.14 / 0.40.
  - Weekday time-of-week variance: 0.55–0.73× overnight ET, 2.6× at 9–10 AM, 3.0× at 10–11 AM; weekends 0.67×.

**Limits:**
- Kalshi one-minute candles are end-of-minute quotes, not executable fills.
- The proxy is not the licensed index.
- The daily result rests on 104 events.

---

## 6.3 Why 15-minute trails (`index_gap`)

Each quote is inverted for the index level the market must be using, holding our variance and tails fixed. The gap is ln(implied / proxy).

| | 15-minute | Hourly |
|---|---|---|
| Median absolute gap | 0.92 bp | 1.67 bp |
| 90th percentile | 2.8 bp | 6.1 bp |
| Gap growth per 1σ of strike distance | 1.6 bp | 2.6 bp |

**Same minute, two markets (13,376 minutes):**
- The 15-minute and hourly-ladder gaps correlate at 0.34.
- Repricing 15-minute contracts on the ladder-implied index narrows the average gap to mid from 4.45¢ to 4.21¢, but Brier gets slightly worse (0.2098 → 0.2107).

**Reading:**
- The gap is about the size of the proxy's error and partly shared across markets. That fits index measurement, but it also fits Kalshi quotes lagging our end-of-minute price.
- The gap grows with distance, which suggests the market reads short-term volatility faster.
- Neither explanation is proven with one-minute data. Phase 3 of the roadmap tests both with sub-second data before any 15-minute quoting.

---

## 6.4 Perp lead (`lead`)

Binance BTC perp vs Binance spot, 100 ms last-trade returns, 2026-10-14 to 10-16.

| Lag | Correlation |
|---|---|
| Perp leads by 100 ms | 0.18 |
| Same 100 ms | 0.62 |
| Spot leads by 100 ms | 0.09 |
| Perp leads by 200 ms / 300 ms | 0.08 / 0.07 |

- 69% of the lead-lag correlation sits on the side where the perp moves first.
- The last second of perp-minus-spot movement explains 1.7% of the next second of spot.

**Limits:** three days, Binance spot only. The lead over USD exchanges needs synchronized sub-second data from those venues.

---

## 6.5 Perp positioning (`positioning`)

Hourly data. Train before May 2026 (4,991 hours); test from 1 May to 25 Oct 2026 (4,269 hours).

| Question | Result |
|---|---|
| Direction, all signals (OI change, OI level, funding, basis, top-trader and account long/short, taker ratio, past returns) | Out-of-sample R² −0.4% (1h), −2.0% (4h), −10.8% (24h) |
| Best single signal for the next hour (OI change) | R² +0.05%, correlation 0.03 |
| Volatility: base forecast (HAR + time of week + DVOL) | Out-of-sample R² 0.63 on next-hour log variance |
| Volatility: positioning on the base forecast's error | Out-of-sample R² −0.03 (no help) |
| Tails: 4-hour moves beyond 2σ, most vs least crowded long group (cut points set on training data, so test groups are uneven: 1,342 vs 630 hours) | Down: 1.8% vs 1.4%. Up: 3.1% vs 1.9% |
| OI story quadrants, next 4 hours (descriptive, full sample, non-overlapping) | Largest \|t\| = 1.35; none significant |
| Liquidation-like hours (OI −2%, price ±1%; n = 77) | After a down-flush, the next 4h averaged +16 bp (t = 0.96) |

**Case study (not a statistical test): 10–11 Oct 2025.**
- Before the cascade, OI was +0.8σ vs its 30-day mean and funding was 0.4 bp.
- In the crash hour (21:00–22:00 UTC), realized volatility was 334 bp against a 119 bp forecast.
- OI fell 18.6% that hour and 37.7% over 24 hours. BTC was down about 9% over the day.

**Methodology note:** using snapshots at their own timestamp made OI change appear to predict the next hour (R² 0.9%). Using each snapshot only from 5 minutes after its timestamp removed the effect.

---

## 6.6 BTC beta (`beta`)

Binance USDT spot, Nov 2025–Oct 2026.

| | β (1m / 1h / 1d) | R² (1m / 1h / 1d) | β in BTC's top 1% hours | Same direction in those hours | Annualized vol |
|---|---|---|---|---|---|
| ETH | 1.17 / 1.21 / 1.26 | 0.74 / 0.79 / 0.82 | 1.20 | 100% | 61% |
| SOL | 1.24 / 1.26 / 1.26 | 0.65 / 0.70 / 0.76 | 1.21 | 100% | 68% |
| BTC | 1 | 1 | 1 | – | 45% |

---

## 6.7 Macro releases (`events`)

**Releases:** 11 CPI, 12 payrolls and 8 FOMC from `configs/events.csv`, checked against federalreserve.gov and bls.gov schedules (including shutdown-delayed dates).

**Method:**
- Realized variance from the release minute onward is compared with the forecast made at the release time.
- That ratio is divided by the same ratio at the same weekday and time on non-release days (±1 and ±2 weeks), because the time-of-week profile already averages some release days in.
- Per-type medians below use all releases (descriptive). The pooled bump is fit on the 16 training releases.

| | First 5 minutes | First hour | Minutes 5–60 |
|---|---|---|---|
| CPI | 25.6× | 4.0× | 1.05× |
| FOMC | 16.2× | 6.3× | 4.2× |
| Payrolls | 10.8× | 3.2× | 1.8× |
| **Pooled, training releases** | **6.3×** | – | **2.0×** |

**Applying the pooled bump** to test-period hourly contracts whose remaining window spans a release (2,036 contract-minutes, 18 event-hours):

| | Brier |
|---|---|
| v4 | 0.1275 |
| v4 + bump | 0.1264 |
| Mid | 0.1275 |

- Bump − mid: 95% CI −5.4 to +2.9 (× 1000).
- The bump moves the model away from the mid (average gap 2.5¢ → 4.2¢) and toward outcomes.
- There are too few releases to call this significant.

---

## 6.8 Attention and crowd error (`sentiment`)

**Attention proxy:** daily English-Wikipedia pageviews of "Bitcoin", as a shock vs the trailing 30 days.

| Test (out of sample) | Result |
|---|---|
| Next-day realized volatility | R² 0.487 (daily HAR) vs 0.464 (+ attention) |
| Next 7-day return | R² 1.0%, correlation −0.12 (overlapping windows) |

**Crowd error:** mid − outcome on the cheap side (model under 30% and mid under 50% for that side), Kalshi hourly and daily ladders, full period. 6,475 events in 44 weeks; intervals resample weeks.

| | Overpriced by | 95% CI |
|---|---|---|
| Upside longshots | 2.0¢ | 0.5 to 3.5 |
| Downside longshots | 1.9¢ | 0.1 to 3.6 |
| Downside, after BTC's strongest 7-day third | 3.6¢ | 2.2 to 5.0 |
| Downside, after BTC's weakest 7-day third | −0.2¢ | −3.9 to 3.9 |
| Downside, highest attention third | 0.0¢ | −3.3 to 3.1 |
| Downside, lowest attention third | 3.1¢ | 1.6 to 4.5 |

The sentiment splits are descriptive: groups were cut on the full sample, each group is effectively about 15 independent weeks, and the extreme groups' intervals overlap.

---

## 6.9 Maker markouts (`markouts`)

**Sample:** random test-period events from `configs/data.yaml` (`kalshi.trades_sample`): 250 fifteen-minute windows, 120 hourly events and 20 daily events. Ladder strikes are chosen from the last settlement known at each event's open (±0.5%·√hours), so the sample does not depend on outcomes. 7.6M fills, each with price, size and taker side.

**Measures, per contract, from the maker's side:**
- settlement P&L: s·(p − Y)
- spread capture: s·(p − mid), against the mid at the end of the minute before the fill
- markout: s·(p − mid), against the mid at the end of the next full minute (1–2 minutes after the fill)
- model edge: s·(p − FV)

Makers pay no fee on these series. Taker fees are computed per fill as ceil(0.07·C·P(1−P)), rounded up to the cent. Intervals resample whole days.

| | 15-minute | Hourly | Daily |
|---|---|---|---|
| Contracts | 405M | 149M | 48M |
| Maker settlement P&L | 0.48¢ (0.20 to 0.81) | 0.74¢ (0.23 to 1.28) | 0.83¢ (0.09 to 1.54) |
| Spread capture vs prior-minute mid | −0.43¢ | +0.67¢ | +0.90¢ |
| Markout after 1–2 minutes | −0.01¢ | +0.02¢ | +0.41¢ |
| Taker fee (paid to Kalshi) | 0.96¢ | 1.10¢ | 1.01¢ |
| Fills with model edge ≥ 1¢ | 1.15¢ (−0.71 to 2.94) | 1.82¢ (0.29 to 3.36) | 0.85¢ (−2.55 to 3.85) |
| Fills with model edge < 0 | −0.03¢ (−1.43 to 1.37) | −0.46¢ (−1.65 to 0.69) | 0.50¢ (−3.06 to 3.95) |

**Hourly, by model edge for the maker:**

| Edge | Maker P&L (95% CI) |
|---|---|
| < −5¢ | −0.76¢ (−2.50 to 0.95) |
| −5 to −2¢ | −0.75¢ (−2.13 to 0.66) |
| −2 to 0¢ | +0.19¢ (−0.91 to 1.27) |
| 0 to 2¢ | +0.78¢ (−0.11 to 1.62) |
| 2 to 5¢ | +1.39¢ (−0.09 to 2.76) |
| > 5¢ | +2.35¢ (0.35 to 4.38) |

**Notes:**
- The 15-minute spread capture is measured against a mid up to a minute old, which is stale at that tenor; settlement P&L is the reliable measure.
- Fills went to whichever makers were at the front of the queue, so the model-filtered numbers assume those fills would have been ours.
- Full breakdowns (by fill size, price and time left) are in `docs/results/markouts.json` and [`04_MARKET_MAKING.md`](04_MARKET_MAKING.md).

---

## 6.10 What is not tested

| Item | Why not | How to close it |
|---|---|---|
| Sub-second index replica and volatility read for 15-minute markets | Needs order books from all seven exchanges | Phase 1 of the roadmap: record books and Kalshi's BRTI stream |
| Polymarket (Chainlink and Binance-candle markets) | Needs Polymarket history and Chainlink stream history | Pull both and run the same calibration; handle the mid-2026 rule change |
| Weekly to year-end contracts and touch markets | Needs Deribit option-chain history | Tardis.dev history; options-implied pricing (§1.11) |
| A queue-position replay of market-making P&L | Needs Kalshi order-book history | Record Kalshi WebSocket books; replay with latency |
| News defense | Needs licensed real-time X data | Enterprise X or vendor feed; measure markouts around classified posts |
| Tail shape at daily horizons | Daily contracts reuse the 1-hour ν | Fit ν on daily returns once more history accumulates |
