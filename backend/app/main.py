"""Personal Finance AI - FastAPI Backend."""
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal
from typing import AsyncGenerator
from uuid import UUID

import litellm
import structlog
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from supabase import AsyncClient

from . import models
from .alerter import create_alert_service, SpendingAlert, AlertConfig
from .categorizer import categorize_batch
from .client import get_async_supabase_client
from .forecaster import generate_forecast
from .parser import CSVParser
from .mock_supabase import get_mock_client

# Configure logging
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)

logger = structlog.get_logger()

# Load LiteLLM config
litellm_settings_path = os.getenv("LITELLM_CONFIG_PATH", "litellm_config.yaml")
if os.path.exists(litellm_settings_path):
    litellm.config_paths = [litellm_settings_path]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """App lifespan handler."""
    logger.info("Starting Personal Finance AI API")
    yield
    logger.info("Shutting down Personal Finance AI API")


app = FastAPI(
    title="Personal Finance AI",
    description="AI-powered personal finance tracking with categorization and forecasting",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependencies
async def get_supabase() -> AsyncClient:
    """Get Supabase client (or mock for testing)."""
    import os
    try:
        return await get_async_supabase_client()
    except ValueError:
        # Return mock client if Supabase not configured
        return get_mock_client()


# Health check
@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# CSV Upload & Processing
@app.post("/api/upload/csv")
async def upload_csv(
    file: UploadFile = File(...),
    user_id: UUID = Header(..., alias="X-User-ID"),
    supabase: AsyncClient = Depends(get_supabase),
) -> models.CSVUploadResponse:
    """
    Upload and parse CSV file.

    Returns parsed transactions ready for categorization.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Must be a CSV file")

    content = await file.read()
    csv_text = content.decode("utf-8")

    # Parse CSV
    parser = CSVParser()
    try:
        transactions = parser.parse(csv_text, str(user_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Record upload
    upload_result = await supabase.table("uploads").insert({
        "user_id": str(user_id),
        "filename": file.filename,
        "row_count": len(transactions),
        "processed": False,
    }).execute()

    return models.CSVUploadResponse(
        filename=file.filename,
        rows_parsed=len(transactions),
        transactions=transactions,  # Already TransactionCreate objects
        upload_id=upload_result.data[0]["id"],
    )


# Batch Categorization
@app.post("/api/categorize")
async def categorize_transactions(
    request: models.TransactionBatch,
) -> models.CategorizeBatchResult:
    """
    Categorize transactions using LLM.

    Returns category predictions with confidence scores.
    """
    # Convert to dict format for LangGraph tool
    tx_dicts = [
        {
            "date": t.date.isoformat() if isinstance(t.date, datetime) else t.date,
            "description": t.description,
            "amount": str(t.amount),
        }
        for t in request.transactions
    ]

    result = await categorize_batch(tx_dicts)

    return models.CategorizeBatchResult(
        results=result.results,
        total=result.total,
        avg_confidence=result.avg_confidence,
        processing_time_ms=result.total_processing_time_ms,
    )


# Save Categorized Transactions
@app.post("/api/transactions")
async def save_transactions(
    transactions: list[models.TransactionCreate],
    user_id: UUID = Header(..., alias="X-User-ID"),
    supabase: AsyncClient = Depends(get_supabase),
) -> dict:
    """Save categorized transactions to database."""
    data = [
        {
            "user_id": str(user_id),
            "date": t.date.isoformat() if isinstance(t.date, datetime) else t.date,
            "description": t.description,
            "amount": str(t.amount),
            "category": t.category,
            "is_income": t.is_income,
            "source": t.source,
        }
        for t in transactions
    ]

    result = await supabase.table("transactions").insert(data).execute()

    return {"inserted": len(result.data), "ids": [r["id"] for r in result.data]}


# Get Transactions
@app.get("/api/transactions")
async def get_transactions(
    user_id: UUID = Header(..., alias="X-User-ID"),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    category: str | None = None,
    limit: int = 100,
    supabase: AsyncClient = Depends(get_supabase),
) -> list[dict]:
    """Get user's transactions with optional filters."""
    query = supabase.table("transactions").select("*").eq(
        "user_id", str(user_id)
    )

    if start_date:
        query = query.gte("date", start_date.isoformat())
    if end_date:
        query = query.lte("date", end_date.isoformat())
    if category:
        query = query.eq("category", category)

    result = query.order("date", desc=True).limit(limit).execute()

    return result.data


# Dashboard Summary
@app.get("/api/dashboard")
async def get_dashboard(
    user_id: UUID = Header(..., alias="X-User-ID"),
    supabase: AsyncClient = Depends(get_supabase),
) -> models.DashboardSummary:
    """Get dashboard summary with spending breakdown."""
    # Get all transactions
    result = await supabase.table("transactions").select("*").eq(
        "user_id", str(user_id)
    ).execute()

    transactions = result.data

    if not transactions:
        return models.DashboardSummary(
            total_income=Decimal("0"),
            total_expense=Decimal("0"),
            net_savings=Decimal("0"),
            category_breakdown={},
            monthly_trend=[],
            budget_status=[],
            recent_transactions=[],
        )

    # Calculate totals
    income = Decimal("0")
    expense = Decimal("0")
    category_totals: dict[str, Decimal] = {}

    for tx in transactions:
        amount = Decimal(str(tx["amount"]))
        if tx.get("is_income", False):
            income += amount
        else:
            expense += amount
            cat = tx.get("category", "Other")
            category_totals[cat] = category_totals.get(cat, Decimal("0")) + amount

    # Get recent transactions
    recent = await supabase.table("transactions").select("*").eq(
        "user_id", str(user_id)
    ).order("date", desc=True).limit(10).execute()

    return models.DashboardSummary(
        total_income=income,
        total_expense=expense,
        net_savings=income - expense,
        category_breakdown={k: float(v) for k, v in category_totals.items()},
        monthly_trend=[],  # TODO: aggregate by month
        budget_status=[],  # TODO: get from budgets table
        recent_transactions=[models.Transaction(**tx) for tx in recent.data],
    )


# Budgets
@app.get("/api/budgets")
async def get_budgets(
    user_id: UUID = Header(..., alias="X-User-ID"),
    month: int | None = None,
    supabase: AsyncClient = Depends(get_supabase),
) -> list[dict]:
    """Get user's budgets."""
    query = supabase.table("budgets").select("*").eq("user_id", str(user_id))
    if month:
        query = query.eq("month", f"{month:02d}")
    result = query.execute()
    return result.data


@app.post("/api/budgets")
async def create_budget(
    budget: models.BudgetCreate,
    supabase: AsyncClient = Depends(get_supabase),
) -> dict:
    """Create or update a budget."""
    data = {
        "user_id": str(budget.user_id),
        "category": budget.category,
        "monthly_limit": str(budget.monthly_limit),
        "month": budget.month.isoformat(),
    }
    result = await supabase.table("budgets").upsert(data).execute()
    return result.data[0]


# Forecast
@app.post("/api/forecast")
async def create_forecast(
    request: models.ForecastRequest,
    supabase: AsyncClient = Depends(get_supabase),
) -> dict:
    """
    Generate spending forecast.

    Uses Prophet for trend prediction + LLM sanity check.
    """
    # Get transactions
    result = await supabase.table("transactions").select("*").eq(
        "user_id", str(request.user_id)
    ).execute()

    transactions = result.data

    if len(transactions) < 5:
        raise HTTPException(
            status_code=400,
            detail="Need at least 5 transactions for forecasting",
        )

    # Generate forecast
    forecast = await generate_forecast(
        transactions=transactions,
        months_ahead=request.months_ahead,
        category=request.category,
    )

    # Save forecast
    forecast_data = {
        "user_id": str(request.user_id),
        "category": request.category,
        "forecast_date": forecast["forecast_date"],
        "predicted_amount": forecast["predicted_amount"],
        "confidence_lower": forecast.get("confidence_lower"),
        "confidence_upper": forecast.get("confidence_upper"),
    }
    await supabase.table("forecasts").insert(forecast_data).execute()

    return forecast


# Alerts
@app.post("/api/alerts/check")
async def check_alerts(
    user_id: UUID = Header(..., alias="X-User-ID"),
    supabase: AsyncClient = Depends(get_supabase),
) -> dict:
    """
    Check spending and send alerts if needed.
    """
    # Get user settings
    user_result = await supabase.table("users").select("*").eq(
        "id", str(user_id)
    ).single().execute()

    user = user_result.data

    # Get budgets
    budget_result = await supabase.table("budgets").select("*").eq(
        "user_id", str(user_id)
    ).execute()

    # Get current month spending
    tx_result = await supabase.table("transactions").select("*").eq(
        "user_id", str(user_id)
    ).execute()

    alert_service = create_alert_service()
    alerts_sent = []

    for budget in budget_result.data:
        category = budget["category"]
        limit = Decimal(budget["monthly_limit"])

        # Calculate current spending for category
        spending = Decimal("0")
        for tx in tx_result.data:
            if tx.get("category") == category and not tx.get("is_income"):
                spending += Decimal(str(tx["amount"]))

        # Check alert
        alert_check = alert_service.check_spending_alert(
            spending=spending,
            budget_limit=limit,
            budget_pct=user.get("budget_pct", 110.0),
            threshold=Decimal(str(user.get("alert_threshold", 5000))),
        )

        if alert_check.get("should_alert"):
            alert = SpendingAlert(
                user_id=str(user_id),
                category=category,
                current_spending=spending,
                budget_limit=limit,
                budget_pct_used=alert_check["pct_used"],
                is_over_budget=alert_check["over_budget"],
                is_over_threshold=alert_check["over_threshold"],
            )

            config = AlertConfig(
                user_id=str(user_id),
                budget_pct=user.get("budget_pct", 110.0),
                alert_threshold=Decimal(str(user.get("alert_threshold", 5000))),
                sms_enabled=user.get("sms_enabled", False),
                email_enabled=user.get("email_enabled", True),
                phone=user.get("phone"),
                email=user.get("email"),
            )

            results = await alert_service.send_spending_alert(config, alert)
            alerts_sent.extend(results)

    return {"alerts_sent": len(alerts_sent), "results": alerts_sent}


# User Settings
@app.get("/api/users/me")
async def get_user(
    user_id: UUID = Header(..., alias="X-User-ID"),
    supabase: AsyncClient = Depends(get_supabase),
) -> dict:
    """Get current user profile."""
    result = await supabase.table("users").select("*").eq(
        "id", str(user_id)
    ).single().execute()
    return result.data


@app.put("/api/users/me")
async def update_user(
    preferences: models.UserPreferences,
    user_id: UUID = Header(..., alias="X-User-ID"),
    supabase: AsyncClient = Depends(get_supabase),
) -> dict:
    """Update user preferences."""
    data = preferences.model_dump()
    result = await supabase.table("users").update(data).eq(
        "id", str(user_id)
    ).execute()
    return result.data[0]


# Error handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception) -> JSONResponse:
    """Global error handler."""
    logger.error("Unhandled exception", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
