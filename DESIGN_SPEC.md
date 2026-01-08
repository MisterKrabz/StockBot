# Reinforcement Learning Portfolio Swing Trading System  
## Design Specification (Fixed Universe, Long-Only, 10-Minute Cadence)

---

## 1. Purpose and Scope

This document defines the architecture, data sources, learning framework, and operational behavior of a reinforcement-learning-based portfolio trading system. The system is designed to trade large-cap U.S. equities on a **long-only basis**, making allocation decisions every **10 minutes**, while maintaining swing-trading discipline.

The primary goal is to construct a system that behaves like a disciplined portfolio manager:
- Allocating capital across multiple stocks
- Emphasizing recent information while retaining broader context
- Avoiding excessive turnover
- Adapting continuously to new data without destabilizing learning

This specification intentionally avoids prescribing exact code implementations. Engineers are expected to exercise judgment while adhering to the constraints and principles described herein.

---

## 2. High-Level System Overview

The system consists of five major components:

1. **Data Ingestion Layer**  
   Collects and caches raw data from free external APIs.

2. **Feature and State Construction Layer**  
   Converts raw data into numerical observations suitable for reinforcement learning.

3. **Reinforcement Learning Environment**  
   Simulates portfolio evolution at a fixed 10-minute timestep.

4. **Learning and Optimization Layer**  
   Trains a policy using PPO with recurrent memory and recency weighting.

5. **Execution Layer (Paper Trading)**  
   Converts policy outputs into feasible share-based trades using Alpaca paper trading.

---

## 3. Trading Universe and Constraints

### 3.1 Universe Selection

- The system operates on a **fixed universe** of large-cap equities.
- The universe remains constant during training and inference.
- This design choice prioritizes stability, interpretability, and reduced leakage risk.

### 3.2 Trading Constraints

- Long-only (no short selling).
- No leverage.
- Portfolio weights must sum to ≤ 100%.
- Cash is an explicit state variable.
- Orders are executed in **integer shares**.
- Fractional portfolio weights are allowed internally, but are quantized before execution.

---

## 4. Decision Cadence and Temporal Design

### 4.1 Decision Frequency

- The agent makes **one decision every 10 minutes**.
- Decisions occur at the close of each 10-minute bar.
- Orders are assumed to execute at the next bar open (or equivalent conservative assumption).

### 4.2 Intrabar Behavior

- The agent does not make strategic decisions intrabar.
- Optional mechanical risk controls (e.g., stop-losses) may be enforced outside the policy.

This structure enforces swing-trading discipline and prevents overreaction to noise.

---

## 5. Observation (State) Design

The agent does not receive raw time series. Instead, it receives a **numerical state vector** that encodes temporal information through rolling statistics and summaries.

### 5.1 Multi-Timescale Context

To ensure recent data is weighted more heavily while preserving broader regime awareness, the state includes:

#### Short-Term Context (High Resolution)
- Last ~12 hours of information at 10-minute resolution
- Implemented via:
  - Rolling returns
  - Volatility measures
  - Micro-trend indicators

#### Medium- and Long-Term Context (Low Resolution)
- Aggregated features over:
  - 48 hours
  - 5 trading days
  - ~20 trading days
- Derived from hourly or daily data

This design ensures:
- Recent conditions dominate inference
- Longer-term regimes remain visible
- Input dimensionality remains tractable

---

## 6. Data Categories in the State Vector

### 6.1 Price and Return Information
- Percentage or log returns over multiple horizons
- Normalized trend distances (e.g., EMA ratios)
- Drawdown measures

Raw prices are explicitly excluded to avoid scale and non-stationarity issues.

### 6.2 Volatility and Risk Measures
- ATR as a percentage of price
- Rolling return volatility
- Volatility regime indicators

### 6.3 Relative Strength
- Stock returns relative to SPY
- Stock returns relative to sector proxies
- Optional cross-sectional ranking signals

### 6.4 Market Regime Indicators
- SPY returns and volatility
- Market breadth proxies
- Macro regime features derived from FRED data

### 6.5 Sector / Industry Information
- Sector or industry encoding (e.g., one-hot or proxy via sector ETFs)

### 6.6 News and Event Pressure
- News article counts over rolling windows (e.g., 1h, 4h, 24h)
- Aggregated sentiment or tone scores
- Event flags (e.g., recent SEC filings)

Raw text is not passed directly to the policy.

### 6.7 Portfolio State (Critical)
- Current portfolio weights
- Cash fraction
- Time in position
- Unrealized PnL
- Distance from entry

Without portfolio state, the agent cannot behave as a portfolio manager.

---

## 7. Data Sources and API Usage (Free Tier Only)

### 7.1 Market Data
- **Alpaca Market Data API**
- Used for:
  - 1-minute bars (aggregated to 10-minute and 1-hour)
  - Equity and ETF prices
- Free tier (IEX feed) is sufficient for the intended timeframe.

### 7.2 News Data
- **GDELT 2.x**
- Used for:
  - Article metadata
  - Timestamps
  - Source information
- Queried at controlled intervals and cached locally.

### 7.3 Macro Data
- **FRED API**
- Used for:
  - Daily macroeconomic series (e.g., effective federal funds rate)
- Retrieved once per day and forward-filled intraday.

### 7.4 Corporate Filings
- **SEC EDGAR**
- Used for:
  - Filing timestamps and form types
- Cached and refreshed conservatively to respect SEC access guidelines.

---

## 8. Rate Limiting and Refresh Strategy

### 8.1 Alpaca
- Batch requests where possible.
- Avoid unnecessary polling.

### 8.2 GDELT
- Cache query results.
- Avoid per-ticker per-step queries.

### 8.3 FRED
- Fetch once daily.
- Forward-fill values throughout the trading day.
- Do not decay values intraday.

### 8.4 SEC EDGAR
- Default: once-daily refresh for the full universe.
- Optional: intraday lightweight checks for held or candidate tickers.
- Filing impact decays naturally via time-since-event features, not manual intraday decay.

---

## 9. Reinforcement Learning Framework

### 9.1 Algorithm Choice

- **Proximal Policy Optimization (PPO)**
- Continuous action space
- Stable under noisy reward signals
- Well-supported in modern RL libraries

### 9.2 Policy Architecture

- PPO with **LSTM (recurrent policy)**
- LSTM enables:
  - Emphasis on recent observations
  - Implicit temporal weighting
  - Reduced need for explicit long sequences

---

## 10. Action Space

- The agent outputs **target portfolio weights** for each asset.
- Constraints enforced post-policy:
  - Long-only
  - Max weight per asset
  - Minimum cash buffer
  - Quantization to reasonable increments
- Weights are converted to **integer share orders** before execution.

---

## 11. Reward Function and Risk Control

### 11.1 Step-Level Reward

- Computed **every 10 minutes** based on:
  - Change in portfolio value
  - Net of transaction costs and slippage

### 11.2 Risk-Aware Adjustments
- Turnover penalties to discourage excessive trading
- Optional drawdown or volatility penalties
- These shape behavior without hardcoding rules

---

## 12. Continual Learning and Recency Weighting

### 12.1 Per-Step Evaluation

- At time *t+1*, the system evaluates the action taken at time *t*.
- This satisfies the requirement that the agent continuously assesses its recent decisions.

### 12.2 Batched Policy Updates

- PPO optimization is performed on a **rolling schedule**:
  - Recommended: hourly or end-of-day
- Updating strictly every 10 minutes is possible but discouraged initially due to variance.

### 12.3 Emphasizing Recent Data

Recent data is weighted more heavily via:
- Exponential decay in sampling
- Loss weighting by transition age
- Trailing training windows (e.g., last N trading days)
- Optional small anchor windows for stability

No manual intraday decay of macro or filing features is applied.

---

## 13. Training and Evaluation Methodology

- Train on multi-year historical data.
- Use walk-forward evaluation:
  - Train on earlier periods
  - Validate and test on later, unseen periods
- Train across multiple stocks simultaneously to avoid memorization.
- All evaluation is leakage-safe (as-of timestamps enforced).

---

## 14. Execution and Deployment (Paper Trading)

- Execution occurs via **Alpaca Paper Trading API**.
- Orders are submitted at decision times only.
- All actions, rewards, and portfolio states are logged.
- Model checkpoints are versioned and promoted only after sanity checks.

---

## 15. Non-Goals

This system explicitly does not:
- Perform high-frequency or tick-level trading
- Use leverage or short selling
- React intrabar to price movements
- Depend on paid data sources
- Rely on hand-coded entry/exit rules

---

## 16. Summary

This design specifies a disciplined, adaptive, reinforcement-learning-based portfolio trading system that:
- Operates at a 10-minute cadence
- Emphasizes recent information without discarding longer-term context
- Uses only free data sources
- Respects realistic execution and risk constraints
- Learns continuously while maintaining stability

All implementation decisions should adhere to the principles and constraints defined in this document.
