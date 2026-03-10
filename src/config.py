"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CrawlerConfig:
    """Configuration for TAIFEX crawler."""

    mongo_uri: str
    mongo_db: str
    mongo_collection: str
    day_url: str
    night_url: str

    DEFAULT_MONGO_DB = "market_data"
    DEFAULT_MONGO_COLLECTION = "taifex_option_daily"
    DEFAULT_TAIFEX_DAY_URL = "https://www.taifex.com.tw/cht/3/optDailyMarketExcel"
    DEFAULT_TAIFEX_NIGHT_URL = (
        "https://www.taifex.com.tw/cht/3/optDailyMarketExcel?marketCode=1"
    )

    @classmethod
    def from_env(cls) -> CrawlerConfig:
        """
        Load configuration from environment variables.

        Supports:
        - Local development: Reads from .env file
        - CI/CD: Reads from system environment variables directly

        All values must be set in environment variables or .env file.
        """
        # Try to load .env file if it exists (for local development)
        try:
            from dotenv import load_dotenv
            env_file = Path(__file__).parent.parent / ".env"
            if env_file.exists():
                load_dotenv(env_file)
        except ImportError:
            pass  # python-dotenv not installed, use system env vars only

        # Read from environment variables
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            raise RuntimeError("MONGO_URI environment variable is required")

        mongo_db = os.getenv("MONGO_DB", cls.DEFAULT_MONGO_DB)

        mongo_collection = os.getenv(
            "MONGO_COLLECTION", cls.DEFAULT_MONGO_COLLECTION
        )

        day_url = os.getenv("TAIFEX_DAY_URL", cls.DEFAULT_TAIFEX_DAY_URL)

        night_url = os.getenv("TAIFEX_NIGHT_URL", cls.DEFAULT_TAIFEX_NIGHT_URL)

        return cls(
            mongo_uri=mongo_uri,
            mongo_db=mongo_db,
            mongo_collection=mongo_collection,
            day_url=day_url,
            night_url=night_url,
        )
