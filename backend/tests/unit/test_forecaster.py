"""Unit tests for forecaster."""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock

from app.models import TransactionCreate
from app.forecaster import (
    prepare_prophet_data,
    forecast_with_prophet,
    calculate_history_summary,
)


class TestPrepareProphetData:
    """Test Prophet data preparation."""

    def test_prepare_prophet_data_empty(self):
        """Test with empty transactions."""
        with pytest.raises(ValueError, match="No transactions found"):
            prepare_prophet_data([])

    def test_prepare_prophet_data_filters_income(self):
        """Test that income transactions are filtered."""
        transactions = [
            TransactionCreate(
                date=datetime.now(),
                description="Salary",
                amount=Decimal("50000"),
                is_income=True,
            ),
        ]

        with pytest.raises(ValueError, match="No transactions found"):
            prepare_prophet_data(transactions)

    def test_prepare_prophet_data_filters_category(self):
        """Test category filtering."""
        transactions = [
            TransactionCreate(
                date=datetime.now(),
                description="Food",
                amount=Decimal("500"),
                category="Dining",
            ),
            TransactionCreate(
                date=datetime.now(),
                description="Grocery",
                amount=Decimal("1000"),
                category="Groceries",
            ),
        ]

        df = prepare_prophet_data(transactions, category="Dining")

        assert len(df) == 1
        assert "ds" in df.columns
        assert "y" in df.columns

    def test_prepare_prophet_data_structure(self, sample_forecast_transactions):
        """Test Prophet data structure."""
        # Convert to Transaction objects
        txs = [
            TransactionCreate(
                date=t["date"],
                description=t["description"],
                amount=Decimal(str(t["amount"])),
                category=t.get("category"),
                is_income=t.get("is_income", False),
            )
            for t in sample_forecast_transactions
        ]

        df = prepare_prophet_data(txs, category="Groceries")

        # Check structure
        assert "ds" in df.columns
        assert "y" in df.columns
        assert len(df) >= 30  # At least 30 days

        # Check data types
        assert df["ds"].dtype is not None
        assert df["y"].dtype is not None


class TestForecastWithProphet:
    """Test Prophet forecasting."""

    def test_forecast_structure(self, sample_forecast_transactions):
        """Test forecast output structure."""
        # Prepare data
        txs = [
            TransactionCreate(
                date=t["date"],
                description=t["description"],
                amount=Decimal(str(t["amount"])),
                category=t.get("category"),
                is_income=t.get("is_income", False),
            )
            for t in sample_forecast_transactions
        ]

        df = prepare_prophet_data(txs, category="Groceries")

        # Generate forecast
        result = forecast_with_prophet(df, periods=30, category="Groceries")

        # Check structure
        assert "category" in result
        assert "forecast_date" in result
        assert "predicted_amount" in result
        assert "confidence_lower" in result
        assert "confidence_upper" in result
        assert "trend" in result

    def test_forecast_has_values(self, sample_forecast_transactions):
        """Test forecast produces reasonable values."""
        txs = [
            TransactionCreate(
                date=t["date"],
                description=t["description"],
                amount=Decimal(str(t["amount"])),
                category=t.get("category"),
                is_income=t.get("is_income", False),
            )
            for t in sample_forecast_transactions
        ]

        df = prepare_prophet_data(txs, category="Groceries")
        result = forecast_with_prophet(df, periods=30, category="Groceries")

        # Predicted amount should be reasonable (absolute value)
        assert abs(result["predicted_amount"]) < 10000  # Reasonable upper bound

        # Confidence interval should contain prediction
        assert result["confidence_lower"] <= result["predicted_amount"]
        assert result["predicted_amount"] <= result["confidence_upper"]

    def test_forecast_date_format(self, sample_forecast_transactions):
        """Test forecast date is ISO format."""
        txs = [
            TransactionCreate(
                date=t["date"],
                description=t["description"],
                amount=Decimal(str(t["amount"])),
                category=t.get("category"),
                is_income=t.get("is_income", False),
            )
            for t in sample_forecast_transactions
        ]

        df = prepare_prophet_data(txs, category="Groceries")
        result = forecast_with_prophet(df, periods=30, category="Groceries")

        # Check date is valid ISO format
        import datetime as dt
        dt.datetime.fromisoformat(result["forecast_date"])


class TestHistorySummary:
    """Test history summary calculation."""

    def test_history_summary_empty(self):
        """Test with empty transactions."""
        result = calculate_history_summary([])

        assert result["count"] == 0
        assert result["total"] == 0

    def test_history_summary_single(self):
        """Test with single transaction."""
        transactions = [
            TransactionCreate(
                date=datetime.now(),
                description="Test",
                amount=Decimal("500"),
                category="Dining",
            ),
        ]

        result = calculate_history_summary(transactions)

        assert result["count"] == 1
        assert result["total"] == 500

    def test_history_summary_multiple(self):
        """Test with multiple transactions."""
        base_date = datetime.now() - timedelta(days=30)
        transactions = [
            TransactionCreate(
                date=base_date + timedelta(days=i),
                description=f"Test {i}",
                amount=Decimal(str(500 + i * 10)),
                category="Groceries",
            )
            for i in range(30)
        ]

        result = calculate_history_summary(transactions)

        assert result["count"] == 30
        assert result["total"] > 0
        assert result["avg_daily"] > 0
        assert result["avg_monthly"] > 0
        assert result["max_single"] >= result["min_single"]

    def test_history_summary_with_category_filter(self):
        """Test category filtering in summary."""
        base_date = datetime.now()
        transactions = [
            TransactionCreate(
                date=base_date,
                description="Grocery",
                amount=Decimal("500"),
                category="Groceries",
            ),
            TransactionCreate(
                date=base_date,
                description="Dining",
                amount=Decimal("300"),
                category="Dining",
            ),
            TransactionCreate(
                date=base_date,
                description="More groceries",
                amount=Decimal("400"),
                category="Groceries",
            ),
        ]

        # Filter by category
        result = calculate_history_summary(transactions, category="Groceries")

        assert result["count"] == 2
        assert result["total"] == 900  # 500 + 400

        # Without filter
        result_all = calculate_history_summary(transactions)
        assert result_all["count"] == 3


class TestForecasterEdgeCases:
    """Edge case tests for forecaster."""

    def test_forecast_insufficient_data(self):
        """Test with insufficient data for forecasting."""
        transactions = [
            TransactionCreate(
                date=datetime.now(),
                description="Test",
                amount=Decimal("100"),
                is_income=True,  # Income is filtered out
            ),
        ]

        with pytest.raises(ValueError, match="No transactions found"):
            prepare_prophet_data(transactions)

    def test_forecast_empty_after_category_filter(self):
        """Test when all transactions are filtered by category."""
        transactions = [
            TransactionCreate(
                date=datetime.now(),
                description="Test",
                amount=Decimal("100"),
                category="Income",  # Will be filtered out
                is_income=True,
            ),
        ]

        with pytest.raises(ValueError, match="No transactions found"):
            prepare_prophet_data(transactions, category="Groceries")

    def test_forecast_trend_direction(self, sample_forecast_transactions):
        """Test that trend is calculated."""
        txs = [
            TransactionCreate(
                date=t["date"],
                description=t["description"],
                amount=Decimal(str(t["amount"])),
                category=t.get("category"),
                is_income=t.get("is_income", False),
            )
            for t in sample_forecast_transactions
        ]

        df = prepare_prophet_data(txs, category="Groceries")
        result = forecast_with_prophet(df, periods=30, category="Groceries")

        assert "trend" in result
        # Trend should be a reasonable number
        assert abs(result["trend"]) < 10000
