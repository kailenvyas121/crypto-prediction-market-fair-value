# Glossary

Plain definitions of the crypto and pricing terms used in this repo.

| Term | Meaning |
|---|---|
| **Basis** | The gap between two prices of the same asset, e.g. a perp vs spot, or Binance BTC/USDT vs BRTI. Measured in basis points |
| **Basis point (bp)** | 0.01%. On BTC at $80,000, 1 bp is $8 |
| **Beta (β)** | How much a coin moves per 1% move in BTC. ETH's beta is about 1.2 |
| **Brier score** | Mean squared error of a probability against the 0/1 outcome. Lower is better; the main accuracy score in this repo |
| **BRTI** | CME CF Bitcoin Real Time Index, published by CF Benchmarks. Built from seven USD exchanges, computed every 200 ms. Kalshi settles on a 60-second average of it |
| **Chainlink** | A data network that publishes price feeds. Polymarket's short crypto markets settle on its BTC/USD streams |
| **Digital option** | Pays a fixed amount if a condition is met and nothing otherwise. Prediction contracts are digitals |
| **DVOL** | Deribit's 30-day implied-volatility index for BTC, the crypto counterpart of the VIX |
| **Fair value** | The probability the contract pays, measured so a market maker could defend and hedge it |
| **Fat tails / kurtosis** | Large moves happen more often than a normal distribution predicts. Excess kurtosis measures how much more |
| **Funding rate** | A periodic payment between perp longs and shorts that keeps the perp near spot. Positive means longs pay |
| **HAR** | Heterogeneous autoregressive model: forecasts volatility from realized volatility over several past windows (here 1h, 24h, 7d) |
| **Implied volatility (IV)** | The volatility that makes an option model match the option's market price |
| **Kill switch** | An automatic rule that pulls all quotes when something goes wrong |
| **Ladder** | The set of "above K" contracts at many strikes for one expiry |
| **Liquidation** | A forced closing of a leveraged position when margin runs out. Liquidations can cascade |
| **Longshot / favorite-longshot bias** | Cheap contracts tend to be overpriced; bettors overpay for small chances |
| **Maker / taker** | A maker posts a resting order; a taker trades against it. On these Kalshi series only takers pay fees |
| **Markout** | How the market price moved after a fill, from the maker's side. Negative markouts mean the maker was picked off |
| **Mid** | The midpoint between the best bid and best ask |
| **Open interest (OI)** | The number of open perp or futures contracts. It measures leverage, not direction |
| **Out of sample** | Scored on data the model never saw while being fit. Every result here is out of sample unless stated |
| **Perpetual future (perp)** | A futures contract with no expiry, kept near spot by funding. Most crypto volume and leverage sits in perps |
| **Pick-off** | When a faster trader takes a resting quote that the latest price has made stale |
| **Realized volatility** | Volatility measured from actual price moves, here from one-minute returns |
| **Risk-neutral** | Probabilities implied by hedgeable prices (e.g. options), which include risk premia |
| **Settlement index** | The exact price a contract settles on. It must be the price you model |
| **Skew** | The difference in implied volatility between downside and upside options. It shows where tail risk is priced |
| **Spread capture** | What a maker earns from the bid-ask spread: the fill price versus the mid |
| **Student-t distribution** | A bell curve with fatter tails than the normal. ν (degrees of freedom) controls the fatness; ν ≈ 4 fits BTC |
| **Touch / barrier** | A contract that pays if the price reaches a level at any time before expiry |
| **TWAP** | Time-weighted average price over a window |
| **USDT** | Tether, a dollar stablecoin. BTC/USDT prices differ slightly from BTC/USD |
