# ingestion/pipeline/backfill.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from ingestion.sources.alpaca.market import AlpacaMarketSource
from ingestion.sources.fred.macro import FredSource
from ingestion.sources.sec.filings import SecEdgarSource
from ingestion.sources.gdelt.news import GdeltSource
from ingestion.storage.writers import ParquetWriter


@dataclass
class BackfillConfig:
    universe_symbols: List[str]
    market_proxy: str = "SPY"
    sector_etfs: List[str] = None
    fred_series: List[str] = None
    symbol_to_cik: Dict[str, str] = None


class BackfillPipeline:
    def __init__(
        self,
        alpaca: AlpacaMarketSource,
        fred: FredSource,
        sec: SecEdgarSource,
        gdelt: GdeltSource,
        writer: ParquetWriter,
    ):
        self.alpaca = alpaca
        self.fred = fred
        self.sec = sec
        self.gdelt = gdelt
        self.writer = writer

    def run(
        self,
        cfg: BackfillConfig,
        start: datetime,
        end: datetime,
    ) -> None:
        sector = cfg.sector_etfs or []
        fred_series = cfg.fred_series or ["EFFR"]
        symbol_to_cik = cfg.symbol_to_cik or {}

        # 1) Market bars (hourly + 10min)
        symbols = sorted(set(cfg.universe_symbols + [cfg.market_proxy] + sector))
        for tf in ["10min", "1hour"]:
            bars = self.alpaca.fetch_bars(symbols=symbols, start=start, end=end, timeframe=tf)
            self.writer.write_partitioned(
                bars,
                dataset_subdir="bronze/alpaca/bars",
                partition_cols=["timeframe", "symbol"],
                dedup_subset=["timeframe", "symbol", "timestamp"],
            )

        # 2) FRED macro
        for sid in fred_series:
            df = self.fred.fetch_series_observations(
                series_id=sid,
                observation_start=start.date().isoformat(),
                observation_end=end.date().isoformat(),
            )
            self.writer.write_partitioned(
                df,
                dataset_subdir="bronze/fred/series",
                partition_cols=["series_id"],
                dedup_subset=["series_id", "date"],
            )

        # 3) SEC filings
        sec_rows = []
        for sym, cik in symbol_to_cik.items():
            try:
                submissions = self.sec.fetch_submissions(cik=cik)
                df = self.sec.extract_recent_filings(symbol=sym, cik=cik, submissions_json=submissions)
                if not df.empty:
                    sec_rows.append(df)
            except Exception:
                # Keep backfill resilient; log later
                continue

        if sec_rows:
            sec_df = pd.concat(sec_rows, ignore_index=True)
            self.writer.write_partitioned(
                sec_df,
                dataset_subdir="bronze/sec/filings",
                partition_cols=["symbol"],
                dedup_subset=["symbol", "accession"],
            )

        # 4) GDELT news (simple per-symbol query; can batch/optimize later)
        gdelt_rows = []
        for sym in cfg.universe_symbols:
            # Basic query; you can refine
            q = f'{sym} OR "{sym}"'
            try:
                news = self.gdelt.fetch_news(query=q, maxrecords=250)
                if not news.empty:
                    news["symbol"] = sym
                    gdelt_rows.append(news)
            except Exception:
                continue

        if gdelt_rows:
            gdelt_df = pd.concat(gdelt_rows, ignore_index=True)
            self.writer.write_partitioned(
                gdelt_df,
                dataset_subdir="bronze/gdelt/news",
                partition_cols=["symbol"],
                dedup_subset=["symbol", "url"],
            )
