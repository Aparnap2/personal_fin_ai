"""Unit tests for transaction categorizer."""
import pytest
import pytest_asyncio
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock

from app.models import TransactionCreate
from app.categorizer import Categorizer, categorize_batch, CATEGORIZE_PROMPT


class TestCategorizerPrompt:
    """Test categorization prompt construction."""

    def test_prompt_format(self):
        """Test that prompt is correctly formatted."""
        parser = Categorizer()
        prompt = parser._build_prompt("Uber trip", Decimal("320.00"))

        assert "Uber trip" in prompt
        assert "320" in prompt
        assert "Groceries" in prompt
        assert "Dining" in prompt
        assert "Transport" in prompt


class TestCategorizer:
    """Test cases for Categorizer class."""

    def test_categorizer_initialization(self):
        """Test categorizer can be initialized."""
        categorizer = Categorizer()

        assert categorizer is not None
        assert len(categorizer.categories) > 0
        assert "Groceries" in categorizer.categories
        assert "Dining" in categorizer.categories
        assert "Transport" in categorizer.categories

    def test_categorizer_with_ollama_model(self):
        """Test categorizer with Ollama model."""
        categorizer = Categorizer(model="qwen2.5-coder:3b")

        assert "qwen2.5-coder:3b" in categorizer.model
        assert categorizer.client is not None

    def test_categorizer_with_openai_model(self):
        """Test categorizer with custom model."""
        categorizer = Categorizer(model="gpt-4o-mini")

        assert "gpt-4o-mini" in categorizer.model
        assert categorizer.client is not None


@pytest.mark.asyncio
@pytest.mark.ollama  # Mark as Ollama test
class TestCategorizerOllama:
    """Integration tests for categorizer with Ollama."""

    @pytest_asyncio.fixture(autouse=True)
    async def check_ollama(self):
        """Check if Ollama is available."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:11434/api/tags") as resp:
                    if resp.status != 200:
                        pytest.skip("Ollama not available")
        except Exception:
            pytest.skip("Ollama not available")

    async def test_categorize_swiggy(self):
        """Test categorization of Swiggy transaction."""
        categorizer = Categorizer(model="qwen2.5-coder:3b")

        tx = TransactionCreate(
            date="2024-01-15",
            description="Swiggy order for dinner",
            amount=Decimal("450.00"),
        )

        result = await categorizer.categorize(tx)

        assert result["category"] in ["Dining", "Groceries"]
        assert "confidence" in result
        assert result["description"] == "Swiggy order for dinner"

    async def test_categorize_uber(self):
        """Test categorization of Uber transaction."""
        categorizer = Categorizer(model="qwen2.5-coder:3b")

        tx = TransactionCreate(
            date="2024-01-15",
            description="Uber trip to airport",
            amount=Decimal("320.00"),
        )

        result = await categorizer.categorize(tx)

        assert result["category"] == "Transport"
        assert "confidence" in result

    async def test_categorize_netflix(self):
        """Test categorization of Netflix transaction."""
        categorizer = Categorizer(model="qwen2.5-coder:3b")

        tx = TransactionCreate(
            date="2024-01-15",
            description="Netflix monthly subscription",
            amount=Decimal("499.00"),
        )

        result = await categorizer.categorize(tx)

        assert result["category"] == "Subscriptions"
        assert result["confidence"] > 0.7

    async def test_categorize_electricity(self):
        """Test categorization of electricity bill."""
        categorizer = Categorizer(model="qwen2.5-coder:3b")

        tx = TransactionCreate(
            date="2024-01-15",
            description="Electricity board payment",
            amount=Decimal("2500.00"),
        )

        result = await categorizer.categorize(tx)

        assert result["category"] == "Utilities"

    async def test_categorize_batch(self, sample_transactions):
        """Test batch categorization."""
        categorizer = Categorizer(model="qwen2.5-coder:3b")

        # Convert to TransactionCreate objects
        txs = [
            TransactionCreate(
                date=t["date"],
                description=t["description"],
                amount=Decimal(str(t["amount"])),
            )
            for t in sample_transactions
        ]

        results = await categorizer.categorize_batch(txs, max_concurrent=3)

        assert len(results) == len(sample_transactions)

        # Check categories are assigned
        categories = [r["category"] for r in results]
        assert all(c in ["Groceries", "Dining", "Transport", "Subscriptions",
                        "Utilities", "Shopping", "Entertainment", "Health",
                        "Income", "Savings", "Other"] for c in categories)

        # Check confidence scores
        confidences = [r.get("confidence", 0) for r in results]
        # Most should have confidence > 0
        high_confidence = [c for c in confidences if c > 0.5]
        assert len(high_confidence) > len(sample_transactions) * 0.7

    async def test_categorize_salary(self):
        """Test categorization of salary deposit."""
        categorizer = Categorizer(model="qwen2.5-coder:3b")

        tx = TransactionCreate(
            date="2024-01-15",
            description="Salary deposit from employer",
            amount=Decimal("75000.00"),
        )

        result = await categorizer.categorize(tx)

        assert result["category"] == "Income"


class TestCategorizerMocked:
    """Mocked tests for categorizer."""

    @pytest.mark.asyncio
    async def test_categorize_with_mocked_llm(self):
        """Test categorization with mocked LLM response."""
        categorizer = Categorizer()

        # Mock the OpenAI client response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"category": "Dining", "confidence": 0.95}'

        with patch.object(categorizer.client.chat.completions, "create", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response

            tx = TransactionCreate(
                date="2024-01-15",
                description="Restaurant dinner",
                amount=Decimal("500.00"),
            )

            result = await categorizer.categorize(tx)

            assert result["category"] == "Dining"
            assert result["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_categorize_handles_invalid_json(self):
        """Test categorization handles invalid JSON gracefully."""
        categorizer = Categorizer()

        # Mock invalid JSON response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Not a JSON response"

        with patch.object(categorizer.client.chat.completions, "create", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response

            tx = TransactionCreate(
                date="2024-01-15",
                description="Test transaction",
                amount=Decimal("100.00"),
            )

            result = await categorizer.categorize(tx)

            assert result["category"] == "Other"
            assert result["confidence"] == 0.0
            assert "error" in result

    @pytest.mark.asyncio
    async def test_categorize_handles_api_error(self):
        """Test categorization handles API errors gracefully."""
        categorizer = Categorizer()

        with patch.object(categorizer.client.chat.completions, "create", new_callable=AsyncMock) as mock:
            mock.side_effect = Exception("API error")

            tx = TransactionCreate(
                date="2024-01-15",
                description="Test transaction",
                amount=Decimal("100.00"),
            )

            result = await categorizer.categorize(tx)

            assert result["category"] == "Other"
            assert result["confidence"] == 0.0
            assert "error" in result


class TestCategorizeBatchFunction:
    """Tests for categorize_batch LangGraph function."""

    @pytest.mark.asyncio
    async def test_categorize_batch_empty(self):
        """Test batch categorization with empty list."""
        result = await categorize_batch([])

        assert result.total == 0
        assert len(result.results) == 0

    @pytest.mark.asyncio
    async def test_categorize_batch_processing_time(self):
        """Test batch categorization calculates processing time."""
        import time

        start = time.perf_counter()

        # Mock the categorizer to avoid actual LLM calls
        with patch("app.categorizer.Categorizer") as MockCategorizer:
            mock_instance = Mock()
            mock_instance.categorize_batch = AsyncMock(return_value=[
                {"description": "Test", "category": "Dining", "confidence": 0.9,
                 "processing_time_ms": 100}
            ])
            MockCategorizer.return_value = mock_instance

            result = await categorize_batch([
                {"date": "2024-01-15", "description": "Test", "amount": "100"}
            ])

        assert result.total == 1
        assert result.total_processing_time_ms >= 0


class TestCategoryValidation:
    """Tests for category validation."""

    def test_category_list_complete(self):
        """Test all expected categories are available."""
        from app.models import Category

        expected = [
            "Groceries", "Dining", "Transport", "Utilities", "Shopping",
            "Entertainment", "Health", "Subscriptions", "Income", "Savings", "Other"
        ]

        assert Category.all() == expected

    def test_category_enum_values(self):
        """Test category enum values."""
        from app.models import Category

        assert Category.GROCERIES.value == "Groceries"
        assert Category.DINING.value == "Dining"
        assert Category.TRANSPORT.value == "Transport"
        assert Category.UTILITIES.value == "Utilities"
