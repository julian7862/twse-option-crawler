"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DAY_URL = "https://www.taifex.com.tw/cht/3/optDailyMarketExcel"
DEFAULT_NIGHT_URL = DEFAULT_DAY_URL + "?marketCode=1"


@dataclass(frozen=True)
class CrawlerConfig:
    """Configuration for TAIFEX crawler."""

    mongo_uri: str
    mongo_db: str = "market_data"
    mongo_collection: str = "taifex_option_daily"
    day_url: str = DEFAULT_DAY_URL
    night_url: str = DEFAULT_NIGHT_URL

    @classmethod
    def from_env(cls) -> CrawlerConfig:
        """
        Load configuration from environment variables.

        Supports two modes:
        1. Local development: Load from .env file (if exists)
        2. CI/CD (GitHub Actions): Load from environment variables directly
        """
        # Try to load .env file if it exists (for local development)
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists():
            from dotenv import load_dotenv
            load_dotenv(env_file)

        # Read from environment variables (works for both local and CI/CD)
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            raise RuntimeError("MONGO_URI environment variable is required")

        return cls(
            mongo_uri=mongo_uri,
            mongo_db=os.getenv("MONGO_DB", "market_data"),
            mongo_collection=os.getenv("MONGO_COLLECTION", "taifex_option_daily"),
            day_url=os.getenv("TAIFEX_DAY_URL", DEFAULT_DAY_URL),
            night_url=os.getenv("TAIFEX_NIGHT_URL", DEFAULT_NIGHT_URL),
        )
