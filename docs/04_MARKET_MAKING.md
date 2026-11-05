# 4. From Fair Value to a Profitable Quote

Fair value is necessary but not sufficient. A market maker earns the spread and the crowd's biases, and loses to pick-off, adverse inventory and price gaps. This document covers how the money is made, what Kalshi's own fill data shows, and how quotes and risk should be run. Tags follow [`01_PRICING_GUIDE.md`](01_PRICING_GUIDE.md).

---

## 4.1 Do makers make money on these contracts? [Tested]

**Sample:** 7.6 million real Kalshi fills from random test-period events: 250 fifteen-minute windows, 120 hourly events and 20 daily events. Ladder strikes were chosen from the price known when each event opened (within ±0.5%·√hours), so the sample never depends on where BTC finished. Each fill records the price, the size and which side the taker bought.

**Maker P&L at settlement, per contract:** s·(price − outcome), where s = +1 if the maker sold YES and −1 if it bought YES. Makers pay no fee on these series. Results are contract-weighted; 95% intervals resample whole days, because contracts closing on the same day share one price path.

| Market | Contracts | Maker P&L per contract | 95% CI | Taker fee paid (to Kalshi) |
|---|---|---|---|---|
| 15-minute | 405M | **+0.48¢** | 0.20 to 0.81 | 0.96¢ |
| Hourly | 149M | **+0.74¢** | 0.23 to 1.28 | 1.10¢ |
| Daily | 48M | **+0.83¢** | 0.09 to 1.54 | 1.01¢ |

Makers as a group earn about half to three-quarters of a cent per contract at every tenor. Takers lose that plus the fee, which is computed per fill as ceil(0.07·C·P(1−P)) rounded up to the cent. This matches Bürgi, Deng & Whelan's finding that makers outperform takers on Kalshi [Source].

---

## 4.2 Does the model tell good fills from bad? [Tested]

Each fill is bucketed by the model's edge for the maker, s·(price − fair value), with fair value computed from data up to the minute before the fill.

**Hourly:**

| Model edge for the maker | Maker P&L per contract (95% CI) |
|---|---|
| < −5¢ | −0.76¢ (−2.50 to 0.95) |
| −5 to −2¢ | −0.75¢ (−2.13 to 0.66) |
| −2 to 0¢ | +0.19¢ (−0.91 to 1.27) |
| 0 to 2¢ | +0.78¢ (−0.11 to 1.62) |
| 2 to 5¢ | +1.39¢ (−0.09 to 2.76) |
| > 5¢ | +2.35¢ (0.35 to 4.38) |

**Fills the model rates at ≥ 1¢ edge vs fills it rates negative:**

| Market | Edge ≥ 1¢ | Edge < 0 | All fills |
|---|---|---|---|
| 15-minute | 1.15¢ (−0.71 to 2.94) | −0.03¢ (−1.43 to 1.37) | 0.48¢ |
| Hourly | **1.82¢ (0.29 to 3.36)** | −0.46¢ (−1.65 to 0.69) | 0.74¢ |
| Daily | 0.85¢ (−2.55 to 3.85) | 0.50¢ (−3.06 to 3.95) | 0.83¢ |

- **Hourly.** Maker P&L rises steadily with the model's edge. Fills the model rates favorable earn about **2.5× the average** per contract, and the interval excludes zero. Fills it rates unfavorable are negative on average, but that interval includes zero.
- **15-minute.** Same direction, but the intervals are wide, consistent with the 15-minute model trailing the market (§1.10).
- **Daily.** Twenty events are too few to show anything either way, so no claim is made there.

**Caveat.** These are fills that happened, taken by whichever makers were at the front of the queue. A new entrant gets a share of them and may be picked off more often than incumbents. A queue-position replay on recorded Kalshi books is the next test ([`06_RESULTS.md`](06_RESULTS.md) §6.10).

---

## 4.3 Where the money is, and where it leaks [Tested]

**By fill size (hourly):**

| Fill size (contracts) | Maker P&L per contract | Markout after ~1 minute |
|---|---|---|
| ≤10 | +1.34¢ (0.80 to 1.86) | +0.24¢ |
| 10–100 | +0.82¢ (0.18 to 1.43) | +0.20¢ |
| 100–1k | +0.76¢ (0.24 to 1.27) | +0.04¢ |
| >1k | +0.33¢ (−1.14 to 1.83) | −0.42¢ |

Small, retail-sized fills pay makers the most. Fills over 1,000 contracts pay the least, and the market moves against the maker after them: large takers are better informed.

**By time left (15-minute):**

| Minutes left | Maker P&L per contract |
|---|---|
| 0–1 | +0.10¢ (−0.33 to 0.52) |
| 1–3 | +0.19¢ (−0.26 to 0.72) |
| 3–6 | −0.19¢ (−0.77 to 0.38) |
| 6–10 | +0.33¢ (−0.50 to 1.07) |
| 10–15 | +1.48¢ (0.55 to 2.44) |

Only the 10–15 minute bucket is clearly positive. Makers earn roughly nothing over the last 10 minutes, where fair value moves fastest and fast traders read the settlement average best. That is the pick-off problem in numbers. It argues for small size and wide quotes late in the window, unless the averaging math (§1.7) runs on sub-second data.

**By price (hourly):**

| Contract price | Maker P&L per contract |
|---|---|
| <10¢ | +0.62¢ (0.22 to 0.99) |
| 10–30¢ | +2.42¢ (1.27 to 3.39) |
| 30–70¢ | +0.66¢ (−0.31 to 1.61) |
| 70–90¢ | −0.30¢ (−1.60 to 0.91) |
| >90¢ | +0.08¢ (−0.88 to 1.06) |

**The longshot premium.** Across 6,475 hourly and daily events, cheap contracts are overpriced by about 2¢ on both the upside and the downside ([`03_SENTIMENT_AND_NEWS.md`](03_SENTIMENT_AND_NEWS.md) §3.2). Selling them, with an accurate fat-tailed fair value, is a structural maker edge.

---

## 4.4 Indicative scale

Mean traded volume per event in our sample: 1.6M contracts per 15-minute window, 1.2M per hourly event and 2.4M per daily event. Ladders are counted only within the sampled strikes, so this understates them. At the average maker economics above, **each 1% share of maker volume** is worth roughly:

| Market | Events per day | Gross per 1% share, per day |
|---|---|---|
| 15-minute | 96 | $7,451 |
| Hourly | 24 | $2,190 |
| Daily | 1 | $201 |

This is gross settlement P&L before hedging costs, capital, infrastructure and the extra adverse selection a new entrant faces. It is indicative, not a forecast. The pool is large enough to matter, and on hourly the model-filtered edge is several times the average.

---

## 4.5 How to quote

1. **Center on fair value**, shaded for inventory: reservation = FV − γ·q·Var_h. Var_h is the payoff's variance over the expected unwind horizon, and it shrinks to p(1−p) at settlement. This is the binary-option version of the standard inventory skew.
2. **Rest only where it pays:** expected spread capture + rebate − expected pick-off loss − inventory cost > 0. The book is usually one tick wide, so the decision is *whether* to sit at the touch and how much, not how wide.
3. **Size down near expiry and on fast markets.** Fair value moves per bp of BTC:
   - one day out: 0.15¢
   - one hour: 0.75¢
   - 15 minutes: 1.5¢
   - start of the final 60-second averaging window: about 10¢
4. **Pull on leading signals:** perp jumps (100–300 ms ahead of spot), news alerts, and liquidation or OI flushes.
5. **Keep the ladder coherent.** Quote every strike and bucket from one distribution, and project quotes back onto monotone, sum-to-one constraints after any change.
6. **Lean into the structural edge.** Sell longshots on both sides, sized by model edge and capped by the ladder-sweep limit.
7. **Widen before scheduled releases.** The first 5 minutes after a release carry about 6× forecast variance (pooled, training releases). Single releases have run much higher: CPI and FOMC medians are 16–26× over the full sample.

---

## 4.6 Risk

- **Hedging.** Per-contract delta hedging doesn't pay below daily tenor, because a perp hedge per contract costs more than the edge. Hedge the **net delta of the whole book** in perps, in bands, and price the perp basis into the hedge (the Binance perp averaged 4.5 bp below spot).
- **Exposure as payoff vectors.** Each expiry's position is a vector of P&L by settlement value. The limit is the exact worst-case loss per expiry.
- **Ladder-sweep cap.** One BTC gap fills every resting order on the way, so cap aggregate resting size per direction.
- **Cross-asset shock grid.** ETH and SOL move with BTC at β ≈ 1.2, and in the same direction in every large BTC hour. Diversification across coins is close to zero in a crash, so limit on a joint BTC/ETH/SOL shock grid.
- **Kill switches:**
  - index replica diverging from Kalshi's BRTI or Chainlink
  - stale feeds or clock drift
  - realized volatility above k× the model
  - news alerts, or liquidation and OI flushes
  - drawdown limits
  - Kalshi order-group fill limits and the Polymarket heartbeat
- **Venue rules.** Kalshi's $25k-per-strike position accountability, the Thursday 3–5 AM ET pause, and the CFTC's scrutiny of market-maker programs.

---

## 4.7 Liquidity-provider programs

Kalshi allots liquidity-provider slots by auction: 2 on crypto 15-minute markets and 1 on crypto hourly and daily. Current programs end 12/31/26 [Source]. Polymarket rebates 20% of crypto taker fees to makers [Source]. These rewards add to the spread economics above. Winning a slot requires reliable, two-sided resting liquidity, and a model that comes within a fraction of a thousandth of the market's accuracy on hourly and daily makes that safe to provide.
