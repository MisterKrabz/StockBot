# ingestion/storage/writers.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

import pandas as pd


@dataclass(frozen=True)
class ParquetWriter:
    base_dir: Path

    def write_partitioned(
        self,
        df: pd.DataFrame,
        dataset_subdir: str,
        partition_cols: Sequence[str],
        dedup_subset: Optional[Sequence[str]] = None,
    ) -> Path:
        """
        Writes a Parquet dataset partitioned by partition_cols.
        Requires pyarrow installed (pandas uses it under the hood).
        """
        if df is None or df.empty:
            return self.base_dir / dataset_subdir

        out_dir = self.base_dir / dataset_subdir
        out_dir.mkdir(parents=True, exist_ok=True)

        df = df.copy()

        # Optional dedup inside the batch
        if dedup_subset:
            df = df.drop_duplicates(subset=list(dedup_subset), keep="last")

        # Use pandas built-in Parquet writer for dataset partitions
        df.to_parquet(
            out_dir,
            engine="pyarrow",
            index=False,
            partition_cols=list(partition_cols),
        )
        return out_dir


def ensure_utc_timestamp(df: pd.DataFrame, col: str) -> pd.DataFrame:
    df = df.copy()
    df[col] = pd.to_datetime(df[col], utc=True)
    return df
