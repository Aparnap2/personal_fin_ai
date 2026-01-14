"""CSV Parser for transaction imports."""
import re
from datetime import datetime
from decimal import Decimal
from io import StringIO
from typing import Any

import pandas as pd
from pydantic import ValidationError

from .models import TransactionCreate


class CSVParser:
    """Flexible CSV parser with column mapping detection."""

    # Common column name patterns
    COLUMN_PATTERNS = {
        "date": r"^(date|txn_date|transaction_date|posted_date|time|datetime|timestamp)$",
        "description": r"^(description|desc|payee|merchant|narrative|details|particulars|transaction_type|memo)$",
        "amount": r"^(amount|value|sum|txn_amount|debit|credit|paid|received)$",
    }

    def __init__(self):
        self._column_map: dict[str, str] = {}

    def detect_columns(self, df: pd.DataFrame) -> dict[str, str]:
        """Auto-detect column mappings."""
        column_map = {}
        df_cols = {c.lower(): c for c in df.columns}

        for field, pattern in self.COLUMN_PATTERNS.items():
            for col_lower, col_original in df_cols.items():
                if re.search(pattern, col_lower):
                    column_map[field] = col_original
                    break

        return column_map

    def parse_amount(self, value: Any) -> Decimal:
        """Parse amount, handling various formats."""
        if isinstance(value, (int, float)):
            return Decimal(str(abs(float(value))))

        # Handle string amounts
        cleaned = str(value).strip()

        # Remove currency symbols and separators
        cleaned = re.sub(r"[₹$€£,\s]", "", cleaned)

        # Handle parentheses for negative (accounting format)
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]

        try:
            return Decimal(str(abs(float(cleaned))))
        except ValueError as e:
            raise ValueError(f"Cannot parse amount: {value}") from e

    def parse_date(self, value: Any) -> datetime:
        """Parse date from various formats."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, pd.Timestamp):
            return value.to_pydatetime()

        date_formats = [
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%b %d, %Y",
            "%B %d, %Y",
            "%d %b %Y",
            "%d %B %Y",
        ]

        date_str = str(value).strip()

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        # Try pandas parsing
        try:
            return pd.to_datetime(date_str).to_pydatetime()
        except ValueError as e:
            raise ValueError(f"Cannot parse date: {value}") from e

    def clean_description(self, value: Any) -> str:
        """Clean and normalize description."""
        if pd.isna(value):
            return "Unknown"

        desc = str(value).strip()

        # Remove extra whitespace
        desc = re.sub(r"\s+", " ", desc)

        # Truncate if too long
        return desc[:500]

    def parse(
        self, csv_content: str, user_id: str | None = None
    ) -> list[TransactionCreate]:
        """
        Parse CSV content to transactions.

        Args:
            csv_content: Raw CSV string
            user_id: Optional user ID for validation

        Returns:
            List of TransactionCreate objects
        """
        # Read CSV
        df = pd.read_csv(StringIO(csv_content))

        # Clean column names
        df.columns = df.columns.str.strip()

        # Detect column mapping
        column_map = self.detect_columns(df)

        if "date" not in column_map or "amount" not in column_map:
            raise ValueError(
                f"Could not detect required columns. Found: {list(df.columns)}"
            )

        # Optional: use description or generate placeholder
        has_description = "description" in column_map

        transactions = []
        errors = []

        for idx, row in df.iterrows():
            try:
                # Parse date (required)
                date_val = self.parse_date(row[column_map["date"]])

                # Parse amount (required)
                raw_amount = row[column_map["amount"]]
                amount = self.parse_amount(raw_amount)

                # Determine if income (amount positive vs context)
                is_income = False

                # Parse description (optional)
                description = (
                    self.clean_description(row[column_map["description"]])
                    if has_description
                    else f"Transaction {idx + 1}"
                )

                tx = TransactionCreate(
                    date=date_val,
                    description=description,
                    amount=amount,
                    is_income=is_income,
                    source="csv",
                )
                transactions.append(tx)

            except (ValueError, KeyError) as e:
                errors.append(f"Row {idx + 1}: {e}")
                continue

        if not transactions:
            raise ValueError(f"No valid transactions found. Errors: {errors}")

        return transactions

    def parse_with_mapping(
        self, csv_content: str, column_mapping: dict[str, str]
    ) -> list[TransactionCreate]:
        """
        Parse CSV with explicit column mapping.

        Args:
            csv_content: Raw CSV string
            column_mapping: Explicit mapping {field: column_name}

        Returns:
            List of TransactionCreate objects
        """
        df = pd.read_csv(StringIO(csv_content))

        # Validate mapping
        missing = set(["date", "amount"]) - set(column_mapping.keys())
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        transactions = []

        for idx, row in df.iterrows():
            try:
                date_val = self.parse_date(row[column_mapping["date"]])
                amount = self.parse_amount(row[column_mapping["amount"]])
                description = self.clean_description(
                    row.get(column_mapping.get("description"), f"Transaction {idx + 1}")
                )

                tx = TransactionCreate(
                    date=date_val,
                    description=description,
                    amount=amount,
                    is_income=False,
                    source="csv",
                )
                transactions.append(tx)

            except (ValueError, KeyError) as e:
                continue

        return transactions


def parse_csv(csv_content: str, user_id: str | None = None) -> list[dict]:
    """
    Convenience function for LangGraph integration.

    Returns list of dict representations for serialization.
    """
    parser = CSVParser()
    transactions = parser.parse(csv_content, user_id)
    return [t.model_dump() for t in transactions]
