# ingestion/storage/schemas.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List

@dataclass(frozen=True)
class BarsSchema:
    # Normalized schema for OHLCV bars
    columns: List[str] = (
        "symbol", "timestamp",
        "open", "high", "low", "close",
        "volume", "trade_count", "vwap",
        "timeframe", "source"
    )

    dtypes: Dict[str, str] = None  # assigned in __post_init__ if needed


@dataclass(frozen=True)
class FredSchema:
    columns: List[str] = ("series_id", "date", "value", "source")


@dataclass(frozen=True)
class SecFilingsSchema:
    columns: List[str] = ("cik", "symbol", "filing_date", "filing_datetime", "form", "accession", "source")


@dataclass(frozen=True)
class GdeltNewsSchema:
    columns: List[str] = (
        "symbol", "publish_datetime", "source_domain", "url",
        "tone", "themes", "source"
    )
