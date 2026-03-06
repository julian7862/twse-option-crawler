"""Domain models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketSessionData:
    """Market session data for a specific trade date and session."""

    trade_date: str
    session: str
    source_url: str
    rows: list[dict]
