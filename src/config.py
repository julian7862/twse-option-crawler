"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CrawlerConfig:
    """Configuration for TAIFEX and TWSE crawler."""

    mongo_uri: str
    mongo_db: str
    mongo_collection: str
    day_url: str
    night_url: str
    future_url: str
    twse_taiex_url: str

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

        mongo_db = os.getenv("MONGO_DB")
        if not mongo_db:
            raise RuntimeError("MONGO_DB environment variable is required")

        mongo_collection = os.getenv("MONGO_COLLECTION")
        if not mongo_collection:
            raise RuntimeError("MONGO_COLLECTION environment variable is required")

        day_url = os.getenv("TAIFEX_DAY_URL")
        if not day_url:
            raise RuntimeError("TAIFEX_DAY_URL environment variable is required")

        night_url = os.getenv("TAIFEX_NIGHT_URL")
        if not night_url:
            raise RuntimeError("TAIFEX_NIGHT_URL environment variable is required")

        future_url = os.getenv("TAIFEX_FUTURE_URL")
        if not future_url:
            raise RuntimeError("TAIFEX_FUTURE_URL environment variable is required")

        twse_taiex_url = os.getenv("TWSE_TAIEX_URL")
        if not twse_taiex_url:
            raise RuntimeError("TWSE_TAIEX_URL environment variable is required")

        return cls(
            mongo_uri=mongo_uri,
            mongo_db=mongo_db,
            mongo_collection=mongo_collection,
            day_url=day_url,
            night_url=night_url,
            future_url=future_url,
            twse_taiex_url=twse_taiex_url,
        )
