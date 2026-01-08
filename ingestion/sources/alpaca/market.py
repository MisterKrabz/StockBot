# ingestion/sources/alpaca/market.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.data.enums import DataFeed  # ✅ ADD: choose IEX vs SIP

from ingestion.storage.writers import ensure_utc_timestamp


@dataclass
class AlpacaMarketSource:
    api_key: str
    api_secret: str

    def _client(self) -> StockHistoricalDataClient:
        return StockHistoricalDataClient(self.api_key, self.api_secret)

    def fetch_bars(
        self,
        symbols: List[str],
        start: datetime,
        end: datetime,
        timeframe: str,
        feed: Optional[DataFeed] = None,  # ✅ optional override
    ) -> pd.DataFrame:
        """
        timeframe: "10min" or "1hour"

        On Alpaca free market data, you generally must use IEX for recent bars.
        If you request SIP without entitlement, Alpaca returns:
        "subscription does not permit querying recent SIP data".
        """
        tf = self._map_timeframe(timeframe)
        client = self._client()

        # ✅ Default to IEX for free plan compatibility
        if feed is None:
            feed = DataFeed.IEX

        req = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=tf,
            start=start,
            end=end,
            limit=10000,
            feed=feed,  # ✅ CRITICAL FIX
        )

        bars = client.get_stock_bars(req).df
        if bars is None or bars.empty:
            return pd.DataFrame()

        # alpaca-py returns a MultiIndex (symbol, timestamp)
        bars = bars.reset_index()

        # Standardize columns / metadata
        bars["timeframe"] = timeframe
        bars["source"] = "alpaca"
        bars["feed"] = str(feed)  # helpful for debugging/auditing

        # Ensure required columns exist consistently across feeds/timeframes
        for col in ["trade_count", "vwap"]:
            if col not in bars.columns:
                bars[col] = pd.NA

        bars = ensure_utc_timestamp(bars, "timestamp")

        keep = [
            "symbol", "timestamp",
            "open", "high", "low", "close",
            "volume", "trade_count", "vwap",
            "timeframe", "source", "feed",
        ]
        return bars[keep]

    @staticmethod
    def _map_timeframe(timeframe: str) -> TimeFrame:
        if timeframe == "10min":
            return TimeFrame(10, TimeFrameUnit.Minute)
        if timeframe == "1hour":
            return TimeFrame(1, TimeFrameUnit.Hour)
        raise ValueError(f"Unsupported timeframe: {timeframe}")
