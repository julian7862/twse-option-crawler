"""Data transformation utilities."""

from __future__ import annotations

import pandas as pd


class DataTransformer:
    """Transforms DataFrames to domain models."""

    @staticmethod
    def _normalize_nan(value):
        """Convert pandas NA/NaN to None."""
        return None if pd.isna(value) else value

    @classmethod
    def dataframe_to_records(cls, dataframe: pd.DataFrame) -> list[dict]:
        """
        Convert DataFrame to list of dictionaries.

        Args:
            dataframe: Input DataFrame

        Returns:
            List of record dictionaries
        """
        records: list[dict] = []
        for raw in dataframe.to_dict(orient="records"):
            # Remove all spaces from field names for consistency
            # e.g., "到期 月份 (週別)" -> "到期月份(週別)"
            record = {str(key).replace(" ", ""): cls._normalize_nan(value) for key, value in raw.items()}
            if isinstance(record.get("交易日"), pd.Timestamp):
                record["交易日"] = record["交易日"].to_pydatetime()
            records.append(record)
        return records
