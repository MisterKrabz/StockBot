# ingestion/storage/schemas.py
"""
Parquet schemas designed for reinforcement learning training pipelines.

Key design principles:
- Raw OHLCV data is stored as-is (no derived features like EMAs stored here)
- Derived features (EMAs, RSI, etc.) are computed at training time
- Schema includes metadata for data provenance (source, feed) for quality tracking
- All timestamps are UTC for consistency
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class BarsSchema:
    """
    Normalized schema for OHLCV bars - optimized for RL training.
    
    Core OHLCV columns:
      - symbol: Stock ticker (e.g., "AAPL")
      - timestamp: UTC datetime of bar open
      - open, high, low, close: Price data
      - volume: Trading volume
      
    Alpaca-provided extras (valuable for RL):
      - trade_count: Number of trades in bar (liquidity signal)
      - vwap: Volume-weighted average price (fair value estimate)
      
    Metadata:
      - timeframe: Bar duration ("10min", "1hour", etc.)
      - source: Data provider ("alpaca", "stooq", etc.)
      - feed: Data feed type ("IEX", "SIP", etc.) - for quality tracking
    """
    columns: Tuple[str, ...] = (
        "symbol", "timestamp",
        "open", "high", "low", "close",
        "volume", "trade_count", "vwap",
        "timeframe", "source", "feed"
    )

    # Pandas dtype hints for reading parquet efficiently
    dtypes: Dict[str, str] = None  # assigned in __post_init__ if needed


@dataclass(frozen=True)
class FredSchema:
    """Macroeconomic indicators from FRED API."""
    columns: Tuple[str, ...] = ("series_id", "date", "value", "source")


@dataclass(frozen=True)
class SecFilingsSchema:
    """SEC EDGAR filings metadata."""
    columns: Tuple[str, ...] = ("cik", "symbol", "filing_date", "filing_datetime", "form", "accession", "source")


@dataclass(frozen=True)
class GdeltNewsSchema:
    """News/sentiment data from GDELT."""
    columns: Tuple[str, ...] = (
        "symbol", "publish_datetime", "source_domain", "url",
        "tone", "themes", "source"
    )
