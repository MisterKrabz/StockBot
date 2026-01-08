from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from config.settings import (
    ALPACA_API_KEY_ID,
    ALPACA_API_SECRET_KEY,
    FRED_API_KEY,
    SEC_USER_AGENT,
)

from ingestion.sources.alpaca.market import AlpacaMarketSource
from ingestion.sources.fred.macro import FredSource
from ingestion.sources.sec.filings import SecEdgarSource
from ingestion.sources.gdelt.news import GdeltSource


def _print_df(title: str, df: pd.DataFrame, n: int = 8) -> None:
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)
    if df is None or df.empty:
        print("(empty)")
        return
    with pd.option_context("display.width", 160, "display.max_columns", 60):
        print(df.head(n))
    print(f"\nrows={len(df)}")
    print(f"cols={list(df.columns)}")


def _assert_has_cols(df: pd.DataFrame, cols: list[str], name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise AssertionError(f"{name}: missing columns {missing}. Found cols={list(df.columns)}")


def main() -> None:
    symbol = "AAPL"
    market_proxy = "SPY"
    sector_proxy = "XLK"  # tech; adjust later based on universe

    end = datetime.now(timezone.utc)
    start_10m = end - timedelta(days=5)   # enough to test windows / indicators
    start_1h = end - timedelta(days=30)   # enough to test hourly backfill

    # -------------------------------------------------------------------------
    # 1) Alpaca bars: 10m and 1h for symbol + SPY + sector ETF
    # -------------------------------------------------------------------------
    alpaca = AlpacaMarketSource(api_key=ALPACA_API_KEY_ID, api_secret=ALPACA_API_SECRET_KEY)

    bars_10m = alpaca.fetch_bars(
        symbols=[symbol, market_proxy, sector_proxy],
        start=start_10m,
        end=end,
        timeframe="10min",
    )
    _print_df(
        f"ALPACA 10MIN BARS [{symbol},{market_proxy},{sector_proxy}] start={start_10m.isoformat()} end={end.isoformat()}",
        bars_10m.sort_values(["symbol", "timestamp"]),
        n=12,
    )

    _assert_has_cols(bars_10m, ["timestamp", "open", "high", "low", "close", "volume", "symbol"], "ALPACA 10MIN")

    # Quick sanity: at least some rows per symbol
    counts = bars_10m.groupby("symbol").size().to_dict()
    print("\n10MIN row counts:", counts)
    if any(v < 50 for v in counts.values()):
        print("Warning: low 10min bar count for one or more symbols (market closed or limited range).")

    # Optional: 1-hour bars (for an hourly baseline / alternative)
    bars_1h = alpaca.fetch_bars(
        symbols=[symbol, market_proxy, sector_proxy],
        start=start_1h,
        end=end,
        timeframe="1hour",
    )
    _print_df(
        f"ALPACA 1H BARS [{symbol},{market_proxy},{sector_proxy}] start={start_1h.isoformat()} end={end.isoformat()}",
        bars_1h.sort_values(["symbol", "timestamp"]),
        n=12,
    )
    _assert_has_cols(bars_1h, ["timestamp", "open", "high", "low", "close", "volume", "symbol"], "ALPACA 1H")

    # -------------------------------------------------------------------------
    # 2) GDELT news: timestamps + url + source_domain + tone
    # -------------------------------------------------------------------------
    gdelt = GdeltSource()

    gdelt_end = end.strftime("%Y%m%d%H%M%S")
    gdelt_start = (end - timedelta(hours=48)).strftime("%Y%m%d%H%M%S")  # 48h context like your plan
    query = f"({symbol} OR Apple)"

    news = gdelt.fetch_news(
        query=query,
        maxrecords=50,
        startdatetime=gdelt_start,
        enddatetime=gdelt_end,
    )

    if not news.empty:
        # standardize a few expected columns
        expected_any = ["publish_datetime", "url"]
        for c in expected_any:
            if c not in news.columns:
                raise AssertionError(f"GDELT: expected column '{c}' missing. cols={list(news.columns)}")

        # keep a compact view
        view_cols = [c for c in ["publish_datetime", "source_domain", "tone", "url"] if c in news.columns]
        news_view = news[view_cols].sort_values("publish_datetime", ascending=False)
    else:
        news_view = news

    _print_df(f"GDELT NEWS query='{query}' start={gdelt_start} end={gdelt_end}", news_view, n=15)

    if news.empty:
        print("GDELT returned empty")

    # -------------------------------------------------------------------------
    # 3) SEC EDGAR: submissions -> recent filings with timestamps/forms
    # -------------------------------------------------------------------------
    # Hardcode AAPL CIK for the test; later you’ll maintain a mapping for your universe.
    AAPL_CIK = "0000320193"

    sec = SecEdgarSource(user_agent=SEC_USER_AGENT)
    submissions = sec.fetch_submissions(cik=AAPL_CIK)
    filings = sec.extract_recent_filings(symbol=symbol, cik=AAPL_CIK, submissions_json=submissions)

    if not filings.empty:
        _assert_has_cols(filings, ["filing_date", "form", "accession", "symbol"], "SEC FILINGS")
        filings_view = filings[["filing_date", "form", "accession", "symbol"]].sort_values("filing_date", ascending=False)
    else:
        filings_view = filings

    _print_df(f"SEC FILINGS symbol={symbol} CIK={AAPL_CIK}", filings_view, n=20)

    # -------------------------------------------------------------------------
    # 4) FRED: daily macro series (EFFR) to forward-fill into intraday
    # -------------------------------------------------------------------------
    fred = FredSource(api_key=FRED_API_KEY)
    fred_start = (datetime.now(timezone.utc) - timedelta(days=60)).date().isoformat()

    effr = fred.fetch_series_observations(series_id="EFFR", observation_start=fred_start)
    _assert_has_cols(effr, ["date", "value"], "FRED EFFR")

    effr_view = effr.sort_values("date", ascending=False).head(10)
    _print_df(f"FRED EFFR (daily) start={fred_start}", effr_view, n=10)

    # -------------------------------------------------------------------------
    # Summary checks: do we have what we need for training?
    # -------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("TRAINING DATA FEASIBILITY SUMMARY")
    print("=" * 100)

    print("Alpaca bars: OK (10min + 1h, OHLCV, multi-symbol)")
    print("Market/sector context: OK (SPY + XLK as proxies)")
    print("GDELT: OK" if not news.empty else "⚠️  GDELT: returned empty (API reachable, but no hits in window)")
    print("SEC: OK (recent filings present)" if not filings.empty else "⚠️  SEC: returned empty (still OK; depends on recent activity)")
    print("FRED: OK (EFFR daily series retrieved)")

    print("\nIf Alpaca and FRED are non-empty, your training pipeline is viable. "
          "GDELT/SEC can be empty depending on time window—widen the window for backfills.\n")


if __name__ == "__main__":
    main()
