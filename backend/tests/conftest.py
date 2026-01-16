"""Pytest configuration and fixtures."""
import asyncio
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment
os.environ["LITELLM_CONFIG_PATH"] = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "litellm_config.yaml"
)
os.environ["REDIS_URL"] = "redis://localhost:6379"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_transactions():
    """Sample transactions for testing."""
    return [
        {
            "date": datetime.now().isoformat(),
            "description": "Swiggy order for dinner",
            "amount": "450.00",
        },
        {
            "date": datetime.now().isoformat(),
            "description": "Uber trip to airport",
            "amount": "320.00",
        },
        {
            "date": datetime.now().isoformat(),
            "description": "BigBasket groceries",
            "amount": "2100.00",
        },
        {
            "date": datetime.now().isoformat(),
            "description": "Netflix subscription",
            "amount": "499.00",
        },
        {
            "date": datetime.now().isoformat(),
            "description": "Electricity bill",
            "amount": "2500.00",
        },
        {
            "date": datetime.now().isoformat(),
            "description": "Salary deposit",
            "amount": "75000.00",
            "is_income": True,
        },
        {
            "date": datetime.now().isoformat(),
            "description": "Amazon shopping",
            "amount": "3500.00",
        },
        {
            "date": datetime.now().isoformat(),
            "description": "Movie tickets",
            "amount": "600.00",
        },
        {
            "date": datetime.now().isoformat(),
            "description": "MedPlus pharmacy",
            "amount": "450.00",
        },
        {
            "date": datetime.now().isoformat(),
            "description": "Petrol refill",
            "amount": "1800.00",
        },
    ]


@pytest.fixture
def sample_csv_content():
    """Sample CSV content for parser testing."""
    return """date,description,amount
2024-01-15,Swiggy order,450.00
2024-01-15,Uber trip,320.00
2024-01-16,BigBasket,2100.00
2024-01-16,Netflix,499.00
2024-01-17,Electricity bill,2500.00
"""


@pytest.fixture
def sample_csv_alternate():
    """CSV with alternate column names."""
    return """Txn Date,Payee,Value
15-01-2024,Swiggy,-450.00
15-01-2024,Uber,-320.00
16-01-2024,BigBasket,-2100.00
"""


@pytest.fixture
def mock_user_id():
    """Mock user ID for testing."""
    return uuid4()


@pytest.fixture
def sample_forecast_transactions():
    """Sample transactions for forecasting."""
    base_date = datetime.now() - timedelta(days=90)
    transactions = []
    for i in range(90):
        date = (base_date + timedelta(days=i)).date()
        # Add some randomness but with a trend
        import random
        transactions.append({
            "date": date.isoformat(),
            "description": f"Grocery shopping {i}",
            "amount": str(500 + random.randint(-100, 200)),
            "category": "Groceries",
            "is_income": False,
        })
    return transactions


@pytest.fixture
def sample_budget():
    """Sample budget data."""
    return {
        "category": "Groceries",
        "monthly_limit": "5000.00",
        "month": datetime.now().strftime("%Y-%m-01"),
    }
