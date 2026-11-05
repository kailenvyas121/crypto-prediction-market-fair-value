> **Archived working notes (2026-10-27).** This was the research sweep written before any testing. Where it conflicts with the numbered docs, the numbered docs win: they use this repo's measured results and a fact-check done on 2026-11-04. Known corrections: Polymarket 15-minute markets settle on a Chainlink 60-second TWAP at the end versus the price at the start (they compared two single prints before mid-2026); Polymarket US settles on BRTI; the Polymarket taker delay is not officially documented; Aleti & Mizrach (2021) find that CME futures, not perps, lead spot; the perp lead and positioning claims are replaced by measured results in `docs/02_MARKET_SIGNALS.md`.

# Pricing and Making Markets in Crypto Prediction Contracts — Research Outline

Prepared for the PinPredict take-home. Research sweep as of 2026-10-27. Tags: **[V]** verified against a primary source (rulebook, live API, the paper itself); **[R]** reported by press or a single source; **[D]** our own derivation or calculation, to be re-checked before it goes in the memo.

---

## 0. Thesis (one paragraph)

Short-dated crypto prediction contracts are **Asian-style digital options on a published index** (CF Benchmarks BRTI for Kalshi). The model itself is not exotic. The edge does not come from forecasting direction, because sub-hour drift signals are noise. It does not come from out-forecasting the mid either: public tests find Kalshi's BTC ladder mid already beats options-implied models. The edge is in **market making**: being as accurate as the mid (settlement-index replication, intraday-seasonal vol, fat tails), never being stale (lead-feed protection), netting risk across the entire strike/expiry surface on one index, and winning the venue's liquidity-provider economics. This is SIG's options-MM playbook applied to a new underlying. The work that is new is the crypto microstructure.

---

## 1. Contract universe and settlement mechanics

### 1.1 Kalshi (the venue that matters: about 90% of short-term crypto prediction volume [R])
| Family | Tickers | Payoff | Settlement value |
|---|---|---|---|
| Above/below ladder | KXBTCD, KXETHD, … | Pays 1 if Ā > K. Strikes listed as X−0.01, so in effect ≥ X. BTC ladder spacing is $100 with about 188 strikes per event | Simple avg of the **60 one-second BRTI prints** before expiry [V] |
| Range buckets | KXBTC, KXETH | Ā ∈ [K₁, K₂] inclusive | same |
| 15-min up/down | KXBTC15M (+ ETH, SOL, XRP, DOGE, …) | Ā_close ≥ Ā_open (**tie pays YES**) | Strike is the prior window's 60s average [V] |
| Max/min (touch) | KXBTCMAXW/M/Y, MIN… | Pays 1 if any minute's **20%-trimmed mean** of BRTI crosses H | Discretely monitored barrier; wicks under about 12s cannot trigger it [V] |

- **Hours** [V]: hourly events run 24/7, including weekends. The exception is a **trading pause every Thursday from 3:00 to 5:00 AM ET**, and no events expire during it.
- **Tick sizes** [V]: hourly markets use 1¢ ticks. 15-min markets use `tapered_deci_cent`, which is 0.1¢ for prices below 10¢ or above 90¢ and 1¢ in between. Contracts can be fractional.
- **Fees** [V formula type / R coefficient]: taker fee = ceil(0.07·C·P(1−P)), which is 1.75¢ at 50¢. Makers pay nothing unless the series is `quadratic_with_maker_fees`. *Still to do: fetch the fee schedule PDF.*
- **Position accountability** [V]: $25k per strike per member.
- **Size** [V, our API pull]: KXBTC15M trades a median of about 3M contracts per 15-min window (max about 5.5M). KXBTCD trades about 1–2.4M contracts per hourly event. Range ladders are thin (25–90k). ETH 15M trades about 1/15th of BTC.
- **Infra** [V]: REST, WebSocket and FIX. **Order groups** auto-cancel orders on a 15s fill-count trigger, which works as a native kill switch. Kalshi **streams BRTI itself** (`cfbenchmarks_value`, at 1 Hz and 5 Hz), including a live 60s-average accumulator during the settlement minute.

### 1.2 Polymarket
- **International** [V]: 5m, 15m and 4h up/down markets settle on a **Chainlink 60s TWAP** (since 2026-08-07, after documented manipulation). Hourly markets settle on the **Binance BTC/USDT 1h candle**, and daily markets on a Binance 1m close at noon ET. The underlying is USDT, not USD.
- **Fees** [V]: taker fee = 0.07·C·p(1−p), and makers pay nothing. **20% of crypto taker fees are rebated to makers**, pro rata.
- **Taker speed bump** [V]: currently 150 ms (50 ms before 2026-09-04; earlier 500 ms, removed in February).
- **Volume** [V snapshot]: about $13M/day in BTC 5m and about $3M/day in BTC 15m, roughly one to two orders of magnitude below Kalshi.
- **Polymarket US** [R]: CFTC-regulated (via the QCEX acquisition). Added 15m BTC markets, reportedly settled on BRTI, in Sept 2026, and announced 5m markets on 10/27. *Settlement convention still to be confirmed.*

### 1.3 Other venues (secondary)
- **ForecastEx (IBKR)** [V]: a 15-min crypto contract certified 2026-10-12, economically identical to KXBTC15M (CF RTI, 60s averages).
- **CDNA / Crypto.com** [V]: a BTC event contract on its own trimmed 60s index.
- **Hyperliquid HIP-4** [R]: daily BTC binary on the HyperCore mark price, small.
- **Coinbase, Robinhood, Webull**: front-ends that route to Kalshi. This is where Kalshi's retail flow comes from.
- **Hedge and reference venues** [V]: Deribit dailies expire at 08:00 UTC and settle on a 30-*minute* TWAP, not 60s, so they don't match these contracts' settlement. Binance and Bybit perps. Kalshi's own BTC/ETH perps.

**Implication:** one pricing engine on BRTI covers Kalshi, ForecastEx and likely Polymarket US. Polymarket international needs a separate Chainlink- and Binance-based engine plus a basis model.

---

## 2. Competitive landscape

- **Designated MMs** [V]: SIG has been Kalshi's first designated MM since 2024 and runs a dedicated predictions desk. Kalshi's LP program allots slots through **reward auctions**: **2 LPs on crypto 15-min, 1 on crypto hourly/daily**. Names are undisclosed, and all programs end 12/31/26.
- **Others** [R]: Jump (equity deals with both venues), Wintermute (quoting since mid-2026), DRW (hiring a prediction-markets trader), Kalshi Trading (an affiliate; under litigation), Polymarket's in-house desk, Galaxy OTC. Kalshi says only about 5% of matches come from big institutional MMs.
- **Regulatory** [V]: CFTC staff advisory 26-23 (Aug 2026) flags MM programs that guarantee profits, and exchange-affiliated MMs. Kalshi is ending volume rewards and keeping rewards for resting liquidity.
- **Maker economics** [V]: Polymarket 15m makers made **+$728k, about 0.48% of volume, in one week before rebates**, while takers had a 53% win rate yet lost money (Telonex, Feb 2026). Makers earn more than takers on Kalshi (Bürgi, Deng & Whelan).

**Takeaway for Ben:** the venue is real (hundreds of millions of contracts a day), the flow is profitable to make against, and the institutional field is thin and new. An options-MM shop is well suited to this.

---

## 3. Fair-value engine

Each layer below lists what to build and the evidence for it.

### 3.1 Underlying: a BRTI replica
- **BRTI method** [V, CF methodology v17.0]:
  - Constituents are **Coinbase, Kraken, Bitstamp, Gemini, LMAX, Bullish and Crypto.com**, using USD books only. **Binance and perps are excluded.**
  - It is recomputed every 200 ms from the merged order books: cap the size at each price level, uncross the book, then take an exponentially depth-weighted mid with λ = 1/(0.3·v_T) out to a 0.5% spread-depth limit.
  - Stale books (>10s) and outlier books (>5% from the median) are dropped.
- **Plan:** subscribe to the 7 L2 feeds and recompute at 200 ms. Validate against Kalshi's BRTI stream, expecting residuals of a few bps.
- **Lead feed:** the Binance perp leads USD spot by about **100–300 ms** [D, 2h sample; consistent with the literature: Alexander & Heck 2020, Aleti & Mizrach 2021]. It predicts the next few BRTI prints (next-1s R² about 0.03–0.05). That matters for quote protection, not for fair value.

### 3.2 Variance forecast over [t, T]
- **Measurement:** 1-minute realized vol, or a realized kernel on the replica. Microstructure noise is small in BTC [D].
- **Model:** log-HAR (1h/24h/168h) × **an intraday/weekday seasonal factor indexed to ET** × an event bump, blended with Deribit implied total variance.
- **Out-of-sample R² for next-1h RV** [D, 12 months of Binance data]:

  | Model | R² |
  |---|---|
  | HAR | 0.16 |
  | + seasonality | 0.24 |
  | + DVOL | 0.28 |

  At 24h, HAR + DVOL reaches 0.34.
- **Seasonal multipliers** [D]:
  - 14–15 UTC on weekdays: about 1.65×
  - 13:30 and 14:30 UTC five-minute windows (8:30 ET data, US open): 1.5–1.8×
  - CME reopen at 22:00 UTC: 1.35×
  - Asian session: 0.8×
  - Weekend: 0.7×
  - Funding timestamps: a weak effect.
- **Events:** CPI and FOMC run at about 1.5–2.5× hourly variance as a prior [R]. Fit the bumps from our own event-window RV.
- **Kalshi ladder-implied vol** is below DVOL and close to realized (about 28% vs DVOL 37% vs RV 25% in one study [R]). The market already prices this. The goal is to match that accuracy.

### 3.3 Distribution shape: the largest single pricing error
- **Excess kurtosis after vol scaling** [D]: about 10 at 15m–1h and about 27 at 1m.
- **Lognormal error with correct σ** [D]: digitals 0.5–1.5σ out of the money are **overpriced by 3–5¢**, near-money buckets are underpriced, and tails beyond 2.5σ are underpriced 2–5×.
- **Fix:** a **Student-t with ν ≈ 3.9** on vol-scaled returns matches the empirical tail probabilities at every k checked [D]. Alternatively, use filtered historical simulation.
- **Jumps** [D]: about 3 one-minute jumps per day carrying about 9% of quadratic variation. They cluster, and order-flow imbalance predicts them (Scaillet, Treccani & Trevisan 2020).
- Refit ν by horizon and regime.

### 3.4 Averaged settlement (Asian digital)
- **Before the window (τ ≥ 60s)** [D, two independent derivations agree]: effective variance is σ²(τ − 0.658w) for 60 discrete prints. The effect is negligible at 1h. At 5 min, σ_eff ≈ 0.93σ; at 2 min, 0.82σ.
- **Inside the window** with k prints known: YES if the average of the remaining m prints ≥ K* = (nK − Σ_k)/m. The remaining average has variance σ²S²Δ(m+1)(2m+1)/(6m).
  - The strike K* moves quickly, so most contracts are decided partway through the minute.
  - Pin risk is smaller than point-settlement Greeks suggest.
- **15M up/down:** both ends are averages, giving variance σ²(T − t₀ − w/3), about 880 effective seconds.

### 3.5 Mapping to each contract (from one terminal distribution)
- **Ladder:** P(Ā > K).
- **Buckets:** CDF differences.
- **Up/down:** the difference of two averages.
- **Touch markets:** Monte Carlo at 1s steps under GARCH-t or HAR-t plus jumps, applying the exact trimmed-minute rule. The Broadie–Glasserman–Kou monitoring shift is about a 1-point effect; fat tails and vol-of-vol dominate.
- **Smile:** for expiries of 8h and longer, a digital = N(d₂) − Vega·∂σ/∂K. Use the Deribit smile as an anchor, interpolated in total variance on the seasonal clock.
- **Drift = 0.** BRTI is designed as a martingale. Funding, OI, basis, ETF flows and sentiment show **no credible directional signal under 1h** [D/R]. For example, funding's correlation with the next-8h return is −0.018. These variables help as **vol and jump-intensity state variables** only.

---

## 4. Quoting layer

- **The book is tick-bound** [V]: the top of book is one tick 92% of the time (Polymarket 15m). So the control variable is **whether to rest at the touch and how much size**, not the optimal δ.
- **Pick-off is the main threat** [D]. Fair-value sensitivity per 1 bp BTC move for an ATM digital at σ = 50%:

  | Time to expiry | Fair-value move per 1 bp |
  |---|---|
  | 1 day | 0.15¢ |
  | 1 hour | 0.75¢ |
  | 15 min | 1.5¢ |
  | 1 min | 5.8¢ |

  The taker fee (1.75¢ at 50¢) shields the maker from about 1.2 bp of BTC movement at 15 min, but only about 0.3 bp at 1 min.
  - Expected loss per arbitrage arrival = 2σ_FV[φ(z) − z(1−N(z))], where z = (h + f)/σ_FV and σ_FV = Δ·S·σ·√L over the cancel latency L.
  - Rest at the touch only if spread capture + rebate − λ_arb·loss − inventory cost > 0.
- **Fade and pull:**
  - Reprice on every lead-feed tick, and pull when |ΔFV| exceeds h + f − buffer.
  - Use a two-tier quote: a sticky core plus a fast layer.
  - Cut size as a function of 1s realized vol relative to the model, perp order-flow imbalance, microprice drift, τ and |d|.
  - Polymarket's 150 ms taker delay is the window that cancels must beat. Its quotes take a median 347 ms to react to large Binance moves [V], so this is where speed pays.
- **Inventory skew in the right units** [D]: r = p − γ·q·Var_h, where Var_h = Φ₂(d, d; ρ = h/τ) − p², and h is the expected unwind horizon. At settlement Var_h is p(1−p). This replaces Avellaneda–Stoikov's σ²(T − t), which is misspecified for binaries. The most rigorous related work is Feil & Nendel 2026 (arXiv 2607.17991), with a terminal penalty of γq²p(1−p).
- **Ladder coherence:**
  - Quote every strike and bucket from the **same distribution**.
  - Enforce that digitals are monotone in strike and that Σ bucket bids ≤ 1 ≤ Σ bucket asks.
  - Project quotes back onto these constraints after any change, for example with a QP. Combinatorial arbitrage of about $40M was realized on Polymarket over a year (Saguillo et al. 2025).
- **Favorite–longshot bias:** sub-10¢ contracts lose more than 60% for buyers on Kalshi (Bürgi, Deng & Whelan). The bias is mostly spread, which makers earn. That argues for leaning toward selling tails, subject to a ladder-sweep cap.

---

## 5. Risk

- **No per-contract delta hedging below daily tenor** [D]. At 15 min the hedge costs 2–7¢ per contract against under 1¢ of edge per fill. Hedge **net book delta** across all strikes and expiries with banded perp clips; candidates are Kalshi's own perp, Binance/Bybit/Hyperliquid, or CME.
- **Risk representation:** each expiry is a piecewise-constant payoff vector over settlement values, so the exact worst-case loss is the primary limit. Short expiries roll into longer ones as cash.
- **Limits:**
  - per-expiry max loss
  - per-asset delta
  - **ladder-sweep cap**: aggregate resting size per direction, since one gap fills every strike on the way
  - joint BTC/ETH scenario grid (simultaneous −3%/−5%/−8% one-minute moves)
- **Vega:** short-dated vega is really realized-vol exposure. A symmetric short ladder is close to vega-neutral but short kurtosis.
- **Manipulation tail** [V]: Dai, Jia & Yu (2026) document end-of-window pushes on Binance before Polymarket's 5m markets moved to TWAP settlement.
  - 821 wallets took $8.2M.
  - Flipping a 90%+ favorite succeeded 34% of the time when pushed.
  - Pushes cluster in thin overnight and weekend hours and in thin altcoins; in the XRP case one trader made $233k.
  - Averaging plus a multi-venue BRTI makes this harder, but widen in thin hours and in alt series.
- **Kill switches:**
  - lead-feed or index staleness, or divergence between BRTI replica, Chainlink and Binance
  - clock drift
  - 1s realized vol above k× the model
  - Kalshi order-group fill breakers
  - Polymarket heartbeat dead-man switch
  - per-expiry and daily drawdown
  - macro-release widening or blackout
  - Thursday-pause handling

---

## 6. Where the edge is, and where it isn't

**Plausible edge for PinPredict**
1. **Being a designated LP.** The slots are few and auctioned, and rewards are tied to resting liquidity. Polymarket's 20% fee rebate is a second source.
2. **Exact settlement replication**, especially pricing off the locked-in partial average in the final minute.
3. **Intraday-seasonal and event-aware vol plus fat tails.** The goal is to match the mid's accuracy at every moment, including the US open, CPI and Asian-hours lulls.
4. **One risk book across the BRTI surface** (15m, hourly, daily, ranges, touch, perps). Netting cuts hedge cost and lets the book quote tighter than single-market bots. The natural extension is **cross-sport/crypto capital efficiency**, which is a PinPredict-specific angle.
5. **Flow segmentation.** Bots are 55–62% of 5m/15m volume but only about 31% of daily/weekly volume [R]. Retail sits in the **hourly and daily** markets via Robinhood, Webull and Coinbase. Size is a usable toxicity proxy.
6. **Defensive latency.** Cancel/replace has to be well under 200 ms. Speed is the cost of entry, not the source of profit.

**Not edge (crowded or disproven)**
- Taker latency arbitrage: dead after fees and against ~20 ms rivals.
- Deribit-implied fair value vs the Kalshi ladder: four public tests found no edge. One pre-registered test lost 1.38¢ per contract.
- Buying 95–99¢ contracts late in the window.
- Buying Up and Down for under $1 combined.
- Time-of-day directional patterns.
- Sentiment at under 1h.

---

## 7. Validation plan (tests to run)

Every test can be run on free data. See section 8.

1. **Calibration.** Score model fair value against Kalshi KXBTCD/KXBTC15M outcomes, using `expiration_value` as the label. Report Brier, log-loss and reliability by τ and |d|.
   - Benchmarks: the Kalshi mid, lognormal + EWMA, lognormal + HAR-seasonal, and t + HAR-seasonal.
   - **Expected result:** we tie the mid. The pitch is "we match the market's own accuracy from first principles, so we can quote safely".
2. **Ablation.** Measure each layer's contribution (seasonality, t tails, settlement averaging, DVOL blend) in Brier and in cents of mispricing.
3. **Implied vs model vol.** Back out Kalshi ladder-implied σ per event and compare it with the forecast and the realized vol to expiry.
4. **Settlement minute.** Compare the partial-average fair value with the Kalshi book during the final 60s: does the book lag the locked-in information?
5. **Simulated market-making P&L.**
   - Use L2 replay (Kalshi WebSocket recordings; OpenMarket's Polymarket–Binance dataset) with a pessimistic queue/fill model and latency.
   - Decompose P&L per fill: spread capture + adverse selection (markouts at 100 ms, 1s, 10s, 60s) + terminal + rebates − fees.
   - **The statistical unit is the expiry, not the fill.**
6. **Deribit 0DTE IV as a forecast of BRTI realized vol to 08:00 UTC.** No published result exists.

---

## 8. Prototype and data stack

**Repo layout (Python, `.venv`, pytest; open in VS Code):**
```
src/pinpricer/
  feeds/      coinbase, kraken, bitstamp, gemini... L2 WS → BRTI replica; binance perp lead; deribit DVOL/chain
  index.py    BRTI replica (200 ms) + 60s settlement accumulator
  vol.py      RV, HAR, seasonal factors (ET-indexed), event calendar, DVOL blend
  dist.py     Student-t / FHS terminal distribution, averaging adjustment
  contracts.py ladder, bucket, up/down, touch (MC) payoffs from one distribution
  quote.py    reservation price, pick-off-aware size, ladder coherence projection
  risk.py     payoff-vector book, limits, kill-switch checks
  venues/     kalshi (REST + signed WS), polymarket (gamma/clob)
tests/        put-call-style invariants: monotone ladder, buckets sum to 1, τ→0 convergence,
              averaging formula vs Monte Carlo, t-limit → normal as ν→∞
notebooks/    calibration study, ablation, live model-vs-book dashboard
```

**Data (verified working from a US IP):**
- **Kalshi REST, no auth:** `/series`, `/events`, `/markets` (with `expiration_value`), orderbook, trades, and 1m candlesticks. The `/historical/*` archive goes back to about Nov 2024 for KXBTCD and Dec 2025 for KXBTC15M.
- **Kalshi WS:** needs a signed API key. The `cfbenchmarks_value` BRTI stream needs an entitlement; get a key and test it early.
- **Spot L2, no keys:** Coinbase Advanced Trade, Kraken v2, Bitstamp, OKX, Bybit.
- **Binance:** `api.binance.com` is geo-blocked (HTTP 451). Use `data-stream.binance.vision`, `fstream.binance.com`, and the bulk files on **data.binance.vision** (1s klines, aggTrades).
- **Deribit, public:** DVOL, option chain, history.
- **Tardis.dev:** the first day of every month is free.
- **Polymarket:** Gamma (`tag_slug=15M`), CLOB `prices-history` (fidelity=1), Data API trades, public market WS. Reading data is fine; US trading is geoblocked.
- **Gotchas:**
  - DST ends 2026-11-01. Parse `close_time` in UTC and never from the ticker.
  - The Mac's python.org Python is missing CA certificates. Run "Install Certificates.command" or use certifi.

**Memo for Ben (4–6 pages):**
- Thesis
- Settlement mechanics (the crypto-specific part)
- The fair-value stack, with ablation numbers
- The quoting/risk design
- Where the edge is, and how PinPredict wins an LP slot
- Calibration results from the prototype
- Next steps and costs (data licenses, colocation, feeds)

---

## 9. Open items to verify before writing the memo
- The Kalshi fee schedule PDF: the 0.07 taker coefficient, and whether KXBTC15M has maker fees.
- Whether a basic Kalshi account gets the `cfbenchmarks_value` entitlement.
- Polymarket US: settlement source and open convention, fees, and API.
- Who holds Kalshi's crypto LP slots, and what the auction terms are.
- Re-check every **[D]** number on BRTI-proxy data, not only Binance USDT. Re-derive the Var_h, pick-off and averaging formulas by Monte Carlo inside the test suite.

---

## 10. Key sources
- Kalshi contract terms: https://assets.kalshi.com/contract_terms/CRYPTO.pdf · BTC.pdf · BTCMINMAX.pdf
- Kalshi API and docs: https://docs.kalshi.com/llms.txt · /websockets/cfbenchmarks-value · /getting_started/historical_data · /getting_started/rate_limits · /getting_started/order_groups
- Kalshi LP program: https://help.kalshi.com/en/articles/15410219-liquidity-provider-program
- CF Benchmarks RTI methodology: https://docs.cfbenchmarks.com/CME%20CF%20Real%20Time%20Indices%20Methodology.pdf
- Polymarket fees, rebates and changelog: https://docs.polymarket.com/trading/fees · /market-makers/maker-rebates · /changelog
- Dai, Jia & Yu, *Settlement Manipulation in Prediction Markets* (2026): https://arxiv.org/abs/2606.31675
- Young, *OpenMarket* Polymarket–Binance dataset (2026): https://arxiv.org/abs/2607.26245
- Feil & Nendel, *Optimal Market Making in Prediction Markets* (2026): https://arxiv.org/abs/2607.17991
- Bürgi, Deng & Whelan, *Makers and Takers* (Kalshi): https://www.karlwhelan.com/Papers/Kalshi.pdf
- Telonex 15m wallet study: https://telonex.io/research/top-crypto-traders-polymarket-15m
- ladderbook (Kalshi BTC ladder MM research): https://github.com/owen-alderson/ladderbook
- edgebook pre-registered null test: https://github.com/milesiscool/edgebook/pull/31
- Corsi (2009) HAR; Andersen & Bollerslev (1997) intraday seasonality; Broadie, Glasserman & Kou (1997) discrete barriers; Budish, Cramton & Shim (2015) latency arbitrage; Cartea et al. (2023) toxic flow
