# ingestion/sources/alpaca/market.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

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
    ) -> pd.DataFrame:
        """
        timeframe: "10min" or "1hour"
        """
        tf = self._map_timeframe(timeframe)
        client = self._client()

        req = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=tf,
            start=start,
            end=end,
            limit=10000,
        )
        bars = client.get_stock_bars(req).df

        if bars is None or bars.empty:
            return pd.DataFrame()

        # alpaca-py returns a MultiIndex (symbol, timestamp)
        bars = bars.reset_index()

        # Standardize columns
        bars.rename(columns={"timestamp": "timestamp"}, inplace=True)
        bars["timeframe"] = timeframe
        bars["source"] = "alpaca"

        # Ensure required columns exist
        for col in ["trade_count", "vwap"]:
            if col not in bars.columns:
                bars[col] = pd.NA

        bars = ensure_utc_timestamp(bars, "timestamp")

        # Keep a consistent set of columns
        keep = [
            "symbol", "timestamp",
            "open", "high", "low", "close",
            "volume", "trade_count", "vwap",
            "timeframe", "source",
        ]
        return bars[keep]

    @staticmethod
    def _map_timeframe(timeframe: str) -> TimeFrame:
        if timeframe == "10min":
            return TimeFrame.Minute(10)
        if timeframe == "1hour":
            return TimeFrame.Hour
        raise ValueError(f"Unsupported timeframe: {timeframe}")
