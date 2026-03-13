#!/usr/bin/env python3
"""Fetch latest close index from TWSE TAIEX 5-minute history page."""

from __future__ import annotations

from requests.exceptions import RequestException

from src.fetcher import TwseTaiexFetcher

TWSE_TAIEX_URL = "https://www.twse.com.tw/rwd/zh/TAIEX/MI_5MINS_HIST?response=html"


def main() -> int:
    fetcher = TwseTaiexFetcher()
    try:
        latest = fetcher.fetch_latest_close_index(TWSE_TAIEX_URL)
    except RequestException as exc:
        print(f"抓取失敗：網路連線異常（{exc}）")
        return 1
    except RuntimeError as exc:
        print(f"抓取失敗：{exc}")
        return 1

    print(f"最新日期: {latest['date']}")
    print(f"收盤指數: {latest['close_index']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
