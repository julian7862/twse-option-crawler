"""Data persistence layer."""

from __future__ import annotations

from datetime import datetime, timezone

from .models import MarketSessionData


class MongoMarketRepository:
    """Repository for persisting market data to MongoDB."""

    def __init__(self, mongo_uri: str, db_name: str, collection_name: str):
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.collection_name = collection_name

    def save_sessions(self, sessions: list[MarketSessionData]) -> None:
        """
        Save market sessions to MongoDB.

        Args:
            sessions: List of market session data to save
        """
        from pymongo import ASCENDING, MongoClient

        with MongoClient(self.mongo_uri) as client:
            collection = client[self.db_name][self.collection_name]
            collection.create_index(
                [("trade_date", ASCENDING), ("session", ASCENDING)],
                unique=True,
                name="trade_date_session_unique",
            )
            for session in sessions:
                self._upsert_session(collection, session)

    @staticmethod
    def _upsert_session(collection, session: MarketSessionData) -> None:
        """Upsert a single session to the collection."""
        payload = {
            "trade_date": session.trade_date,
            "session": session.session,
            "source_url": session.source_url,
            "fetched_at": datetime.now(timezone.utc),
            "row_count": len(session.rows),
            "rows": session.rows,
        }
        collection.update_one(
            {"trade_date": session.trade_date, "session": session.session},
            {"$set": payload},
            upsert=True,
        )

    def save_future_months(self, months: list[dict], trade_date: str, source_url: str) -> None:
        """
        Save future month data (one document per month).

        Args:
            months: List of month records with 期貨月份 field
            trade_date: Trading date string
            source_url: Source URL for the data

        Unique key: 期貨月份
        """
        from pymongo import MongoClient

        with MongoClient(self.mongo_uri) as client:
            collection = client[self.db_name][self.collection_name]

            # Create unique index on 期貨月份 with partial filter
            # Only apply to documents where session is "future_month"
            collection.create_index(
                "期貨月份",
                unique=True,
                name="future_month_unique",
                partialFilterExpression={"session": "future_month"}
            )

            for month_data in months:
                month_value = month_data["期貨月份"]
                payload = {
                    "session": "future_month",
                    "期貨月份": month_value,
                    "trade_date": trade_date,
                    "source_url": source_url,
                    "fetched_at": datetime.now(timezone.utc),
                }
                collection.update_one(
                    {"期貨月份": month_value},
                    {"$set": payload},
                    upsert=True
                )

    def save_option_records(
        self,
        records: list[dict],
        session: str,
        trade_date: str,
        source_url: str,
        valid_months: set[int]
    ) -> int:
        """
        Save option data (one document per record).

        Args:
            records: List of option records
            session: "day" or "night"
            trade_date: Trading date string
            source_url: Source URL for the data
            valid_months: Set of valid future months for filtering

        Returns:
            Number of records saved

        Unique key: session + 期貨月份 + 履約價 + 買賣權

        Note:
            - Only monthly options are saved (weekly options with W1, W2, F1 suffixes are filtered out)
            - The 到期月份(週別) field is standardized to 期貨月份 (pure 6-digit month number)
        """
        from pymongo import ASCENDING, MongoClient

        with MongoClient(self.mongo_uri) as client:
            collection = client[self.db_name][self.collection_name]

            # Create composite unique index with partial filter
            # Only apply to documents where session is "day" or "night" (not "future_month")
            collection.create_index(
                [
                    ("session", ASCENDING),
                    ("期貨月份", ASCENDING),
                    ("履約價", ASCENDING),
                    ("買賣權", ASCENDING),
                ],
                unique=True,
                name="option_unique_key",
                partialFilterExpression={"session": {"$in": ["day", "night"]}}
            )

            saved_count = 0
            for record in records:
                # Get the expiry month value
                month_str = record.get("到期月份(週別)", "")

                # Filter: only keep pure month values (e.g., "202605", not "202603W2")
                if not self._is_pure_month_value(month_str):
                    continue

                # Convert to integer for validation
                try:
                    month_int = int(month_str)
                except (ValueError, TypeError):
                    continue

                # Check if month is in valid_months
                if month_int not in valid_months:
                    continue

                # Standardize: use 期貨月份 instead of 到期月份(週別)
                payload = {
                    "session": session,
                    "期貨月份": month_int,
                    "履約價": record.get("履約價"),
                    "買賣權": record.get("買賣權"),
                    "trade_date": trade_date,
                    "source_url": source_url,
                    "fetched_at": datetime.now(timezone.utc),
                    **{k: v for k, v in record.items() if k != "到期月份(週別)"}  # Exclude old field
                }

                collection.update_one(
                    {
                        "session": session,
                        "期貨月份": month_int,
                        "履約價": record.get("履約價"),
                        "買賣權": record.get("買賣權"),
                    },
                    {"$set": payload},
                    upsert=True
                )
                saved_count += 1

            return saved_count

    @staticmethod
    def _is_pure_month_value(month_str: str) -> bool:
        """
        Check if the month string is a pure 6-digit month number (without weekly suffixes).

        Examples:
            "202603" -> True (monthly option)
            "202603W2" -> False (weekly option)
            "202603F1" -> False (weekly option)
            202605 -> True (integer)

        Args:
            month_str: Expiry month string or integer

        Returns:
            True if pure month value, False otherwise
        """
        import re

        if not month_str:
            return False

        # Convert to string for regex check
        month_str = str(month_str).strip()

        # Check if it's exactly 6 digits (no suffixes like W1, W2, F1)
        match = re.match(r'^(\d{6})$', month_str)
        return match is not None

    @staticmethod
    def _extract_month_from_string(month_str: str) -> int:
        """
        Extract month number from expiry month string.

        Examples:
            "202603W2" -> 202603
            "202603F2" -> 202603
            "202603" -> 202603

        Args:
            month_str: Expiry month string

        Returns:
            Month number as integer, or 0 if invalid
        """
        import re

        if not month_str:
            return 0
        # Extract first 6 digits
        match = re.match(r'(\d{6})', str(month_str))
        return int(match.group(1)) if match else 0
