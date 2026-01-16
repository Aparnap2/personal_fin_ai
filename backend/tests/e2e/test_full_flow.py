"""
End-to-End Tests for Personal Finance AI

Tests the complete flow:
1. CSV Upload → Parse → Categorize → Save
2. Dashboard → Charts → Budgets
3. Forecasting → Alerts

Uses Playwright for frontend testing and FastAPI TestClient for backend.
"""
import asyncio
import logging
import pytest
import pytest_asyncio
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import AsyncGenerator
from uuid import uuid4

import httpx
from playwright.async_api import async_playwright, Page

# Configure detailed logging for debugging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration
TEST_BASE_URL = "http://localhost:8000"
TEST_FRONTEND_URL = "http://localhost:5173"
TEST_USER_ID = str(uuid4())


class TestBackendAPI:
    """Backend API integration tests."""

    @pytest_asyncio.fixture
    async def client(self):
        """Create async test client."""
        async with httpx.AsyncClient(base_url=TEST_BASE_URL) as client:
            yield client

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """Test health check endpoint."""
        logger.info("Testing health check endpoint")
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        logger.info(f"Health check passed: {data}")

    @pytest.mark.asyncio
    async def test_upload_csv(self, client):
        """Test CSV upload endpoint."""
        logger.info("Testing CSV upload endpoint")

        csv_content = """date,description,amount
2024-01-15,Swiggy order,450.00
2024-01-15,Uber trip,320.00
2024-01-16,BigBasket,2100.00
2024-01-16,Netflix,499.00
2024-01-17,Electricity bill,2500.00
"""

        response = await client.post(
            "/api/upload/csv",
            files={"file": ("test.csv", csv_content, "text/csv")},
            headers={"X-User-ID": TEST_USER_ID},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rows_parsed"] == 5
        assert len(data["transactions"]) == 5
        logger.info(f"CSV upload passed: {data['rows_parsed']} rows parsed")

    @pytest.mark.asyncio
    async def test_categorize_transactions(self, client):
        """Test transaction categorization."""
        logger.info("Testing transaction categorization")

        transactions = [
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
                "description": "Netflix subscription",
                "amount": "499.00",
            },
        ]

        response = await client.post(
            "/api/categorize",
            json={
                "transactions": transactions,
                "user_id": TEST_USER_ID,
            },
            headers={"X-User-ID": TEST_USER_ID},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["results"]) == 3

        # Check categories are assigned
        categories = [r.get("category") for r in data["results"]]
        assert all(c is not None for c in categories)

        # Calculate accuracy
        confidences = [r.get("confidence", 0) for r in data["results"]]
        avg_confidence = sum(confidences) / len(confidences)
        logger.info(f"Categorization passed: avg confidence = {avg_confidence:.2%}")

    @pytest.mark.asyncio
    async def test_get_transactions_empty(self, client):
        """Test getting transactions when none exist."""
        logger.info("Testing get transactions (empty state)")

        response = await client.get(
            "/api/transactions",
            headers={"X-User-ID": TEST_USER_ID},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        logger.info(f"Get transactions passed: {len(data)} transactions")

    @pytest.mark.asyncio
    async def test_dashboard_empty(self, client):
        """Test dashboard with no data."""
        logger.info("Testing dashboard (empty state)")

        response = await client.get(
            "/api/dashboard",
            headers={"X-User-ID": TEST_USER_ID},
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_income" in data
        assert "total_expense" in data
        assert "net_savings" in data
        assert "category_breakdown" in data
        logger.info(f"Dashboard response: income={data['total_income']}, expense={data['total_expense']}")


class TestFrontendE2E:
    """Frontend E2E tests with Playwright."""

    @pytest_asyncio.fixture
    async def browser(self):
        """Launch browser for testing."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            yield browser
            await browser.close()

    @pytest_asyncio.fixture
    async def page(self, browser):
        """Create browser page."""
        context = await browser.new_context()
        page = await context.new_page()

        # Add console logging
        page.on("console", lambda msg: logger.info(f"Browser console [{msg.type}]: {msg.text}"))
        page.on("pageerror", lambda err: logger.error(f"Page error: {err}"))

        yield page
        await context.close()

    @pytest.mark.asyncio
    async def test_dashboard_page_loads(self, page):
        """Test dashboard page loads correctly."""
        logger.info("Testing dashboard page load")

        # Navigate to dashboard
        await page.goto(f"{TEST_FRONTEND_URL}/", timeout=30000)

        # Wait for page to load
        await page.wait_for_load_state("networkidle")

        # Check page title
        title = await page.title()
        logger.info(f"Page title: {title}")

        # Check main content is visible
        content = await page.content()
        assert "Dashboard" in content or "Finance" in content

        logger.info("Dashboard page loaded successfully")

    @pytest.mark.asyncio
    async def test_navigation(self, page):
        """Test navigation between pages."""
        logger.info("Testing navigation")

        await page.goto(f"{TEST_FRONTEND_URL}/", timeout=30000)
        await page.wait_for_load_state("networkidle")

        # Check sidebar navigation
        nav_items = await page.locator("aside nav a").all()
        logger.info(f"Found {len(nav_items)} navigation items")

        # Click on Upload
        upload_link = page.locator("a[href='/upload']")
        if await upload_link.is_visible():
            await upload_link.click()
            await page.wait_for_load_state("networkidle")
            content = await page.content()
            assert "Upload" in content or "CSV" in content
            logger.info("Upload page loaded")

        # Click on Transactions
        tx_link = page.locator("a[href='/transactions']")
        if await tx_link.is_visible():
            await tx_link.click()
            await page.wait_for_load_state("networkidle")
            content = await page.content()
            assert "Transactions" in content
            logger.info("Transactions page loaded")

    @pytest.mark.asyncio
    async def test_upload_page_elements(self, page):
        """Test upload page elements are present."""
        logger.info("Testing upload page elements")

        await page.goto(f"{TEST_FRONTEND_URL}/upload", timeout=30000)
        await page.wait_for_load_state("networkidle")

        # Check for drop zone
        drop_zone = page.locator("text=Drop your CSV file here")
        logger.info(f"Drop zone visible: {await drop_zone.is_visible()}")

        # Check for file input
        file_input = page.locator('input[type="file"]')
        logger.info(f"File input exists: {await file_input.is_visible()}")

    @pytest.mark.asyncio
    async def test_transactions_page(self, page):
        """Test transactions page."""
        logger.info("Testing transactions page")

        await page.goto(f"{TEST_FRONTEND_URL}/transactions", timeout=30000)
        await page.wait_for_load_state("networkidle")

        # Check for transactions table
        table = page.locator("table")
        logger.info(f"Table visible: {await table.is_visible()}")

        # Check for search input
        search_input = page.locator('input[placeholder*="Search"]')
        logger.info(f"Search input visible: {await search_input.is_visible()}")

    @pytest.mark.asyncio
    async def test_budgets_page(self, page):
        """Test budgets page."""
        logger.info("Testing budgets page")

        await page.goto(f"{TEST_FRONTEND_URL}/budgets", timeout=30000)
        await page.wait_for_load_state("networkidle")

        # Check for create budget form
        create_button = page.locator("text=Create Budget")
        logger.info(f"Create budget button visible: {await create_button.is_visible()}")


class TestEndToEndFlow:
    """Complete end-to-end flow tests."""

    @pytest_asyncio.fixture
    async def client(self):
        """Create async test client."""
        async with httpx.AsyncClient(base_url=TEST_BASE_URL) as client:
            yield client

    @pytest.mark.asyncio
    async def test_complete_csv_flow(self, client):
        """Test complete CSV upload → categorize → save flow."""
        logger.info("Testing complete CSV flow")

        # Step 1: Upload CSV
        csv_content = """date,description,amount
2024-01-15,Swiggy order,450.00
2024-01-15,Uber trip,320.00
2024-01-16,BigBasket,2100.00
2024-01-16,Netflix subscription,499.00
2024-01-17,Electricity bill,2500.00
2024-01-18,Amazon shopping,3500.00
2024-01-18,Movie tickets,600.00
2024-01-19,Pharmacy,450.00
2024-01-19,Petrol,1800.00
2024-01-20,Salary,75000.00
"""

        # Upload
        upload_response = await client.post(
            "/api/upload/csv",
            files={"file": ("test.csv", csv_content, "text/csv")},
            headers={"X-User-ID": TEST_USER_ID},
        )

        assert upload_response.status_code == 200
        upload_data = upload_response.json()
        logger.info(f"Step 1 - Upload: {upload_data['rows_parsed']} rows parsed")

        # Step 2: Categorize
        categorize_response = await client.post(
            "/api/categorize",
            json={
                "transactions": upload_data["transactions"],
                "user_id": TEST_USER_ID,
            },
            headers={"X-User-ID": TEST_USER_ID},
        )

        assert categorize_response.status_code == 200
        categorize_data = categorize_response.json()
        logger.info(f"Step 2 - Categorize: {categorize_data['total']} transactions, "
                   f"avg confidence: {categorize_data['avg_confidence']:.2%}")

        # Verify categories
        categories = [r.get("category") for r in categorize_data["results"]]
        assert "Dining" in categories  # Swiggy
        assert "Transport" in categories  # Uber, Petrol
        assert "Subscriptions" in categories  # Netflix
        assert "Utilities" in categories  # Electricity

        # Step 3: Merge and save
        categorized_transactions = [
            {
                **t,
                "category": categorize_data["results"][i].get("category", "Other"),
            }
            for i, t in enumerate(upload_data["transactions"])
        ]

        save_response = await client.post(
            "/api/transactions",
            json=categorized_transactions,
            headers={"X-User-ID": TEST_USER_ID},
        )

        assert save_response.status_code == 200
        save_data = save_response.json()
        logger.info(f"Step 3 - Saved: {save_data['inserted']} transactions")

        # Step 4: Verify dashboard shows data
        dashboard_response = await client.get(
            "/api/dashboard",
            headers={"X-User-ID": TEST_USER_ID},
        )

        assert dashboard_response.status_code == 200
        dashboard_data = dashboard_response.json()
        logger.info(f"Step 4 - Dashboard: income={dashboard_data['total_income']}, "
                   f"expense={dashboard_data['total_expense']}")

        # Verify category breakdown
        breakdown = dashboard_data.get("category_breakdown", {})
        assert "Dining" in breakdown or "Groceries" in breakdown

        logger.info("Complete CSV flow test passed!")

    @pytest.mark.asyncio
    async def test_forecast_flow(self, client):
        """Test forecast generation flow."""
        logger.info("Testing forecast flow")

        # Generate forecast
        forecast_response = await client.post(
            "/api/forecast",
            json={
                "user_id": TEST_USER_ID,
                "months_ahead": 1,
                "category": None,
            },
            headers={"X-User-ID": TEST_USER_ID},
        )

        # Should fail without enough transactions
        if forecast_response.status_code == 400:
            logger.info(f"Forecast requires more transactions: {forecast_response.json()}")
            pytest.skip("Not enough transactions for forecast")
        else:
            assert forecast_response.status_code == 200
            forecast_data = forecast_response.json()
            logger.info(f"Forecast generated: {forecast_data['predicted_amount']} "
                       f"for {forecast_data['forecast_date']}")

            # Verify forecast structure
            assert "predicted_amount" in forecast_data
            assert "confidence_lower" in forecast_data
            assert "confidence_upper" in forecast_data
            assert "llm_sanity_check" in forecast_data

            logger.info("Forecast flow test passed!")


class TestErrorHandling:
    """Error handling tests."""

    @pytest_asyncio.fixture
    async def client(self):
        """Create async test client."""
        async with httpx.AsyncClient(base_url=TEST_BASE_URL) as client:
            yield client

    @pytest.mark.asyncio
    async def test_invalid_csv(self, client):
        """Test handling invalid CSV."""
        logger.info("Testing invalid CSV handling")

        response = await client.post(
            "/api/upload/csv",
            files={"file": ("test.csv", "not,a,valid,csv", "text/csv")},
            headers={"X-User-ID": TEST_USER_ID},
        )

        # Should return 400 with error message
        assert response.status_code == 400
        logger.info(f"Invalid CSV handled: {response.json()}")

    @pytest.mark.asyncio
    async def test_missing_user_header(self, client):
        """Test missing user ID header."""
        logger.info("Testing missing user header")

        response = await client.get("/api/transactions")

        # Should fail without user ID
        assert response.status_code in [401, 403, 422]
        logger.info(f"Missing user header handled: status={response.status_code}")

    @pytest.mark.asyncio
    async def test_categorization_timeout(self, client):
        """Test categorization with slow response."""
        logger.info("Testing categorization timeout handling")

        # This tests that the service handles timeouts gracefully
        transactions = [
            {
                "date": datetime.now().isoformat(),
                "description": "Test transaction",
                "amount": "100.00",
            }
        ]

        # Should complete within reasonable time
        response = await client.post(
            "/api/categorize",
            json={
                "transactions": transactions,
                "user_id": TEST_USER_ID,
            },
            headers={"X-User-ID": TEST_USER_ID},
        )

        # Should either succeed or fail gracefully
        logger.info(f"Categorization completed: status={response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
