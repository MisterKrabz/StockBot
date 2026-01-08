# ingestion/sources/fred/macro.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

import pandas as pd
import requests


@dataclass
class FredSource:
    api_key: str
    base_url: str = "https://api.stlouisfed.org/fred"

    def fetch_series_observations(
        self,
        series_id: str,
        observation_start: str,
        observation_end: Optional[str] = None,
    ) -> pd.DataFrame:
        url = f"{self.base_url}/series/observations"
        params = {
            "api_key": self.api_key,
            "series_id": series_id,
            "file_type": "json",
            "observation_start": observation_start,
        }
        if observation_end:
            params["observation_end"] = observation_end

        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        j = r.json()
        obs = j.get("observations", [])

        rows = []
        for o in obs:
            rows.append(
                {
                    "series_id": series_id,
                    "date": o["date"],
                    "value": None if o["value"] == "." else float(o["value"]),
                    "source": "fred",
                }
            )
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        df["date"] = pd.to_datetime(df["date"]).dt.date
        return df
