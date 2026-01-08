# ingestion/pipeline/live_poll.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List

from ingestion.sources.alpaca.market import AlpacaMarketSource
from ingestion.storage.writers import ParquetWriter


@dataclass
class LivePollConfig:
    symbols: List[str]
    lookback_hours: int = 6  # fetch last 6 hours every poll
    timeframe: str = "10min"


class LivePollPipeline:
    def __init__(self, alpaca: AlpacaMarketSource, writer: ParquetWriter):
        self.alpaca = alpaca
        self.writer = writer

    def poll_once(self, cfg: LivePollConfig) -> None:
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=cfg.lookback_hours)

        bars = self.alpaca.fetch_bars(
            symbols=cfg.symbols,
            start=start,
            end=end,
            timeframe=cfg.timeframe,
        )
        self.writer.write_partitioned(
            bars,
            dataset_subdir="bronze/alpaca/bars",
            partition_cols=["timeframe", "symbol"],
            dedup_subset=["timeframe", "symbol", "timestamp"],
        )
