# ingestion/sources/gdelt/news.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any

import time
import requests
import pandas as pd


@dataclass
class GdeltSource:
    base_url: str = "https://api.gdeltproject.org/api/v2/doc/doc"

    def fetch_news(
        self,
        query: str,
        maxrecords: int = 50,
        startdatetime: Optional[str] = None,  # YYYYMMDDHHMMSS
        enddatetime: Optional[str] = None,    # YYYYMMDDHHMMSS
        timeout_s: int = 30,
        retries: int = 3,
    ) -> pd.DataFrame:
        """
        Returns a DataFrame of article metadata. GDELT occasionally returns HTML/text
        (rate-limit / transient errors / "no data"). This function handles that.
        """
        params: Dict[str, Any] = {
            "query": query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": int(maxrecords),
            "sort": "hybridrel",
        }
        if startdatetime:
            params["startdatetime"] = startdatetime
        if enddatetime:
            params["enddatetime"] = enddatetime

        headers = {
            "User-Agent": "StockBotResearch/1.0 (contact: you@example.com)",
            "Accept": "application/json",
        }

        last_err: Optional[Exception] = None

        for attempt in range(1, retries + 1):
            try:
                r = requests.get(self.base_url, params=params, headers=headers, timeout=timeout_s)
                # Make HTTP failures explicit (429/500/etc)
                r.raise_for_status()

                # If content-type isn't JSON, don't parse it as JSON
                ctype = (r.headers.get("Content-Type") or "").lower()
                if "json" not in ctype:
                    snippet = r.text[:400].replace("\n", " ")
                    raise RuntimeError(
                        f"GDELT returned non-JSON (Content-Type={ctype}). "
                        f"Status={r.status_code}. BodySnippet={snippet}"
                    )

                j = r.json()

                # GDELT returns {"articles":[...]} when present; sometimes empty/missing
                articles = j.get("articles", []) or []
                if not articles:
                    return pd.DataFrame()

                df = pd.DataFrame(articles)

                # Standardize publish_datetime column
                if "seendate" in df.columns and "publish_datetime" not in df.columns:
                    df.rename(columns={"seendate": "publish_datetime"}, inplace=True)

                return df

            except Exception as e:
                last_err = e
                # backoff: 1s, 2s, 4s...
                if attempt < retries:
                    time.sleep(2 ** (attempt - 1))
                else:
                    break

        # Raise an error after retries
        raise RuntimeError(f"GDELT fetch_news failed after {retries} attempts: {last_err}") from last_err
