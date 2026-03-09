import os
import sys
from datetime import datetime
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import Mock, patch

import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import CrawlerConfig
from src.fetcher import TaifexTableFetcher
from src.models import MarketSessionData
from src.repository import MongoMarketRepository
from src.service import TaifexCrawlerService
from src.transformer import DataTransformer


class FakeFetcher:
    def fetch_table(self, url, is_night):
        df = pd.DataFrame(
            [
                {"履約價": 23000, "成交量": 10, "交易日": pd.Timestamp("2025-01-01")},
                {"履約價": 23100, "成交量": None, "交易日": pd.Timestamp("2025-01-01")},
            ]
        )
        return df, "2025/01/01"

    def option_fetch_table(self, url, is_night):
        return self.fetch_table(url, is_night)

    def future_fetch_table(self, url, is_night):
        df = pd.DataFrame(
            [
                {
                    "契約": "TX",
                    "到期月份(週別)": 202603,
                    "開盤價": 31730,
                    "最高價": 32111,
                    "最低價": 31124,
                    "最後成交價": 31786,
                    "交易日": pd.Timestamp("2025-01-01"),
                },
                {
                    "契約": "TX",
                    "到期月份(週別)": 202604.0,
                    "開盤價": 31808,
                    "最高價": 32205,
                    "最低價": 31227,
                    "最後成交價": 31880,
                    "交易日": pd.Timestamp("2025-01-01"),
                },
            ]
        )
        return df, "2025/01/01"


class FakeCollection:
    def __init__(self):
        self.update_calls = []

    def update_one(self, filt, payload, upsert=False):
        self.update_calls.append((filt, payload, upsert))


class CrawlerTests(TestCase):
    def test_config_from_env(self):
        with patch.dict(
            os.environ,
            {
                "MONGO_URI": "mongodb://localhost:27017",
                "MONGO_DB": "demo_db",
                "MONGO_COLLECTION": "demo_col",
                "TAIFEX_DAY_URL": "https://day.example",
                "TAIFEX_NIGHT_URL": "https://night.example",
            },
            clear=True,
        ):
            config = CrawlerConfig.from_env()

        self.assertEqual(config.mongo_uri, "mongodb://localhost:27017")
        self.assertEqual(config.mongo_db, "demo_db")
        self.assertEqual(config.mongo_collection, "demo_col")
        self.assertEqual(config.day_url, "https://day.example")
        self.assertEqual(config.night_url, "https://night.example")

    def test_transformer_converts_nan_to_none(self):
        df = pd.DataFrame(
            [{"交易日": pd.Timestamp("2025-01-01"), "成交量": None, "履約價": 23000}]
        )

        records = DataTransformer.dataframe_to_records(df)

        self.assertEqual(len(records), 1)
        self.assertIsNone(records[0]["成交量"])
        self.assertIsInstance(records[0]["交易日"], datetime)

    def test_service_crawl_returns_day_and_night_sessions(self):
        service = TaifexCrawlerService(fetcher=FakeFetcher(), transformer=DataTransformer())

        sessions = service.crawl("https://day.example", "https://night.example")

        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0].session, "day")
        self.assertEqual(sessions[1].session, "night")
        self.assertEqual(sessions[0].trade_date, "2025/01/01")

    def test_repository_upsert_payload(self):
        fake_collection = FakeCollection()
        session = MarketSessionData(
            trade_date="2025/01/01",
            session="day",
            source_url="https://day.example",
            rows=[{"履約價": 23000}],
        )

        MongoMarketRepository._upsert_session(fake_collection, session)

        self.assertEqual(len(fake_collection.update_calls), 1)
        filt, payload, upsert = fake_collection.update_calls[0]
        self.assertEqual(filt, {"trade_date": "2025/01/01", "session": "day"})
        self.assertTrue(upsert)
        self.assertEqual(payload["$set"]["row_count"], 1)

    def test_option_fetch_returns_correct_data(self):
        service = TaifexCrawlerService(fetcher=FakeFetcher(), transformer=DataTransformer())

        sessions = service.crawl("https://day.example", "https://night.example")

        self.assertEqual(len(sessions), 2)
        self.assertIn("履約價", sessions[0].rows[0])

    def test_future_fetch_returns_correct_data(self):
        fetcher = FakeFetcher()
        df, trade_date = fetcher.future_fetch_table("https://future.example", False)

        self.assertEqual(trade_date, "2025/01/01")
        self.assertEqual(len(df), 2)
        self.assertIn("契約", df.columns)
        self.assertIn("到期月份(週別)", df.columns)
        self.assertEqual(df.iloc[0]["契約"], "TX")

    def test_service_crawl_futures_returns_month_data(self):
        service = TaifexCrawlerService(fetcher=FakeFetcher(), transformer=DataTransformer())

        sessions = service.crawl_futures("https://day.example", "https://night.example")

        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0].session, "future_month")
        self.assertEqual(sessions[1].session, "future_month")
        self.assertEqual(sessions[0].trade_date, "2025/01/01")

        # Check that rows contain only 期貨月份
        for row in sessions[0].rows:
            self.assertIn("期貨月份", row)
            self.assertEqual(len(row), 1)

        # Check unique months are extracted
        months = [row["期貨月份"] for row in sessions[0].rows]
        self.assertEqual(set(months), {202603, 202604})
        for month in months:
            self.assertIsInstance(month, int)


class FetcherParsingTests(TestCase):
    @patch("src.fetcher.requests.get")
    def test_future_fetch_table_removes_summary_row_and_normalizes_dash(self, mock_get):
        html = """
        <html><body>
        日期：2025/01/01
        <table>
          <tr><th>契約</th><th>到期 月份 (週別)</th><th>開盤價</th><th>最高價</th></tr>
          <tr><td>TX</td><td>202603</td><td>31730</td><td>-</td></tr>
          <tr><td>TX</td><td>202604</td><td>31808</td><td>32205</td></tr>
          <tr><td></td><td>小計</td><td></td><td></td></tr>
        </table>
        </body></html>
        """
        response = Mock()
        response.headers = {"content-type": "text/html; charset=utf-8"}
        response.text = html
        response.raise_for_status = Mock()
        mock_get.return_value = response

        df, trade_date = TaifexTableFetcher().future_fetch_table("https://future.example", is_night=False)

        self.assertEqual(trade_date, "2025/01/01")
        self.assertEqual(len(df), 2)
        self.assertTrue(pd.isna(df.iloc[0]["最高價"]))
        self.assertEqual(df.iloc[0]["市場時段"], "日盤")

    @patch("src.fetcher.requests.get")
    def test_option_fetch_table_parses_night_date_and_sets_session(self, mock_get):
        html = """
        <html><body>
        2025/01/01 15:00 ~ 次日 05:00
        <table>
          <tr><th>履約價</th><th>成交量</th></tr>
          <tr><td>23000</td><td>10</td></tr>
          <tr><td>合計</td><td>10</td></tr>
        </table>
        </body></html>
        """
        response = Mock()
        response.headers = {"content-type": "text/html"}
        response.text = html
        response.raise_for_status = Mock()
        mock_get.return_value = response

        df, trade_date = TaifexTableFetcher().option_fetch_table("https://option.example", is_night=True)

        self.assertEqual(trade_date, "2025/01/01")
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["市場時段"], "夜盤")


if __name__ == "__main__":
    main()
