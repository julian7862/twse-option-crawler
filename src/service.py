"""Application service for crawling TAIFEX data."""

from __future__ import annotations

from typing import Protocol

import pandas as pd

from .models import MarketSessionData
from .transformer import DataTransformer


class TableFetcher(Protocol):
    """Protocol for table fetchers."""

    def fetch_table(self, url: str, is_night: bool) -> tuple[pd.DataFrame, str]:
        """Fetch table from URL."""
        ...


class TaifexCrawlerService:
    """Service for crawling TAIFEX option data."""

    def __init__(self, fetcher: TableFetcher, transformer: DataTransformer):
        self.fetcher = fetcher
        self.transformer = transformer

    def crawl(self, day_url: str, night_url: str) -> list[MarketSessionData]:
        """
        Crawl both day and night session data.

        Args:
            day_url: URL for day session
            night_url: URL for night session

        Returns:
            List of MarketSessionData for both sessions
        """
        day_df, day_date = self.fetcher.fetch_table(day_url, is_night=False)
        night_df, night_date = self.fetcher.fetch_table(night_url, is_night=True)

        return [
            MarketSessionData(
                trade_date=day_date,
                session="day",
                source_url=day_url,
                rows=self.transformer.dataframe_to_records(day_df),
            ),
            MarketSessionData(
                trade_date=night_date,
                session="night",
                source_url=night_url,
                rows=self.transformer.dataframe_to_records(night_df),
            ),
        ]
