#!/usr/bin/env python3
"""Main entry point for TAIFEX option crawler."""

from __future__ import annotations

import time

from src.config import CrawlerConfig
from src.fetcher import TaifexTableFetcher
from src.repository import MongoMarketRepository
from src.service import TaifexCrawlerService
from src.transformer import DataTransformer


def main() -> int:
    """Run the crawler."""
    total_start = time.time()
    config = CrawlerConfig.from_env()

    # Build dependencies
    fetcher = TaifexTableFetcher()
    transformer = DataTransformer()
    service = TaifexCrawlerService(fetcher=fetcher, transformer=transformer)
    repository = MongoMarketRepository(
        mongo_uri=config.mongo_uri,
        db_name=config.mongo_db,
        collection_name=config.mongo_collection,
    )

    # Step 1: Crawl futures data
    print("[1/5] Crawling futures data...")
    step_start = time.time()
    future_session = service.crawl_futures(future_url=config.future_url)
    print(f"      Done in {time.time() - step_start:.2f}s")

    # Step 2: Save future month data
    print("[2/5] Saving future months...")
    step_start = time.time()
    repository.save_future_months(
        months=future_session.rows,
        trade_date=future_session.trade_date,
        source_url=future_session.source_url,
    )
    print(f"      Done in {time.time() - step_start:.2f}s")

    # Step 3: Get future months set (for filtering options)
    future_months = {row["期貨月份"] for row in future_session.rows}
    print(f"      Future months: {sorted(future_months)}")

    # Step 4: Crawl options data
    print("[3/5] Crawling options data...")
    step_start = time.time()
    option_sessions = service.crawl_options(
        day_url=config.day_url,
        night_url=config.night_url
    )
    print(f"      Done in {time.time() - step_start:.2f}s")

    # Step 5: Save option data (filtered by valid months)
    total_day_saved = 0
    total_night_saved = 0
    for session_data in option_sessions:
        print(f"[4/5] Saving {session_data.session} option records...")
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
    print(f"  Day options: {total_day_saved}")
    print(f"  Night options: {total_night_saved}")
    print(f"  Total time: {time.time() - total_start:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
