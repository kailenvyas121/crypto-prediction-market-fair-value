# 4. From Fair Value to a Profitable Quote

Fair value is necessary but not sufficient. A market maker earns the spread and the crowd's biases, and loses to pick-off, adverse inventory and price gaps. This document covers how the money is made, what Kalshi's own fill data shows, and how quotes and risk should be run. Tags follow [`01_PRICING_GUIDE.md`](01_PRICING_GUIDE.md).

---

## 4.1 Do makers make money on these contracts? [Tested]

**Sample:** 7.8 million real Kalshi fills from random test-period events (250 fifteen-minute windows, 120 hourly events, 20 daily events; ladder strikes within ±1% of settlement, where the volume is). Each fill records the price and which side the taker bought.

**Maker P&L at settlement, per contract:** s·(price − outcome), where s = +1 if the maker sold YES and −1 if it bought YES. Makers pay no fee on these series. Contract-weighted; 95% intervals resample whole events.

| Market | Contracts | Maker P&L per contract | 95% CI | Taker fee paid (to Kalshi) |
|---|---|---|---|---|
| 15-minute | 405M | **+0.48¢** | 0.17 to 0.78 | 0.95¢ |
| Hourly | 181M | **+0.61¢** | 0.17 to 1.07 | 1.06¢ |
| Daily | 41M | **+0.65¢** | 0.08 to 1.20 | 1.02¢ |

Makers as a group earn about half a cent per contract at every tenor, and takers lose that plus the fee. That matches Bürgi, Deng & Whelan's finding that makers outperform takers on Kalshi [Source].

---

## 4.2 Does the model tell good fills from bad? [Tested]

Each fill is bucketed by the model's edge for the maker, s·(price − fair value), with fair value computed from data up to the minute before the fill.

**Hourly:**

| Model edge for the maker | Maker P&L per contract (95% CI) |
|---|---|
| < −5¢ | −1.58¢ (−3.41 to 0.31) |
| −5 to −2¢ | −0.79¢ (−2.18 to 0.53) |
| −2 to 0¢ | +0.28¢ (−0.58 to 1.18) |
| 0 to 2¢ | +0.69¢ (−0.09 to 1.42) |
| 2 to 5¢ | +1.04¢ (−0.37 to 2.44) |
| > 5¢ | +2.74¢ (0.79 to 4.76) |

**Fills the model rates at ≥ 1¢ edge vs fills it rates negative:**

| Market | Edge ≥ 1¢ | Edge < 0 | All fills |
|---|---|---|---|
| 15-minute | 1.15¢ (−0.78 to 3.11) | −0.03¢ | 0.48¢ |
| Hourly | **1.85¢ (0.51 to 3.23)** | −0.79¢ | 0.61¢ |
| Daily | 0.15¢ (−3.10 to 3.25) | 1.04¢ | 0.65¢ |

**On hourly, standing only where the model sees edge roughly triples the average maker's P&L per contract, and the fills it would skip lose money.** On 15-minute the direction is the same (+1.15¢ vs −0.03¢) but the interval is wide, consistent with the 15-minute model trailing the market (§1.10). On daily the 20-event sample shows nothing either way: the intervals span roughly ±3¢ and the ordering is reversed, so no claim is made there.

**Caveat.** These are fills that happened, taken by whichever makers were at the front of the queue. A new entrant gets a share of them and may be picked off more often than incumbents. A queue-position replay on recorded Kalshi books is the next test ([`06_RESULTS.md`](06_RESULTS.md) §6.9).

---

## 4.3 Where the money is, and where it leaks [Tested]

**By fill size (hourly):**

| Fill size (contracts) | Maker P&L per contract |
|---|---|
| ≤10 | +1.10¢ (0.52 to 1.66) |
| 10–100 | +0.60¢ (−0.07 to 1.31) |
| 100–1k | +0.68¢ (0.25 to 1.13) |
| >1k | +0.23¢ (−1.03 to 1.57) |

Small, retail-sized fills pay makers the most.

**By time left (15-minute):**

| Minutes left | Maker P&L | One-minute markout |
|---|---|---|
| 0–1 | +0.10¢ (−0.30 to 0.51) | −0.73¢ |
| 1–3 | +0.19¢ (−0.26 to 0.70) | −0.17¢ |
| 3–6 | −0.19¢ (−0.78 to 0.39) | −0.03¢ |
| 6–10 | +0.33¢ (−0.44 to 1.12) | +0.05¢ |
| 10–15 | +1.48¢ (0.41 to 2.50) | +0.07¢ |

The final minute is where makers stop earning: the one-minute markout turns negative because fast traders read the settlement average better. That is the pick-off problem in numbers, and it argues for pulling or widening in the last minute unless the averaging math (§1.7) runs on sub-second data.

**By price (hourly):**

| Contract price | Maker P&L per contract |
|---|---|
| <10¢ | +0.65¢ (0.25 to 1.02) |
| 10–30¢ | +1.68¢ (0.45 to 2.78) |
| 30–70¢ | +0.62¢ (−0.33 to 1.53) |
| 70–90¢ | −0.00¢ (−1.10 to 1.06) |
| >90¢ | −0.04¢ (−0.97 to 0.83) |

**The longshot premium.** Across 6,470 hourly and daily events, cheap contracts (under 30% for that side) are overpriced by about 2¢ on both the upside and the downside ([`03_SENTIMENT_AND_NEWS.md`](03_SENTIMENT_AND_NEWS.md) §3.2). Selling those, with an accurate fat-tailed fair value, is a structural maker edge.

---

## 4.4 Indicative scale

Median traded volume per event in our sample: 1.5M contracts per 15-minute window, 1.4M per hourly event and 2.0M per daily event (ladders counted only within ±1% of settlement, so this understates them). At the average maker economics above, **each 1% share of maker volume** is worth roughly:

| Market | Events per day | Gross per 1% share, per day |
|---|---|---|
| 15-minute | 96 | $6,884 |
| Hourly | 24 | $2,088 |
| Daily | 1 | $132 |

This is gross settlement P&L before hedging costs, capital, infrastructure and the extra adverse selection a new entrant faces. It is indicative, not a forecast. The point is that the pool is large enough to matter, and the model-filtered edge on hourly is roughly three times the average.

---

## 4.5 How to quote

1. **Center on fair value**, shaded for inventory: reservation = FV − γ·q·Var_h, where Var_h is the payoff's variance over the expected unwind horizon (it shrinks to p(1−p) at settlement). This is the binary-option version of the standard inventory skew.
2. **Rest only where it pays.** Expected spread capture + rebate − expected pick-off loss − inventory cost > 0. The book is usually one tick wide, so the decision is *whether* to sit at the touch and how much, not how wide.
3. **Size down near expiry and on fast markets.** Fair value moves 0.15¢ per bp of BTC at one day out, 0.75¢ at one hour, 1.5¢ at 15 minutes and 5.8¢ in the final minute.
4. **Pull on leading signals.** Perp jumps (100–300 ms ahead of spot), news alerts, and liquidation and OI flushes.
5. **Keep the ladder coherent.** Every strike and bucket is quoted from one distribution; project quotes back onto monotone, sum-to-one constraints after any change.
6. **Lean into the structural edges.** Sell longshots on both sides, sized by model edge. Collect the small volatility premium the book carries (the mid prices 1.00–1.06× our forecast volatility; outcomes favor 0.92–0.96×).
7. **Widen before scheduled releases.** The first 5 minutes after CPI or FOMC carry about 21× forecast variance.

---

## 4.6 Risk

- **Hedging.** Per-contract delta hedging doesn't pay below daily tenor: a perp hedge per contract costs more than the edge. Hedge the **net delta of the whole book** in perps, in bands. Price the perp basis (Binance perp averaged 4.5 bp below spot) into the hedge.
- **Exposure as payoff vectors.** Each expiry's position is a vector of P&L by settlement value. The limit is the exact worst-case loss per expiry.
- **Ladder-sweep cap.** One BTC gap fills every resting order on the way. Cap aggregate resting size per direction.
- **Cross-asset shock grid.** ETH and SOL move with BTC at β ≈ 1.2 and in the same direction in every large BTC hour, so diversification across coins is close to zero in a crash. Limit on a joint BTC/ETH/SOL shock grid.
- **Kill switches:**
  - index replica diverging from Kalshi's BRTI or from Chainlink
  - stale feeds or clock drift
  - realized volatility above k× the model
  - news alerts, and liquidation or OI flushes
  - drawdown limits
  - Kalshi order-group fill limits; Polymarket heartbeat
- **Venue rules.** Kalshi's $25k-per-strike position accountability, the Thursday 3–5 AM ET pause, and the CFTC's scrutiny of market-maker programs.

---

## 4.7 Liquidity-provider programs

Kalshi allots liquidity-provider slots by auction: 2 on crypto 15-minute markets, 1 on crypto hourly and daily. Current programs end 12/31/26 [Source]. Polymarket rebates 20% of crypto taker fees to makers [Source]. These rewards add to the spread economics above, and winning a slot requires showing reliable, two-sided resting liquidity. That is exactly what a model that ties the market on hourly and daily makes safe to provide.
