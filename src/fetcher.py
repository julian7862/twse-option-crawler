"""HTTP fetchers for TAIFEX and TWSE data."""

from __future__ import annotations

import io
import re

import pandas as pd
import requests
from requests.exceptions import ConnectionError, ProxyError, SSLError, Timeout

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
        """Try default request first, then retry direct connection when proxy/network fails.

        Handles:
        - ProxyError: Proxy server rejected the request
        - SSLError: SSL certificate verification failed
        - ConnectionError: DNS resolution failed, connection refused, etc.
        - Timeout: Request timed out (possibly due to proxy)
        """
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        try:
            response = requests.get(url, headers=self.headers, timeout=30, verify=False)
            response.raise_for_status()
            return response
        except (ProxyError, SSLError, ConnectionError, Timeout):
            # Retry without proxy (trust_env=False ignores HTTP_PROXY/HTTPS_PROXY)
            session = requests.Session()
            session.trust_env = False
            response = session.get(url, headers=self.headers, timeout=30, verify=False)
            response.raise_for_status()
            return response

    @staticmethod
    def _roc_to_gregorian(date_str: str) -> str:
        """Convert ROC date (民國年) to Gregorian date if needed.

        Example: '115/03/13' -> '2026/03/13'
        Already Gregorian: '2025/01/01' -> '2025/01/01'
        """
        parts = str(date_str).split("/")
        if len(parts) == 3:
            year = int(parts[0])
            # If year < 1911, assume it's ROC calendar
            if year < 1911:
                gregorian_year = year + 1911
                return f"{gregorian_year}/{parts[1]}/{parts[2]}"
        return date_str

    def fetch_latest_close_index(self, url: str) -> dict[str, str | float]:
        """Fetch the latest date's close index from a TWSE page (supports JSON and HTML)."""
        import json

        response = self._get_with_proxy_fallback(url)
        response.encoding = "utf-8"

        # Check if response looks like an error page or blocked response
        content_preview = response.text[:500] if response.text else "(empty)"
        if not response.text or len(response.text) < 100:
            raise RuntimeError(
                f"TWSE returned empty or blocked response. "
                f"Status: {response.status_code}, Content: {content_preview}"
            )

        # Try JSON first (GitHub Actions may receive JSON instead of HTML)
        try:
            json_data = json.loads(response.text)
            return self._parse_json_response(json_data)
        except (json.JSONDecodeError, KeyError, IndexError):
            pass  # Not JSON or invalid format, try HTML

        # Fall back to HTML parsing
        try:
            tables = pd.read_html(io.StringIO(response.text), flavor="lxml")
        except ValueError as e:
            raise RuntimeError(
                f"TWSE response is neither valid JSON nor HTML with tables. "
                f"Status: {response.status_code}, Content preview: {content_preview}"
            ) from e

        if not tables:
            raise RuntimeError(f"Could not find any table from: {url}")

        return self._parse_html_table(tables[0])

    def _parse_json_response(self, json_data: dict) -> dict[str, str | float]:
        """Parse TWSE JSON response format."""
        if json_data.get("stat") != "OK":
            raise RuntimeError(f"TWSE JSON response stat is not OK: {json_data.get('stat')}")

        fields = json_data.get("fields", [])
        data = json_data.get("data", [])

        if not data:
            raise RuntimeError("TWSE JSON response has no data")

        # Find column indices
        date_idx = next((i for i, f in enumerate(fields) if "日期" in f), None)
        close_idx = next((i for i, f in enumerate(fields) if "收盤" in f), None)

        if date_idx is None or close_idx is None:
            raise RuntimeError(f"Could not find 日期/收盤 in fields: {fields}")

        # Get the last row (latest date)
        latest_row = data[-1]
        roc_date = latest_row[date_idx]
        close_value = str(latest_row[close_idx]).replace(",", "").strip()

        # Convert ROC date to Gregorian
        gregorian_date = self._roc_to_gregorian(roc_date)

        return {
            "date": gregorian_date,
            "close_index": float(close_value),
        }

    def _parse_html_table(self, table: pd.DataFrame) -> dict[str, str | float]:
        """Parse TWSE HTML table format."""
        # Handle multi-level column names (flatten if needed)
        if isinstance(table.columns, pd.MultiIndex):
            table.columns = [col[-1] for col in table.columns]

        date_col = next((col for col in table.columns if "日期" in str(col)), None)
        close_col = next((col for col in table.columns if "收盤" in str(col)), None)
        if date_col is None or close_col is None:
            raise RuntimeError(f"Could not find 日期/收盤 columns: {list(table.columns)}")

        data = table[[date_col, close_col]].dropna().copy()
        if data.empty:
            raise RuntimeError("TWSE table is empty")

        # Convert ROC date to Gregorian and parse
        data["_date_gregorian"] = data[date_col].apply(self._roc_to_gregorian)
        data["_date_parsed"] = pd.to_datetime(data["_date_gregorian"], format="%Y/%m/%d", errors="coerce")
        data = data.dropna(subset=["_date_parsed"])
        if data.empty:
            raise RuntimeError("Could not parse 日期 column")

        latest_row = data.sort_values("_date_parsed", ascending=False).iloc[0]
        close_value = str(latest_row[close_col]).replace(",", "").strip()

        return {
            "date": latest_row["_date_parsed"].strftime("%Y/%m/%d"),
            "close_index": float(close_value),
        }
