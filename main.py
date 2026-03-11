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

    # Execute - Crawl options
    option_sessions = service.crawl_options(day_url=config.day_url, night_url=config.night_url)
    repository.save_sessions(option_sessions)

    # Execute - Crawl futures
    future_session = service.crawl_futures(future_url=config.future_url)
    repository.save_sessions([future_session])

    # Report
    day_rows = len(option_sessions[0].rows)
    night_rows = len(option_sessions[1].rows)
    future_rows = len(future_session.rows)
    print(f"Stored option day({day_rows}) + night({night_rows}) rows to MongoDB.")
    print(f"Stored future({future_rows}) month records to MongoDB.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
