# ingestion/sources/gdelt/news.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import pandas as pd
import requests


@dataclass
class GdeltSource:
    base_url: str = "https://api.gdeltproject.org/api/v2/doc/doc"

    def fetch_news(
        self,
        query: str,
        maxrecords: int = 250,
        startdatetime: Optional[str] = None,  # YYYYMMDDHHMMSS
        enddatetime: Optional[str] = None,
    ) -> pd.DataFrame:
        params = {
            "query": query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": maxrecords,
            "sort": "HybridRel",
        }
        if startdatetime:
            params["startdatetime"] = startdatetime
        if enddatetime:
            params["enddatetime"] = enddatetime

        r = requests.get(self.base_url, params=params, timeout=30)
        r.raise_for_status()
        j = r.json()
        articles = j.get("articles", [])
        if not articles:
            return pd.DataFrame()

        rows = []
        for a in articles:
            rows.append(
                {
                    "publish_datetime": a.get("seendate"),  # format like 20250108123000
                    "source_domain": a.get("domain"),
                    "url": a.get("url"),
                    "tone": a.get("tone"),          # may be absent
                    "themes": a.get("themes"),      # may be list or string
                    "source": "gdelt",
                }
            )

        df = pd.DataFrame(rows)
        # Convert publish_datetime when available
        if "publish_datetime" in df.columns:
            # GDELT seendate is typically YYYYMMDDHHMMSS in UTC
            df["publish_datetime"] = pd.to_datetime(df["publish_datetime"], format="%Y%m%d%H%M%S", utc=True, errors="coerce")
        return df
