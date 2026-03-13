#!/usr/bin/env python3
"""Main entry point for TAIFEX option crawler."""

from __future__ import annotations

from src.config import CrawlerConfig
from src.fetcher import TaifexTableFetcher
from src.repository import MongoMarketRepository
from src.service import TaifexCrawlerService
from src.transformer import DataTransformer


def main() -> int:
    """Run the crawler."""
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
    print("Crawling futures data...")
    future_session = service.crawl_futures(future_url=config.future_url)

    # Step 2: Save future month data
    repository.save_future_months(
        months=future_session.rows,
        trade_date=future_session.trade_date,
        source_url=future_session.source_url,
    )

    # Step 3: Get future months set (for filtering options)
    future_months = {row["期貨月份"] for row in future_session.rows}
    print(f"Future months: {sorted(future_months)}")

    # Step 4: Crawl options data
    print("Crawling options data...")
    option_sessions = service.crawl_options(
        day_url=config.day_url,
        night_url=config.night_url
    )

    # Step 5: Save option data (filtered by valid months)
    total_day_saved = 0
    total_night_saved = 0
    for session_data in option_sessions:
        saved_count = repository.save_option_records(
            records=session_data.rows,
            session=session_data.session,
            trade_date=session_data.trade_date,
            source_url=session_data.source_url,
            valid_months=future_months,
        )
        if session_data.session == "day":
            total_day_saved = saved_count
        else:
            total_night_saved = saved_count
        print(f"Stored {saved_count} {session_data.session} option records.")

    # Report
    print(f"Stored {len(future_session.rows)} future month records.")
    print(f"Total: day({total_day_saved}) + night({total_night_saved}) option records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
