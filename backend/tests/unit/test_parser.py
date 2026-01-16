"""Unit tests for CSV parser."""
import pytest
from datetime import datetime

from app.parser import CSVParser, parse_csv


class TestCSVParser:
    """Test cases for CSVParser class."""

    def test_detect_columns_standard(self):
        """Test column detection with standard column names."""
        parser = CSVParser()
        import pandas as pd

        df = pd.DataFrame({
            "date": ["2024-01-15"],
            "description": ["Test"],
            "amount": [100.0],
        })

        column_map = parser.detect_columns(df)

        assert column_map["date"] == "date"
        assert column_map["description"] == "description"
        assert column_map["amount"] == "amount"

    def test_detect_columns_alternate(self):
        """Test column detection with alternate column names."""
        parser = CSVParser()
        import pandas as pd

        df = pd.DataFrame({
            "Txn Date": ["2024-01-15"],
            "Payee": ["Test"],
            "Value": [100.0],
        })

        column_map = parser.detect_columns(df)

        assert "date" in column_map
        assert "amount" in column_map

    def test_parse_amount_decimal(self):
        """Test amount parsing with decimal values."""
        from decimal import Decimal
        parser = CSVParser()

        result = parser.parse_amount(1234.56)
        assert result == Decimal("1234.56")

    def test_parse_amount_with_currency_symbol(self):
        """Test amount parsing with currency symbols."""
        from decimal import Decimal
        parser = CSVParser()

        result = parser.parse_amount("₹1,234.56")
        assert result == Decimal("1234.56")

    def test_parse_amount_accounting_format(self):
        """Test amount parsing with accounting format (parentheses)."""
        parser = CSVParser()

        result = parser.parse_amount("(500.00)")
        assert result == 500.0

    def test_parse_amount_integer(self):
        """Test amount parsing with integer."""
        parser = CSVParser()

        result = parser.parse_amount("100")
        assert result == 100.0

    def test_parse_date_standard_format(self):
        """Test date parsing with standard format."""
        parser = CSVParser()

        result = parser.parse_date("2024-01-15")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_date_indian_format(self):
        """Test date parsing with Indian format."""
        parser = CSVParser()

        result = parser.parse_date("15-01-2024")
        assert result.day == 15
        assert result.month == 1
        assert result.year == 2024

    def test_parse_date_slash_format(self):
        """Test date parsing with slash format."""
        parser = CSVParser()

        result = parser.parse_date("01/15/2024")
        assert result.month == 1
        assert result.day == 15

    def test_clean_description(self):
        """Test description cleaning."""
        parser = CSVParser()

        result = parser.clean_description("  Uber   trip  ")
        assert result == "Uber trip"

    def test_clean_description_truncates_long(self):
        """Test description truncation."""
        parser = CSVParser()

        long_desc = "A" * 600
        result = parser.clean_description(long_desc)
        assert len(result) == 500

    def test_parse_valid_csv(self, sample_csv_content):
        """Test parsing valid CSV content."""
        parser = CSVParser()

        transactions = parser.parse(sample_csv_content)

        assert len(transactions) == 5
        assert transactions[0].description == "Swiggy order"
        assert float(transactions[0].amount) == 450.0

    def test_parse_csv_with_mapping(self, sample_csv_alternate):
        """Test parsing CSV with explicit column mapping."""
        parser = CSVParser()

        mapping = {
            "date": "Txn Date",
            "description": "Payee",
            "amount": "Value",
        }

        transactions = parser.parse_with_mapping(sample_csv_alternate, mapping)

        assert len(transactions) == 3
        assert transactions[0].description == "Swiggy"

    def test_parse_csv_missing_required_columns(self):
        """Test parsing CSV with missing required columns."""
        parser = CSVParser()
        import pandas as pd

        df = pd.DataFrame({
            "description": ["Test"],
            # Missing date and amount
        })

        # Create CSV content
        csv_content = df.to_csv(index=False)

        with pytest.raises(ValueError, match="Could not detect required columns"):
            parser.parse(csv_content)

    def test_parse_empty_csv(self):
        """Test parsing empty CSV."""
        parser = CSVParser()

        with pytest.raises(ValueError, match="No valid transactions found"):
            parser.parse("date,description,amount")

    def test_parse_function(self, sample_csv_content):
        """Test parse_csv convenience function."""
        transactions = parse_csv(sample_csv_content)

        assert len(transactions) == 5
        assert all(isinstance(t, dict) for t in transactions)
        assert "date" in transactions[0]
        assert "description" in transactions[0]
        assert "amount" in transactions[0]


class TestCSVParserEdgeCases:
    """Edge case tests for CSVParser."""

    def test_parse_negative_amounts(self):
        """Test parsing negative amounts."""
        parser = CSVParser()

        result = parser.parse_amount("-500.00")
        assert result == 500.0  # Should take absolute value

    def test_parse_whitespace_only(self):
        """Test parsing whitespace-only values."""
        parser = CSVParser()

        with pytest.raises(ValueError):
            parser.parse_amount("   ")

    def test_parse_empty_string(self):
        """Test parsing empty string."""
        parser = CSVParser()

        with pytest.raises(ValueError):
            parser.parse_amount("")

    def test_parse_invalid_number(self):
        """Test parsing invalid number."""
        parser = CSVParser()

        with pytest.raises(ValueError):
            parser.parse_amount("not-a-number")

    def test_parse_pandas_timestamp(self):
        """Test parsing pandas timestamp."""
        import pandas as pd
        parser = CSVParser()

        ts = pd.Timestamp("2024-01-15")
        result = parser.parse_date(ts)

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_python_datetime(self):
        """Test parsing Python datetime."""
        parser = CSVParser()

        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = parser.parse_date(dt)

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
