"""HTTP fetchers for TAIFEX and TWSE data."""

from __future__ import annotations

import io
import re

import pandas as pd
import requests
from requests.exceptions import ProxyError

DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0"}


class TaifexTableFetcher:
    """Fetches option and future tables from TAIFEX website."""

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

        table = None
        for tbl in tables:
            has_contract = "契約" in tbl.columns
            has_expiry = any("到期" in str(col) and "月份" in str(col) for col in tbl.columns)
            if has_contract and has_expiry:
                table = tbl
                break

        if table is None:
            raise RuntimeError(f"Could not find futures table from: {url}")

        table = table.loc[:, ~table.columns.str.contains(r"^Unnamed")]

        if len(table) > 0:
            last_row = table.iloc[-1]
            last_row_str = " ".join(str(val) for val in last_row.values)
            if any(keyword in last_row_str for keyword in ["小計", "合計", "總計"]) or pd.isna(last_row.iloc[0]):
                table = table.iloc[:-1]

        table = table.replace({"-": pd.NA, "－": pd.NA})
        table["市場時段"] = "夜盤" if is_night else "日盤"
        table["交易日"] = pd.to_datetime(trade_date, format="%Y/%m/%d")

        return table, trade_date


class TwseTaiexFetcher:
    """Fetches TAIEX index data from TWSE."""

    def __init__(self, headers: dict | None = None):
        self.headers = headers or DEFAULT_HEADERS

    def _get_with_proxy_fallback(self, url: str) -> requests.Response:
        """Try default request first, then retry direct connection when proxy blocks."""
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response
        except ProxyError:
            session = requests.Session()
            session.trust_env = False
            response = session.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response

    def fetch_latest_close_index(self, url: str) -> dict[str, str | float]:
        """Fetch the latest date's close index from a TWSE HTML table page."""
        response = self._get_with_proxy_fallback(url)
        response.encoding = "utf-8"

        tables = pd.read_html(io.StringIO(response.text), flavor="lxml")
        if not tables:
            raise RuntimeError(f"Could not find any table from: {url}")

        table = tables[0]
        date_col = next((col for col in table.columns if "日期" in str(col)), None)
        close_col = next((col for col in table.columns if "收盤" in str(col)), None)
        if date_col is None or close_col is None:
            raise RuntimeError(f"Could not find 日期/收盤 columns from: {url}")

        data = table[[date_col, close_col]].dropna().copy()
        if data.empty:
            raise RuntimeError(f"TWSE table is empty from: {url}")

        data[date_col] = pd.to_datetime(data[date_col], errors="coerce")
        data = data.dropna(subset=[date_col])
        if data.empty:
            raise RuntimeError(f"Could not parse 日期 column from: {url}")

        latest_row = data.sort_values(date_col, ascending=False).iloc[0]
        close_value = str(latest_row[close_col]).replace(",", "").strip()

        return {
            "date": latest_row[date_col].strftime("%Y/%m/%d"),
            "close_index": float(close_value),
        }
