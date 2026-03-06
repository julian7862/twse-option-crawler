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

    def fetch_table(self, url: str, is_night: bool) -> tuple[pd.DataFrame, str]:
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
