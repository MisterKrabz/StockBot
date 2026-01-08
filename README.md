# Reinforcement Learning Swing Trading Bot (RLST)

## Overview

This project is a trading system that uses **reinforcement learning (RL)** to manage a portfolio of large-cap U.S. stocks. The bot trades on a **long-only basis**, makes decisions every **10 minutes**, and allocates capital across multiple stocks in a way similar to a disciplined portfolio manager or swing trader.

Rather than hard-coding entry/exit rules, the system learns *when* and *how much* to allocate to each stock based on market conditions, recent price behavior, macro context, news pressure, and its own portfolio state.

This is not a high-frequency trading system and does not attempt to compete on speed or latency.

---

## Setup

1. **clone this repository**
   - in the terminal, navigate to your intended workspace
   - run "git clone https://github.com/MisterKrabz/StockBot"

2. **install dependencies**
   - activate a conda environment
   - run "pip install -r requirements.lock.txt"

3. **set up your env**
   - collaborators should have access to our communal env file from the google drive
   - non collaborators should read through the .env.example file and obtain their own API keys 

---

## Core Trading Philosophy

The bot is designed to behave like a **systematic swing portfolio manager**, not a scalper or day trader. Concretely, that means:

- Decisions are made at **fixed 10-minute intervals**
- Positions are typically held for **hours to days**
- Capital is rotated toward relative strength and favorable regimes
- Risk and volatility are explicitly considered
- Overtrading is actively discouraged

The model is allowed to hold cash when conditions are unfavorable.

---

## High-Level Architecture

The system is composed of five main layers:

1. **Data Ingestion**
   - Collects market, news, macro, and corporate-event data
   - Uses only free APIs
   - Caches data locally to respect rate limits

2. **State Construction**
   - Converts raw data into numerical features
   - Encodes short-term behavior and longer-term context
   - Includes portfolio state (holdings, cash, PnL)

3. **Reinforcement Learning Environment**
   - Advances in fixed 10-minute steps
   - Simulates portfolio evolution
   - Computes rewards from realized PnL

4. **Learning System**
   - Uses Proximal Policy Optimization (PPO)
   - Employs a recurrent (LSTM) policy to emphasize recent data
   - Trains continually using rolling updates

5. **Execution (Paper Trading)**
   - Converts portfolio weights into integer share orders
   - Executes via Alpaca paper trading
   - Logs all decisions and outcomes

---

## Trading Universe and Constraints

- **Fixed universe** of large-cap stocks
- **Long-only**
- No leverage
- No short selling
- Portfolio weights must be feasible given available cash
- Orders are placed in whole shares

The fixed universe simplifies learning, reduces leakage risk, and keeps behavior interpretable.

---

## Time and Context Handling

Although the bot acts every 10 minutes, it sees **much more than just the last candle**.

The observation includes:
- Very recent behavior (last few hours)
- Medium-term context (1–5 days)
- Broader regime indicators (weeks)

Recent information naturally carries more weight through:
- Rolling features
- Recurrent memory (LSTM)
- Training procedures that emphasize newer data

The model is not fed raw price time series; instead, it receives normalized, scale-invariant numerical summaries.

---

## Learning Approach

The system uses **reinforcement learning**

At every 10-minute step:
1. The agent observes the current state
2. It outputs target portfolio weights
3. Trades are executed (paper)
4. After the next step, the system computes a reward based on realized PnL

The agent continuously evaluates its past decisions and updates itself using recent experience.

To maintain stability in ever changing markets:
- Rewards include transaction costs
- Turnover is penalized
- Model updates are batched (not every single step)

---

## Data Sources (Free Only)

This project intentionally avoids paid or proprietary data.

| Source | Purpose |
|------|--------|
| Alpaca | Market prices and paper trading |
| GDELT | News volume and timing |
| FRED | Daily macroeconomic indicators |
| SEC EDGAR | Corporate filings and event signals |

All data must be timestamped and used in a leakage-safe manner.

---

## Disclaimer

This project is for **educational and research purposes only**.  
All trading is performed using paper accounts.  
Nothing in this repository constitutes investment advice.

---

For a more detailed look, read the **Design Specification** document. 
