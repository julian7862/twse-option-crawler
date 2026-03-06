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
