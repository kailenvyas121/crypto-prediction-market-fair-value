# Glossary

Plain definitions of the crypto and pricing terms used in this repo.

| Term | Meaning |
|---|---|
| **aggTrades** | Binance's trade-by-trade files, with nearby fills at one price merged |
| **Asian digital** | A digital option settled on an average price rather than a single print. Kalshi's 60-second settlement makes its contracts Asian digitals |
| **Basis** | The gap between two prices of the same asset, e.g. a perp vs spot, or Binance BTC/USDT vs BRTI. Measured in basis points |
| **Basis point (bp)** | 0.01%. On BTC at $80,000, 1 bp is $8 |
| **Beta (β)** | How much a coin moves per 1% move in BTC. ETH's beta is about 1.2 |
| **Brier score** | Mean squared error of a probability against the 0/1 outcome. Lower is better; the main accuracy score in this repo |
| **Brier × 1000** | Brier differences are tiny, so tables show them multiplied by 1,000. +0.3 means 0.0003 worse |
| **BRTI** | CME CF Bitcoin Real Time Index, published by CF Benchmarks. Built from seven USD exchanges, computed every 200 ms. Kalshi settles on a 60-second average of it |
| **Chainlink** | A data network that publishes price feeds. Polymarket's short crypto markets settle on its BTC/USD streams |
| **Contract-minute** | One contract observed at one minute; the unit of the accuracy tests |
| **Designated market maker / LP** | A firm with an agreement to quote continuously, often for rewards. Kalshi auctions liquidity-provider (LP) slots; SIG has been Kalshi's first designated market maker |
| **Digital option** | Pays a fixed amount if a condition is met and nothing otherwise. Prediction contracts are digitals |
| **DVOL** | Deribit's 30-day implied-volatility index for BTC, the crypto counterpart of the VIX |
| **EWMA** | Exponentially weighted moving average: recent observations count more. Used here for a fast realized-volatility estimate |
| **Fair value** | The probability the contract pays, measured so a market maker could defend and hedge it |
| **Fat tails / kurtosis** | Large moves happen more often than a normal distribution predicts. Excess kurtosis measures how much more |
| **Funding rate** | A periodic payment between perp longs and shorts that keeps the perp near spot. Positive means longs pay |
| **HAR** | Heterogeneous autoregressive model: forecasts volatility from realized volatility over several past windows (here 1h, 24h, 7d) |
| **Heartbeat / order groups** | Venue safety features. Polymarket cancels orders if a heartbeat stops; Kalshi order groups auto-cancel after a fill limit |
| **Implied volatility (IV)** | The volatility that makes an option model match the option's market price |
| **Kill switch** | An automatic rule that pulls all quotes when something goes wrong |
| **Ladder** | The set of "above K" contracts at many strikes for one expiry |
| **Liquidation** | A forced closing of a leveraged position when margin runs out. Liquidations can cascade |
| **Long/short ratio** | Share of an exchange's accounts, or of its top traders, that are net long perps |
| **Longshot / favorite-longshot bias** | Cheap contracts tend to be overpriced; bettors overpay for small chances |
| **Maker / taker** | A maker posts a resting order; a taker trades against it. On these Kalshi series only takers pay fees |
| **Markout** | How the market price moved after a fill, from the maker's side. Negative markouts mean the maker was picked off |
| **Mid** | The midpoint between the best bid and best ask |
| **Open interest (OI)** | The number of open perp or futures contracts. It measures leverage, not direction |
| **Out of sample** | Scored on data the model never saw while being fit. Every result here is out of sample unless stated |
| **Perpetual future (perp)** | A futures contract with no expiry, kept near spot by funding. Most crypto volume and leverage sits in perps |
| **Pick-off** | When a faster trader takes a resting quote that the latest price has made stale |
| **Position accountability** | Kalshi's per-member limit ($25k per strike) above which the exchange can ask about positions |
| **Realized volatility** | Volatility measured from actual price moves, here from one-minute returns |
| **Risk reversal (25-delta)** | Implied vol of 25-delta calls minus 25-delta puts; a standard measure of skew |
| **Risk-neutral** | Probabilities implied by hedgeable prices (e.g. options), which include risk premia |
| **Settlement index** | The exact price a contract settles on. It must be the price you model |
| **Skew** | The difference in implied volatility between downside and upside options. It shows where tail risk is priced |
| **Smearing** | A correction applied when converting a log-variance forecast back to variance, so the forecast isn't biased low |
| **Spread capture** | What a maker earns from the bid-ask spread: the fill price versus the mid |
| **Student-t distribution** | A bell curve with fatter tails than the normal. ν (degrees of freedom) controls the fatness; ν ≈ 4 fits BTC |
| **Taker ratio** | Aggressive buy volume divided by aggressive sell volume |
| **Touch / barrier** | A contract that pays if the price reaches a level at any time before expiry |
| **TWAP** | Time-weighted average price over a window |
| **USDT** | Tether, a dollar stablecoin. BTC/USDT prices differ slightly from BTC/USD |
| **Vol-of-vol** | How much volatility itself moves; it fattens tails and raises touch probabilities |
