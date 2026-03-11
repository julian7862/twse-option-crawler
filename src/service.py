"""Application service for crawling TAIFEX data."""

from __future__ import annotations

import numbers
from typing import Protocol

import pandas as pd

from .models import MarketSessionData
from .transformer import DataTransformer


class TableFetcher(Protocol):
    """Protocol for table fetchers."""

    def option_fetch_table(self, url: str, is_night: bool) -> tuple[pd.DataFrame, str]:
        """Fetch option table from URL."""
        ...

    def future_fetch_table(self, url: str, is_night: bool) -> tuple[pd.DataFrame, str]:
        """Fetch future table from URL."""
        ...


class TaifexCrawlerService:
    """Service for crawling TAIFEX option and future data."""

    def __init__(self, fetcher: TableFetcher, transformer: DataTransformer):
        self.fetcher = fetcher
        self.transformer = transformer

    def crawl_options(self, day_url: str, night_url: str) -> list[MarketSessionData]:
        """
        Crawl both day and night session option data.

        Args:
            day_url: URL for day session
            night_url: URL for night session

        Returns:
            List of MarketSessionData for both sessions
        """
        day_df, day_date = self.fetcher.option_fetch_table(day_url, is_night=False)
        night_df, night_date = self.fetcher.option_fetch_table(night_url, is_night=True)

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

    def crawl_futures(self, future_url: str) -> MarketSessionData:
        """
        Crawl future data and extract unique month values.

        Args:
            future_url: URL for future data

        Returns:
            MarketSessionData with future month data
        """
        df, trade_date = self.fetcher.future_fetch_table(future_url, is_night=False)

        return MarketSessionData(
            trade_date=trade_date,
            session="future_month",
            source_url=future_url,
            rows=self._transform_future_to_month_records(df),
        )

    def _transform_future_to_month_records(self, df: pd.DataFrame) -> list[dict]:
        """
        Transform future DataFrame to records with only month data.

        Args:
            df: Future DataFrame with 到期 月份 (週別) or 到期月份(週別) column

        Returns:
            List of dictionaries with format {"期貨月份": value}
        """
        # Find the expiry month column (handles both with and without spaces)
        expiry_col = None
        for col in df.columns:
            if "到期" in str(col) and "月份" in str(col):
                expiry_col = col
                break

        if expiry_col is None:
            raise ValueError("Could not find expiry month column in futures data")

        # Extract unique month values and create records
        records = []
        for value in df[expiry_col].dropna().unique():
            # Convert float-like numeric values to int (e.g., 202603.0 -> 202603)
            if isinstance(value, numbers.Real) and float(value).is_integer():
                value = int(value)
            records.append({"期貨月份": value})

        return records
