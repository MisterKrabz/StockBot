# ingestion/sources/sec/filings.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd
import requests


@dataclass
class SecEdgarSource:
    user_agent: str

    def fetch_submissions(self, cik: str) -> dict:
        cik_padded = cik.zfill(10)
        url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
        headers = {"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"}
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()

    def extract_recent_filings(self, symbol: str, cik: str, submissions_json: dict) -> pd.DataFrame:
        recent = submissions_json.get("filings", {}).get("recent", {})
        if not recent:
            return pd.DataFrame()

        n = len(recent.get("form", []))
        rows = []
        for i in range(n):
            filing_date = recent["filingDate"][i]  # YYYY-MM-DD
            accession = recent["accessionNumber"][i]
            form = recent["form"][i]
            # filingDate has day resolution; keep also a datetime for easier merging
            rows.append(
                {
                    "cik": cik,
                    "symbol": symbol,
                    "filing_date": filing_date,
                    "filing_datetime": f"{filing_date}T00:00:00Z",
                    "form": form,
                    "accession": accession,
                    "source": "sec",
                }
            )

        df = pd.DataFrame(rows)
        df["filing_date"] = pd.to_datetime(df["filing_date"]).dt.date
        df["filing_datetime"] = pd.to_datetime(df["filing_datetime"], utc=True)
        return df
