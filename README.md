---
title: "Hybrid ML-First Trading System (Sentiment + Fundamentals + Price)"
output: github_document
---

## 0. What we are building (high-level)

We are building an **ML-first trading system** that:

1. Collects **time-stamped** market + alternative data (price/volume, bid-ask, news sentiment, social sentiment, fundamentals/filings).
2. Converts everything into **as-of features**: "What did we know at time *t*?"
3. Trains a model to output a **probabilistic forecast** over a chosen horizon (e.g., 1 day, 5 days, 60 minutes):
   - a central estimate (mean/median trajectory),
   - uncertainty (IQR / quantiles),
   - tail risk (bad-case quantiles).
4. Converts the forecast into trades using a **small, deterministic execution + risk layer**.

The ML model does the pattern recognition; the non-ML layer ensures safety + tradability.

---

## 1. Why we need the non-ML layer (even if we want "mostly ML")

Even if the model outputs a perfect forecast distribution, we still must decide:

- Which symbols are eligible to trade (liquidity, price floor, etc.)
- How much to buy/sell (position sizing)
- How to account for transaction costs (spread + slippage)
- Exposure limits (per-name, sector, total gross/net)
- Safety rules (max drawdown, stop trading conditions)

This "algorithmic code" is not optional. It is the seatbelt.

---

## 2. Data Sources (examples)

### 2.1 Market Data
- OHLCV candles at the target resolution (daily or intraday bars)
- Quotes / bid-ask (at least spread proxy)

### 2.2 News & News Sentiment
- Article timestamps + ticker tagging
- Sentiment score per article or aggregated per ticker per time bucket

### 2.3 Social / Investor Sentiment
- Social sentiment time series per ticker (e.g., StockTwits-like sources)

### 2.4 Fundamentals / Financial Statements
- Income statement / balance sheet / cash flow
- **Critical:** attach to dates using the *release/filing time* (as-of), not period-end.

---

## 3. The most important concept: "as-of" feature alignment (no leakage)

### The rule
At time `t`, the feature set must only include information published **at or before** `t`.

Common leakage bugs:
- Using fundamentals as if they were known at quarter end (they are known at filing/release time).
- Using revised datasets without "as originally reported" history.
- Building labels then accidentally letting future prices influence features.

We enforce "as-of joins" so each row represents:
`(symbol, time t) -> features known by time t -> label from future prices`

---

## 4. Dataset design

Each training row is:

- **Index:** (symbol i, time t)
- **Inputs X(i,t):**
  - price/volume/volatility features
  - bid-ask / liquidity proxies
  - aggregated news sentiment in a recent window (e.g., past 24h)
  - aggregated social sentiment (e.g., past 24h)
  - fundamentals (as-of last filing date)
  - market regime features (SPY trend, volatility index proxy, etc.)
- **Label y(i,t):** future outcome over horizon H

### Label options
- Regression: forward return over horizon H
- Classification: probability forward return > threshold
- Ranking: cross-sectional rank of forward return

We prefer **probabilistic outputs**:
- Predict multiple quantiles (e.g., 10/50/90th percentile),
- Then compute IQR, downside risk, etc.

---

## 5. Model: probabilistic forecasting (what the model outputs)

Instead of outputting a single "BUY/SELL", the model outputs a distribution summary:

- `q10(i,t)`: pessimistic outcome (10th percentile)
- `q50(i,t)`: median outcome
- `q90(i,t)`: optimistic outcome

From this we derive:
- **Expected value proxy:** q50 (or mean)
- **Uncertainty:** (q75 - q25) or (q90 - q10)
- **Downside risk:** q10

This makes the system more robust than a single-point forecast.

---

## 6. Training & evaluation (how we avoid fooling ourselves)

### 6.1 Walk-forward validation (time-based splits)
We never shuffle randomly.
We do rolling windows:

- Train: years A..B
- Validate: year B+1
- Test: year B+2
- Roll forward and repeat

### 6.2 Cost-aware backtesting
We simulate:
- buys execute closer to ask,
- sells execute closer to bid,
- plus slippage assumptions.

A model that "works" only at mid-price is not tradable.

### 6.3 Monitoring for regime drift
Markets change.
We track:
- feature drift,
- prediction confidence,
- live vs expected error,
- drawdown triggers.

---

## 7. Trading policy (minimal deterministic layer)

Given the forecast distribution per symbol:

1. Compute a **score**:
   - e.g., `score = q50 - cost_estimate - risk_penalty * uncertainty`
2. Filter:
   - `q10` must be above a downside threshold (avoid ugly tails)
   - liquidity and spread constraints
3. Construct portfolio:
   - pick top N symbols by score (and/or short bottom N if allowed)
   - size positions by confidence (smaller when
  

## 8. Problems we may encounter: 
 1. data leakage - we must train the underlying models based on what we know at time *t* to avoid exposing the model to future data. If we expose the model to future data then it will have unexpected inference performance. 


