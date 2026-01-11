from __future__ import annotations

"""
Bulk data ingestion from Stooq historical data.

This module reads 5-minute OHLCV bar data from Stooq bulk downloads,
resamples to 10-minute bars, and writes to partitioned Parquet files
for RL training pipelines.

Usage:
    python -m ingestion.bulk.stooq_bars
    
Or with custom config:
    from ingestion.bulk.stooq_bars import bulk_convert_stooq_to_parquet, BulkConfig
    cfg = BulkConfig(stooq_5min_dir=Path("./my_data"))
    bulk_convert_stooq_to_parquet(cfg)
"""

import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas as pd

from ingestion.storage.writers import ParquetWriter, ensure_utc_timestamp
from ingestion.storage.schemas import BarsSchema


# --------------------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class BulkConfig:
    """Configuration for bulk Stooq data ingestion."""
    
    # Where you downloaded Stooq bulk data to (zip or directory)
    stooq_5min_zip: Optional[Path] = None
    stooq_5min_dir: Optional[Path] = Path("./data/raw/stooq/us_5min")

    # Where your Parquet datasets live
    parquet_base_dir: Path = Path("./data/parquet")

    # Where to write bars dataset under parquet_base_dir
    bars_dataset_subdir: str = "bars"

    # Path to tickers CSV (same folder as this script by default)
    tickers_csv: Path = Path(__file__).with_name("tickers.csv")

    # Resample target
    target_timeframe: str = "10min"
    
    # Continue processing even if some tickers fail
    continue_on_error: bool = True
    
    # Verbose logging
    verbose: bool = True


BARS_COLS = list(BarsSchema().columns)


# --------------------------------------------------------------------------------------
# TICKERS
# --------------------------------------------------------------------------------------

def load_tickers(csv_path: Path) -> tuple[str, ...]:
    """
    Read tickers from a CSV with a header like:
      symbol
      AAPL.US
      SPY.US
      XLK.US
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Tickers CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    if "symbol" not in df.columns:
        raise ValueError(f"Tickers CSV must have a 'symbol' column. Found: {list(df.columns)}")

    symbols = (
        df["symbol"]
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .unique()
        .tolist()
    )

    if not symbols:
        raise ValueError(f"No symbols found in {csv_path}")

    return tuple(s.upper() for s in symbols)


# --------------------------------------------------------------------------------------
# HELPERS
# --------------------------------------------------------------------------------------

def _read_stooq_csv(path: Path) -> pd.DataFrame:
    """
    Read a Stooq-style OHLCV CSV and return:
      timestamp, open, high, low, close, volume
    Defensive parsing: Stooq bulk formats can vary.

    Common columns:
      Date, Time, Open, High, Low, Close, Volume
    or:
      datetime, open, high, low, close, volume
    """
    df = pd.read_csv(path)

    # Normalize column names
    df.columns = [c.strip().lower() for c in df.columns]

    # Detect datetime
    if "datetime" in df.columns:
        ts = pd.to_datetime(df["datetime"], errors="coerce", utc=True)
    elif "date" in df.columns and "time" in df.columns:
        ts = pd.to_datetime(df["date"].astype(str) + " " + df["time"].astype(str), errors="coerce", utc=True)
    elif "date" in df.columns:
        ts = pd.to_datetime(df["date"], errors="coerce", utc=True)
    else:
        raise ValueError(f"Cannot find datetime columns in {path.name}. cols={list(df.columns)}")

    df["timestamp"] = ts
    df = df.dropna(subset=["timestamp"])

    # Normalize OHLCV columns
    rename_map = {
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
        "vol": "volume",
    }
    for k, v in rename_map.items():
        if k in df.columns and v not in df.columns:
            df[v] = df[k]

    required = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing OHLCV cols {missing} in {path.name}. cols={list(df.columns)}")

    # Coerce numeric
    for c in required:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.dropna(subset=required)

    return df[["timestamp", "open", "high", "low", "close", "volume"]].copy()


def _infer_symbol_from_filename(path: Path) -> str:
    """
    Expect files named like AAPL.US.csv (or aapl.us.csv). We use the stem as the symbol.
    """
    return path.stem.upper()


def _resample_to_10m(df_5m: pd.DataFrame) -> pd.DataFrame:
    """
    Resample 5-minute bars into 10-minute bars.
    """
    df = df_5m.sort_values("timestamp").set_index("timestamp")

    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }

    out = df.resample("10min", label="left", closed="left").agg(agg)
    out = out.dropna(subset=["open", "high", "low", "close"])
    out = out.reset_index()

    return out


def _to_bars_schema(
    symbol: str, 
    bars: pd.DataFrame, 
    timeframe: str, 
    source: str,
    feed: str = "bulk"
) -> pd.DataFrame:
    """
    Convert normalized OHLCV to BarsSchema format.
    
    Args:
        symbol: Stock ticker (e.g., "AAPL.US")
        bars: DataFrame with timestamp, open, high, low, close, volume
        timeframe: Bar duration ("10min", "1hour", etc.)
        source: Data provider ("stooq", "alpaca", etc.)
        feed: Data feed type ("bulk", "IEX", "SIP", etc.)
        
    Returns:
        DataFrame conforming to BarsSchema with date partition column
    """
    df = bars.copy()
    df["symbol"] = symbol
    df["timeframe"] = timeframe
    df["source"] = source
    df["feed"] = feed  # New: track data feed type

    # Fields Alpaca provides but bulk OHLCV typically does not:
    df["trade_count"] = pd.NA
    df["vwap"] = pd.NA

    # Ensure UTC timestamp
    df = ensure_utc_timestamp(df, "timestamp")

    # Partition helper - used for Hive-style partitioning
    df["date"] = df["timestamp"].dt.date.astype(str)

    # Ensure all BarsSchema columns exist
    for c in BARS_COLS:
        if c not in df.columns:
            df[c] = pd.NA

    return df[BARS_COLS + ["date"]]


# --------------------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------------------

def bulk_convert_stooq_to_parquet(cfg: BulkConfig) -> dict:
    """
    Main entry point: read all tickers from CSV, process Stooq data, write to Parquet.
    
    Args:
        cfg: BulkConfig with paths and settings
        
    Returns:
        dict with stats: {"processed": int, "failed": int, "rows": int, "symbols": list}
    """
    symbols = load_tickers(cfg.tickers_csv)
    wanted: Set[str] = set(s.upper() for s in symbols)
    
    if cfg.verbose:
        print(f"📋 Loaded {len(wanted)} tickers from {cfg.tickers_csv}")
        print(f"   First 10: {sorted(wanted)[:10]}...")

    writer = ParquetWriter(base_dir=cfg.parquet_base_dir)

    # If zip provided, extract it
    extract_dir: Optional[Path] = None
    if cfg.stooq_5min_zip:
        if cfg.verbose:
            print(f"📦 Extracting zip: {cfg.stooq_5min_zip}")
        extract_dir = Path("./data/tmp/stooq_extract")
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(cfg.stooq_5min_zip, "r") as zf:
            zf.extractall(extract_dir)
        source_dir = extract_dir
    else:
        if cfg.stooq_5min_dir is None:
            raise ValueError("Provide either stooq_5min_zip or stooq_5min_dir")
        source_dir = cfg.stooq_5min_dir

    if not source_dir.exists():
        raise FileNotFoundError(f"Stooq source_dir not found: {source_dir}")

    all_files = sorted([p for p in source_dir.rglob("*.csv")])
    if not all_files:
        raise FileNotFoundError(f"No CSV files found under {source_dir}")
    
    if cfg.verbose:
        print(f"📂 Found {len(all_files)} CSV files in {source_dir}")

    # Build index of available files by symbol
    file_by_symbol: dict[str, Path] = {}
    for csv_path in all_files:
        sym = _infer_symbol_from_filename(csv_path)
        if sym in wanted:
            file_by_symbol[sym] = csv_path
    
    # Report which tickers are missing
    missing_tickers = wanted - set(file_by_symbol.keys())
    if missing_tickers and cfg.verbose:
        print(f"⚠️  Missing {len(missing_tickers)} tickers: {sorted(missing_tickers)[:20]}...")

    out_batches: list[pd.DataFrame] = []
    processed = 0
    failed = 0
    failed_symbols: list[str] = []

    for sym, csv_path in sorted(file_by_symbol.items()):
        try:
            df_5m = _read_stooq_csv(csv_path)
            df_10m = _resample_to_10m(df_5m)

            bars_df = _to_bars_schema(
                symbol=sym,
                bars=df_10m,
                timeframe=cfg.target_timeframe,
                source="stooq",
                feed="bulk",
            )
            out_batches.append(bars_df)
            processed += 1
            
            if cfg.verbose and processed % 50 == 0:
                print(f"   Processed {processed} tickers...")
                
        except Exception as e:
            failed += 1
            failed_symbols.append(sym)
            if cfg.verbose:
                print(f"⚠️  Failed to process {sym}: {e}")
            if not cfg.continue_on_error:
                raise

    if not out_batches:
        raise RuntimeError(
            f"Found no matching symbol CSVs under {source_dir}. "
            f"wanted={sorted(wanted)[:10]}... "
            f"(Make sure filenames match tickers.csv, e.g. AAPL.US.csv)"
        )

    final = pd.concat(out_batches, ignore_index=True)

    writer.write_partitioned(
        df=final,
        dataset_subdir=cfg.bars_dataset_subdir,
        partition_cols=["symbol", "timeframe", "date"],
        dedup_subset=["symbol", "timestamp", "timeframe", "source"],
    )

    out_path = cfg.parquet_base_dir / cfg.bars_dataset_subdir
    unique_symbols = sorted(final["symbol"].unique())
    
    if cfg.verbose:
        print(f"\n✅ Wrote bars dataset to: {out_path}")
        print(f"   Total rows: {len(final):,}")
        print(f"   Symbols processed: {processed}")
        print(f"   Symbols failed: {failed}")
        if failed_symbols:
            print(f"   Failed symbols: {failed_symbols[:10]}...")
    
    return {
        "processed": processed,
        "failed": failed,
        "failed_symbols": failed_symbols,
        "rows": len(final),
        "symbols": unique_symbols,
        "output_path": str(out_path),
    }


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Stooq Bulk Data Ingestion")
    print("=" * 60)
    
    cfg = BulkConfig(
        # If you downloaded a zip, set this (and optionally set stooq_5min_dir=None):
        # stooq_5min_zip=Path("./data/raw/stooq/us_5min.zip"),

        # Or if you extracted/downloaded into a directory:
        stooq_5min_dir=Path("./data/raw/stooq/us_5min"),

        parquet_base_dir=Path("./data/parquet"),
        bars_dataset_subdir="bars",
        tickers_csv=Path(__file__).with_name("tickers.csv"),
        target_timeframe="10min",
        continue_on_error=True,
        verbose=True,
    )
    
    try:
        result = bulk_convert_stooq_to_parquet(cfg)
        print("\n" + "=" * 60)
        print("📊 Summary")
        print("=" * 60)
        print(f"   Output: {result['output_path']}")
        print(f"   Rows: {result['rows']:,}")
        print(f"   Symbols: {result['processed']}")
        if result['failed'] > 0:
            print(f"   Failed: {result['failed']}")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
