"""HTTP fetcher for TAIFEX option data."""

from __future__ import annotations

import io
import re

import pandas as pd
import requests

DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0"}


class TaifexTableFetcher:
    """Fetches option tables from TAIFEX website."""

    def __init__(self, headers: dict | None = None):
        self.headers = headers or DEFAULT_HEADERS

    @staticmethod
    def _best_encoding(response: requests.Response) -> str:
        """Determine the best encoding for the response."""
        content_type = response.headers.get("content-type", "").lower()
        return "utf-8" if "utf-8" in content_type else "big5"

    def option_fetch_table(self, url: str, is_night: bool) -> tuple[pd.DataFrame, str]:
        """
        Fetch and parse option table from TAIFEX.

        Args:
            url: The URL to fetch from
            is_night: Whether this is a night session

        Returns:
            Tuple of (DataFrame, trade_date)
        """
        response = requests.get(url, headers=self.headers, timeout=30)
        response.raise_for_status()
        response.encoding = self._best_encoding(response)
        html = response.text.replace("&nbsp;", " ")

        date_match = (
            re.search(r"日期：\s*([\d/]+)", html)
            if not is_night
            else re.search(r"(\d{4}/\d{2}/\d{2})\s*\d{2}:\d{2}\s*[~～]\s*次日", html)
        )
        if not date_match:
            raise RuntimeError(f"Could not find trade date from: {url}")

        trade_date = date_match.group(1)
        tables = pd.read_html(io.StringIO(html), header=0, flavor="lxml")
        table = next(tbl for tbl in tables if "履約價" in tbl.columns)

        table = table.loc[:, ~table.columns.str.contains(r"^Unnamed")]
        if str(table.iloc[-1, 0]).strip() in ("合計", "總計"):
            table = table.iloc[:-1]

        table = table.replace({"-": pd.NA, "－": pd.NA})
        table["市場時段"] = "夜盤" if is_night else "日盤"
        table["交易日"] = pd.to_datetime(trade_date, format="%Y/%m/%d")
        return table, trade_date

    def future_fetch_table(self, url: str, is_night: bool) -> tuple[pd.DataFrame, str]:
        """
        Fetch and parse future table from TAIFEX.

        Args:
            url: The URL to fetch from
            is_night: Whether this is a night session

        Returns:
            Tuple of (DataFrame, trade_date)
        """
        response = requests.get(url, headers=self.headers, timeout=30)
        response.raise_for_status()
        response.encoding = self._best_encoding(response)
        html = response.text.replace("&nbsp;", " ")

        date_match = (
            re.search(r"日期：\s*([\d/]+)", html)
            if not is_night
            else re.search(r"(\d{4}/\d{2}/\d{2})\s*\d{2}:\d{2}\s*[~～]\s*次日", html)
        )
        if not date_match:
            raise RuntimeError(f"Could not find trade date from: {url}")

        trade_date = date_match.group(1)
        tables = pd.read_html(io.StringIO(html), header=0, flavor="lxml")

        # Find the futures table (first table with 契約 column)
        # Column name might have spaces like "到期 月份 (週別)" or "到期月份(週別)"
        table = None
        for tbl in tables:
            # Check if this is a futures table by looking for key columns
            has_contract = "契約" in tbl.columns
            has_expiry = any("到期" in str(col) and "月份" in str(col) for col in tbl.columns)

            if has_contract and has_expiry:
                table = tbl
                break

        if table is None:
            raise RuntimeError(f"Could not find futures table from: {url}")

        # Remove unnamed columns
        table = table.loc[:, ~table.columns.str.contains(r"^Unnamed")]

        # Remove summary rows (小計 row)
        # The summary row might have NaN in contract column and "小計" in other columns
        if len(table) > 0:
            last_row = table.iloc[-1]
            # Check if any cell in the last row contains summary keywords
            last_row_str = " ".join(str(val) for val in last_row.values)
            if any(keyword in last_row_str for keyword in ["小計", "合計", "總計"]) or pd.isna(last_row.iloc[0]):
                table = table.iloc[:-1]

        # Replace dashes with NA
        table = table.replace({"-": pd.NA, "－": pd.NA})

        # Add metadata columns
        table["市場時段"] = "夜盤" if is_night else "日盤"
        table["交易日"] = pd.to_datetime(trade_date, format="%Y/%m/%d")

        return table, trade_date

    def fetch_table(self, url: str, is_night: bool) -> tuple[pd.DataFrame, str]:
        """
        Fetch and parse option table from TAIFEX (deprecated, use option_fetch_table).

        Args:
            url: The URL to fetch from
            is_night: Whether this is a night session

        Returns:
            Tuple of (DataFrame, trade_date)
        """
        return self.option_fetch_table(url, is_night)
