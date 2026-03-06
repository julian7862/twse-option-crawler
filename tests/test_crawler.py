import os
import sys
from datetime import datetime
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import CrawlerConfig
from src.models import MarketSessionData
from src.service import TaifexCrawlerService
from src.transformer import DataTransformer
from src.repository import MongoMarketRepository


class FakeFetcher:
    def fetch_table(self, url, is_night):
        df = pd.DataFrame(
            [
                {"履約價": 23000, "成交量": 10, "交易日": pd.Timestamp("2025-01-01")},
                {"履約價": 23100, "成交量": None, "交易日": pd.Timestamp("2025-01-01")},
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


if __name__ == "__main__":
    main()
