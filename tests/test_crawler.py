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
    def option_fetch_table(self, url, is_night):
        df = pd.DataFrame(
            [
                # Monthly options (pure 6-digit month)
                {
                    "契約": "TXO",
                    "到期月份(週別)": "202603",
                    "履約價": 23000,
                    "買賣權": "Call",
                    "成交量": 10,
                    "交易日": pd.Timestamp("2025-01-01")
                },
                {
                    "契約": "TXO",
                    "到期月份(週別)": "202603",
                    "履約價": 23000,
                    "買賣權": "Put",
                    "成交量": 5,
                    "交易日": pd.Timestamp("2025-01-01")
                },
                # Weekly options (should be filtered out in new logic)
                {
                    "契約": "TXO",
                    "到期月份(週別)": "202603W2",
                    "履約價": 23100,
                    "買賣權": "Call",
                    "成交量": 3,
                    "交易日": pd.Timestamp("2025-01-01")
                },
                {
                    "契約": "TXO",
                    "到期月份(週別)": "202604F1",
                    "履約價": 23100,
                    "買賣權": "Call",
                    "成交量": None,
                    "交易日": pd.Timestamp("2025-01-01")
                },
            ]
        )
        return df, "2025/01/01"

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


class FakeBulkWriteResult:
    def __init__(self, count):
        self.upserted_count = count
        self.modified_count = 0


class FakeCollection:
    def __init__(self):
        self.update_calls = []
        self.indexes = []
        self.bulk_operations = []
        self.bulk_operations_raw = []  # Store serializable filter/update data

    def update_one(self, filt, payload, upsert=False):
        self.update_calls.append((filt, payload, upsert))

    def bulk_write(self, operations, ordered=True):
        self.bulk_operations = operations
        # Extract filter and update data for testing without accessing private attributes
        for op in operations:
            # UpdateOne stores filter in _filter and update in _doc, but we extract via repr
            # or we can just count. For detailed verification, store raw data before UpdateOne creation.
            pass
        return FakeBulkWriteResult(len(operations))

    def create_index(self, index_spec, unique=False, name=None, partialFilterExpression=None):
        self.indexes.append((index_spec, unique, name, partialFilterExpression))


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
                "TAIFEX_FUTURE_URL": "https://future.example",
            },
            clear=True,
        ):
            config = CrawlerConfig.from_env()

        self.assertEqual(config.mongo_uri, "mongodb://localhost:27017")
        self.assertEqual(config.mongo_db, "demo_db")
        self.assertEqual(config.mongo_collection, "demo_col")
        self.assertEqual(config.day_url, "https://day.example")
        self.assertEqual(config.night_url, "https://night.example")
        self.assertEqual(config.future_url, "https://future.example")

    def test_transformer_converts_nan_to_none(self):
        df = pd.DataFrame(
            [{"交易日": pd.Timestamp("2025-01-01"), "成交量": None, "履約價": 23000}]
        )

        records = DataTransformer.dataframe_to_records(df)

        self.assertEqual(len(records), 1)
        self.assertIsNone(records[0]["成交量"])
        self.assertIsInstance(records[0]["交易日"], datetime)

    def test_service_crawl_options_returns_day_and_night_sessions(self):
        service = TaifexCrawlerService(fetcher=FakeFetcher(), transformer=DataTransformer())

        sessions = service.crawl_options("https://day.example", "https://night.example")

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

        sessions = service.crawl_options("https://day.example", "https://night.example")

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

        session = service.crawl_futures("https://future.example")

        self.assertEqual(session.session, "future_month")
        self.assertEqual(session.trade_date, "2025/01/01")

        # Check that rows contain only 期貨月份
        for row in session.rows:
            self.assertIn("期貨月份", row)
            self.assertEqual(len(row), 1)

        # Check unique months are extracted
        months = [row["期貨月份"] for row in session.rows]
        self.assertEqual(set(months), {202603, 202604})
        for month in months:
            self.assertIsInstance(month, int)

    def test_extract_month_from_string(self):
        # Test extracting month from various formats
        self.assertEqual(MongoMarketRepository._extract_month_from_string("202603W2"), 202603)
        self.assertEqual(MongoMarketRepository._extract_month_from_string("202603F1"), 202603)
        self.assertEqual(MongoMarketRepository._extract_month_from_string("202604"), 202604)
        self.assertEqual(MongoMarketRepository._extract_month_from_string(""), 0)
        self.assertEqual(MongoMarketRepository._extract_month_from_string(None), 0)

    def test_is_pure_month_value(self):
        # Test identifying pure month values (no weekly suffixes)
        self.assertTrue(MongoMarketRepository._is_pure_month_value("202603"))
        self.assertTrue(MongoMarketRepository._is_pure_month_value("202605"))
        self.assertTrue(MongoMarketRepository._is_pure_month_value(202605))

        self.assertFalse(MongoMarketRepository._is_pure_month_value("202603W2"))
        self.assertFalse(MongoMarketRepository._is_pure_month_value("202603W1"))
        self.assertFalse(MongoMarketRepository._is_pure_month_value("202604F1"))
        self.assertFalse(MongoMarketRepository._is_pure_month_value(""))
        self.assertFalse(MongoMarketRepository._is_pure_month_value(None))

    def test_repository_save_future_months(self):
        fake_collection = FakeCollection()
        months = [{"期貨月份": 202603}, {"期貨月份": 202604}]

        with patch("pymongo.MongoClient") as mock_client:
            mock_client.return_value.__enter__.return_value.__getitem__.return_value.__getitem__.return_value = fake_collection

            repo = MongoMarketRepository("mongodb://localhost", "test_db", "test_col")
            repo.save_future_months(months, "2025/01/01", "https://example.com")

        # Check index was created
        self.assertEqual(len(fake_collection.indexes), 1)
        self.assertEqual(fake_collection.indexes[0][0], "期貨月份")
        self.assertTrue(fake_collection.indexes[0][1])  # unique=True

        # Check updates were made
        self.assertEqual(len(fake_collection.update_calls), 2)
        filt1, payload1, upsert1 = fake_collection.update_calls[0]
        self.assertEqual(filt1, {"期貨月份": 202603})
        self.assertTrue(upsert1)
        self.assertEqual(payload1["$set"]["期貨月份"], 202603)

    def test_repository_save_option_records_filters_by_valid_months(self):
        fake_collection = FakeCollection()
        records = [
            # Pure month values (monthly options)
            {"到期月份(週別)": "202603", "履約價": 23000, "買賣權": "Call", "成交量": 10},
            {"到期月份(週別)": "202604", "履約價": 23100, "買賣權": "Put", "成交量": 5},
            # Weekly options (should be filtered out)
            {"到期月份(週別)": "202603W2", "履約價": 23000, "買賣權": "Call", "成交量": 7},
            # Invalid month (not in valid_months)
            {"到期月份(週別)": "202605", "履約價": 23200, "買賣權": "Call", "成交量": 3},
        ]
        valid_months = {202603, 202604}  # Only 202603 and 202604 are valid

        with patch("pymongo.MongoClient") as mock_client:
            mock_client.return_value.__enter__.return_value.__getitem__.return_value.__getitem__.return_value = fake_collection

            repo = MongoMarketRepository("mongodb://localhost", "test_db", "test_col")
            saved_count = repo.save_option_records(
                records, "day", "2025/01/01", "https://example.com", valid_months
            )

        # Should only save 2 records (202603 and 202604 monthly options)
        # Weekly options and invalid months are filtered out
        self.assertEqual(saved_count, 2)
        # Verify bulk_write was called with correct number of operations
        self.assertEqual(len(fake_collection.bulk_operations), 2)


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
