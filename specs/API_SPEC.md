# External Data APIs and Feature Extraction Specification
**Free-Tier Only · Leakage-Safe · Swing-Trading Oriented**


## 1. Market Price, Volume, Trend, and Volatility Data

### API
**Alpaca Market Data API (Free Plan)**  
**Provider:** Alpaca Markets  
**Documentation:** https://docs.alpaca.markets  

### Data Extracted
Hourly OHLCV bars for:
- Each stock in the fixed trading universe
- SPY (market proxy)
- Relevant sector ETFs (e.g., XLK, XLF, XLV, XLE)

This data is available on Alpaca’s free market data tier (IEX feed). No SIP-only or paid features are required.

### Call Frequency
- **Historical backfill:** once per symbol per backfill run
- **Live / inference:** once per hour per symbol (batched requests)
- Data is cached locally and reused for training and inference

### Derived Features (Computed Locally)

**Trend and Structure**
- EMA stack (fast / medium / slow EMAs)
- EMA ratio–based trend state

**Volatility**
- ATR (Average True Range)
- ATR as a percentage of price

**Trend Strength**
- ADX (Average Directional Index)

**Liquidity**
- Dollar volume
- Volume z-score relative to a rolling baseline

**Market and Sector Context**
- Relative return vs SPY over multiple windows (e.g., 6h, 24h, 5d)
- Relative return vs sector ETF
- Rolling beta estimate vs SPY (computed from returns; no external beta API)

### Weighting / Time Sensitivity
- Recent returns and volatility are emphasized implicitly via rolling windows
- No manual decay is applied; temporal relevance is learned by the model

---

## 2. Execution, Portfolio State, and Fill Feedback

### API
**Alpaca Trading API (Paper Trading)**  
**Provider:** Alpaca Markets  
**Documentation:** https://docs.alpaca.markets  

### Data Extracted
- Account equity
- Buying power
- Open positions
- Orders
- Executed fills (price, quantity, timestamp)

### Call Frequency
- **Account / positions:** once per decision step
- **Orders:** only when trades are submitted
- **Fills:** polled after order submission or via order status checks

### Purpose in the System
This data is treated as **portfolio state**, not market signal:
- Current exposure
- Position sizing
- Cash constraints
- Realized and unrealized PnL
- Risk limits and logging

This enables a closed-loop paper trading system with realistic execution feedback.

---

## 3. Real-Time News Flow and Information Pressure

### API
**GDELT 2.x (Global Database of Events, Language, and Tone)**  
**Provider:** The GDELT Project  
**Documentation:** https://www.gdeltproject.org  

### Data Extracted
From the GDELT document APIs:
- Article URLs
- Publish timestamps
- Source domains
- Themes
- GDELT-provided tone / sentiment-style metadata

No full-text scraping is required. No API key is required.

### Call Frequency
- **Live:** every 10–15 minutes (aligned with GDELT update cadence)
- **Training:** queried historically and cached
- Results are cached locally to avoid repeated calls

### Derived Features
- **News intensity**
  - Count of relevant articles in last 1h / 4h / 24h
- **Aggregated tone / sentiment**
  - Mean or weighted mean over the same windows
- **Source-weighted sentiment**
  - Higher weights assigned to trusted or historically reliable domains

### Leakage Control
- Only articles with `publish_timestamp ≤ bar_close_time` are included
- Future articles are never visible to the model

### Weighting / Time Sensitivity
- Shorter windows (1h, 4h) naturally carry more influence
- No additional manual decay beyond windowing

---

## 4. Earnings and Filing Event Risk

### API
**SEC EDGAR APIs**  
**Provider:** U.S. Securities and Exchange Commission  
**Endpoint:** https://data.sec.gov  

### Data Extracted
- Filing timestamps
- Filing form types (e.g., 8-K, 10-Q, 10-K)

No API key is required. A descriptive User-Agent header is mandatory.

### Call Frequency
- **Universe-wide scan:** once per day
- **Optional intraday refresh:** limited to held or high-priority tickers
- Results are cached aggressively

### Derived Features
- `recent_8k` flag (binary, within N days)
- `hours_since_last_filing`
- Optional heuristic detection of earnings-related 8-K filings

### Weighting / Time Sensitivity
- Filing impact is modeled via `time_since_event`
- No intraday decay; relevance decreases naturally as time-since increases

---

## 5. Macro and Interest Rate Regime Data

### API
**FRED API (Federal Reserve Economic Data)**  
**Provider:** Federal Reserve Bank of St. Louis  
**Documentation:** https://fred.stlouisfed.org  

### Data Extracted
Daily macroeconomic time series:
- **EFFR (Effective Federal Funds Rate)**

Optional (also free):
- SOFR
- Treasury yield spreads (e.g., 10y–2y)

### Call Frequency
- **Once per day** (pre-market or at a fixed morning time)
- Values are forward-filled across all intraday bars for that date

### Derived Features
- Rate level
- 5-day rate change
- 20-day rate trend

### Leakage and Revisions (Optional Strict Mode)
- FRED real-time/vintage parameters can be used to request data “as-of” a historical date
- This is optional and supported on the free API

### Weighting / Time Sensitivity
- No intraday decay
- Optional `hours_since_macro_update` feature may be included

---

## 6. Summary of API Usage (Free Tier Compliance)

| API | Free Tier Used | Authentication | Typical Call Frequency |
|----|---------------|----------------|------------------------|
| Alpaca Market Data | Yes | API Key | Hourly (batched) |
| Alpaca Trading (Paper) | Yes | API Key | Per decision step |
| GDELT | Yes | None | Every 10–15 minutes |
| SEC EDGAR | Yes | User-Agent | Daily (+ optional hourly for subset) |
| FRED | Yes | API Key | Once per day |

All features listed above are fully compatible with free access and do not rely on paid or restricted endpoints.

---
