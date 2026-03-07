"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Try to load .env file if it exists (for local development)
# In CI/CD, this will be skipped and use actual environment variables
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass  # python-dotenv not installed, use system env vars only

DEFAULT_DAY_URL = "https://www.taifex.com.tw/cht/3/optDailyMarketExcel"
DEFAULT_NIGHT_URL = DEFAULT_DAY_URL + "?marketCode=1"


@dataclass(frozen=True)
class CrawlerConfig:
    """Configuration for TAIFEX crawler."""

    mongo_uri: str
    mongo_db: str
    mongo_collection: str
    day_url: str
    night_url: str

    @classmethod
    def from_env(cls) -> CrawlerConfig:
        """
        Load configuration from environment variables.

        Supports:
        - Local development: Reads from .env file (loaded at module level)
        - CI/CD: Reads from system environment variables directly
        """
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            raise RuntimeError("MONGO_URI environment variable is required")

        return cls(
            mongo_uri=mongo_uri,
            mongo_db=os.getenv("MONGO_DB") or "market_data",
            mongo_collection=os.getenv("MONGO_COLLECTION") or "taifex_option_daily",
            day_url=os.getenv("TAIFEX_DAY_URL") or DEFAULT_DAY_URL,
            night_url=os.getenv("TAIFEX_NIGHT_URL") or DEFAULT_NIGHT_URL,
        )
