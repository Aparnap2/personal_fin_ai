"""Mock Supabase client for testing without real credentials."""
from typing import Any
from datetime import datetime

import structlog

logger = structlog.get_logger()


class MockAsyncClient:
    """Mock Supabase async client for local testing."""

    def __init__(self):
        self.storage = MockStorage()
        self.auth = MockAuth()
        self._data = {
            "transactions": [],
            "budgets": [],
            "forecasts": [],
            "uploads": [],
            "users": [],
        }
        logger.warning("Using MOCK Supabase client - data not persisted!")

    def table(self, name):
        """Return mock table interface."""
        return MockTable(name, self._data)


class MockTable:
    """Mock table interface."""

    def __init__(self, table_name: str, data_store: dict):
        self._table_name = table_name
        self._data = data_store
        self._items = []
        self._filters = {}
        self._order_col = None
        self._order_desc = False
        self._limit_n = None
        self._pending_data = None

    def select(self, columns: str = "*"):
        """Select columns."""
        self._items = self._data.get(self._table_name, [])
        return self

    def eq(self, column: str, value: Any):
        """Filter by column value."""
        self._items = [i for i in self._items if i.get(column) == value]
        return self

    def gte(self, column: str, value: Any):
        """Filter greater than or equal."""
        self._items = [i for i in self._items if i.get(column, 0) >= value]
        return self

    def lte(self, column: str, value: Any):
        """Filter less than or equal."""
        self._items = [i for i in self._items if i.get(column, 0) <= value]
        return self

    def order(self, column: str, desc: bool = False):
        """Order by column."""
        self._order_col = column
        self._order_desc = desc
        return self

    def limit(self, n: int):
        """Limit results."""
        self._limit_n = n
        return self

    def single(self):
        """Get single result."""
        self._items = self._items[0] if self._items else None
        return self

    def insert(self, data: dict | list):
        """Insert data (returns self for chaining)."""
        self._pending_data = data
        return self

    def upsert(self, data: dict):
        """Upsert data."""
        return self.insert(data)

    def update(self, data: dict):
        """Update data."""
        for item in self._items:
            item.update(data)
        return self

    def execute(self):
        """Execute query (for inserts/upserts, actually perform the operation)."""
        # For insert operations
        if self._pending_data is not None:
            # Handle both single dict and list of dicts
            items_to_insert = self._pending_data if isinstance(self._pending_data, list) else [self._pending_data]
            results = []
            if self._table_name not in self._data:
                self._data[self._table_name] = []
            for item_data in items_to_insert:
                item = {
                    "id": len(self._data[self._table_name]) + 1,
                    **item_data,
                    "created_at": datetime.now().isoformat(),
                }
                self._data[self._table_name].append(item)
                results.append(item)
            self._pending_data = None
            return MockResult(results)

        # For select operations
        # Apply ordering
        if self._order_col:
            self._items = sorted(
                self._items,
                key=lambda x: x.get(self._order_col, ""),
                reverse=self._order_desc
            )
        # Apply limit
        if self._limit_n:
            self._items = self._items[:self._limit_n]
        return MockResult(self._items)

    # Make it awaitable for async compatibility
    def __await__(self):
        """Allow awaiting the table for async compatibility."""
        async def _execute():
            return self.execute()
        return _execute().__await__()


class MockResult:
    """Mock query result."""

    def __init__(self, data: Any):
        self.data = data if isinstance(data, list) else [data]

    @property
    def first(self):
        """Get first item."""
        return self.data[0] if self.data else None

    # Make it awaitable for async compatibility
    def __await__(self):
        """Allow awaiting the result."""
        async def _return_self():
            return self
        return _return_self().__await__()


class MockAuth:
    """Mock auth interface."""

    def __init__(self):
        pass

    async def get_user(self):
        """Get current user."""
        return {"data": {"user": None}}


class MockStorage:
    """Mock storage interface."""

    pass


# Singleton mock client
_mock_client: MockAsyncClient | None = None


def get_mock_client() -> MockAsyncClient:
    """Get or create mock client."""
    global _mock_client
    if _mock_client is None:
        _mock_client = MockAsyncClient()
    return _mock_client


async def get_async_supabase_client():
    """Get async Supabase client (or mock if not configured)."""
    import os

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        logger.info("Supabase not configured, using mock client for testing")
        return get_mock_client()

    # Import and return real client if credentials exist
    from supabase import AsyncClient, create_client, ClientOptions

    options = ClientOptions(
        schema="public",
        auto_refresh_token=True,
    )
    return await create_client(url, key, options)
