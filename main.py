#!/usr/bin/env python3
"""Main entry point for TAIFEX and TWSE crawler."""

from __future__ import annotations

import re
import time

from src.config import CrawlerConfig
from src.fetcher import TaifexTableFetcher, TwseTaiexFetcher
from src.repository import MongoMarketRepository
from src.service import TaifexCrawlerService
from src.transformer import DataTransformer


def extract_expiry_dates(day_session_rows: list[dict]) -> dict[int, int]:
    """
    Extract expiry dates from day session data.

    Args:
        day_session_rows: List of option records from day session

    Returns:
        Mapping of future month (int) to expiry date (int, YYYYMMDD format)
    """
    expiry_map: dict[int, int] = {}
    for row in day_session_rows:
        month_str = str(row.get("到期月份(週別)", ""))
        expiry = row.get("契約到期日")

        # Only use pure month values (6 digits, no W1/W2/F1 suffix)
        if re.match(r"^\d{6}$", month_str) and expiry is not None:
            month_int = int(month_str)
            if month_int not in expiry_map:
                # Convert float to int (e.g., 20260318.0 -> 20260318)
                expiry_map[month_int] = int(expiry)

    return expiry_map


def main() -> int:
    """Run the crawler."""
    total_start = time.time()
    config = CrawlerConfig.from_env()

    # Build dependencies
    fetcher = TaifexTableFetcher()
    twse_fetcher = TwseTaiexFetcher()
    transformer = DataTransformer()
    service = TaifexCrawlerService(fetcher=fetcher, transformer=transformer)
    repository = MongoMarketRepository(
        mongo_uri=config.mongo_uri,
        db_name=config.mongo_db,
        collection_name=config.mongo_collection,
    )

    # Step 1: Crawl futures data (get valid months)
    print("[1/6] Crawling futures data...")
    step_start = time.time()
    future_session = service.crawl_futures(future_url=config.future_url)
    future_months = {row["期貨月份"] for row in future_session.rows}
    print(f"      Done in {time.time() - step_start:.2f}s")
    print(f"      Future months: {sorted(future_months)}")

    # Step 2: Crawl options data (need day session for expiry dates)
    print("[2/6] Crawling options data...")
    step_start = time.time()
    option_sessions = service.crawl_options(
        day_url=config.day_url,
        night_url=config.night_url
    )
    print(f"      Done in {time.time() - step_start:.2f}s")

    # Step 3: Extract expiry dates from day session
    day_session = next(s for s in option_sessions if s.session == "day")
    expiry_dates = extract_expiry_dates(day_session.rows)
    print(f"      Expiry dates: {expiry_dates}")

    # Step 4: Crawl TWSE TAIEX data (optional - may fail due to IP blocking)
    print("[3/6] Crawling TWSE TAIEX data...")
    step_start = time.time()
    taiex_data: dict | None = None
    try:
        taiex_data = twse_fetcher.fetch_latest_close_index(config.twse_taiex_url)
        print(f"      Done in {time.time() - step_start:.2f}s")
        print(f"      TAIEX: {taiex_data['date']} -> {taiex_data['close_index']}")
    except Exception as e:
        print(f"      WARNING: Failed to fetch TWSE TAIEX data: {e}")
        print(f"      Continuing without TAIEX data...")

    # Step 5: Save future month data (with expiry dates)
    print("[4/6] Saving future months...")
    step_start = time.time()
    repository.save_future_months(
        months=future_session.rows,
        trade_date=future_session.trade_date,
        source_url=future_session.source_url,
        expiry_dates=expiry_dates,
    )
    print(f"      Done in {time.time() - step_start:.2f}s")

    # Step 6: Save TWSE TAIEX data (if available)
    if taiex_data:
        print("[5/6] Saving TWSE TAIEX data...")
        step_start = time.time()
        repository.save_twse_taiex(
            date=taiex_data["date"],
            close_index=taiex_data["close_index"],
            source_url=config.twse_taiex_url,
        )
        print(f"      Done in {time.time() - step_start:.2f}s")
    else:
        print("[5/6] Skipping TWSE TAIEX save (no data)")
    print(f"      Done in {time.time() - step_start:.2f}s")

    # Step 7: Save option data (filtered by valid months)
    total_day_saved = 0
    total_night_saved = 0
    for session_data in option_sessions:
        print(f"[6/6] Saving {session_data.session} option records...")
        step_start = time.time()
        saved_count = repository.save_option_records(
            records=session_data.rows,
            session=session_data.session,
            trade_date=session_data.trade_date,
            source_url=session_data.source_url,
            valid_months=future_months,
        )
        print(f"      Stored {saved_count} records in {time.time() - step_start:.2f}s")
        if session_data.session == "day":
            total_day_saved = saved_count
        else:
            total_night_saved = saved_count

    # Report
    print(f"\n[Summary]")
    print(f"  Future months: {len(future_session.rows)}")
    print(f"  TWSE TAIEX: {taiex_data['close_index'] if taiex_data else 'N/A (failed)'}")
    print(f"  Day options: {total_day_saved}")
    print(f"  Night options: {total_night_saved}")
    print(f"  Total time: {time.time() - total_start:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
