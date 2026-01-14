"""Pydantic models for Personal Finance AI."""
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator
import re


class TransactionBase(BaseModel):
    """Base transaction model."""
    date: datetime
    description: str = Field(..., min_length=1, max_length=500)
    amount: Decimal = Field(..., decimal_places=2)
    category: str | None = None
    is_income: bool = False


class TransactionCreate(TransactionBase):
    """Transaction creation model."""
    source: str = "csv"


class Transaction(TransactionCreate):
    """Complete transaction model."""
    id: int
    user_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionBatch(BaseModel):
    """Batch of transactions for processing."""
    transactions: list[TransactionCreate]
    user_id: UUID


class Category(str, Enum):
    """Transaction categories."""
    GROCERIES = "Groceries"
    DINING = "Dining"
    TRANSPORT = "Transport"
    UTILITIES = "Utilities"
    SHOPPING = "Shopping"
    ENTERTAINMENT = "Entertainment"
    HEALTH = "Health"
    SUBSCRIPTIONS = "Subscriptions"
    INCOME = "Income"
    SAVINGS = "Savings"
    OTHER = "Other"

    @classmethod
    def all(cls) -> list[str]:
        return [c.value for c in cls]


class CategorizeResult(BaseModel):
    """Result from categorization."""
    description: str
    category: Category
    confidence: float = Field(..., ge=0, le=1)


class CategorizeBatchResult(BaseModel):
    """Batch categorization results."""
    results: list[CategorizeResult]
    total: int
    processing_time_ms: int


class BudgetBase(BaseModel):
    """Budget model."""
    category: str
    monthly_limit: Decimal = Field(..., decimal_places=2, gt=0)
    month: date


class BudgetCreate(BudgetBase):
    """Budget creation model."""
    user_id: UUID


class Budget(BudgetCreate):
    """Complete budget model."""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ForecastBase(BaseModel):
    """Forecast model."""
    category: str | None = None
    forecast_date: date
    predicted_amount: Decimal = Field(..., decimal_places=2)
    confidence_lower: Decimal | None = None
    confidence_upper: Decimal | None = None


class Forecast(ForecastBase):
    """Complete forecast model."""
    id: int
    user_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class ForecastRequest(BaseModel):
    """Forecast request model."""
    user_id: UUID
    months_ahead: int = Field(default=1, ge=1, le=12)
    category: str | None = None


class AlertType(str, Enum):
    """Alert types."""
    SMS = "sms"
    EMAIL = "email"


class AlertBase(BaseModel):
    """Alert model."""
    type: AlertType
    message: str = Field(..., max_length=500)


class Alert(AlertBase):
    """Complete alert model."""
    id: int
    user_id: UUID
    sent_at: datetime

    class Config:
        from_attributes = True


class AlertSettings(BaseModel):
    """Alert settings model."""
    user_id: UUID
    budget_pct: Annotated[float, Field(ge=100, le=200)] = 110.0
    alert_threshold: Annotated[Decimal, Field(gt=0)] = Decimal("5000")
    sms_enabled: bool = False
    email_enabled: bool = True
    phone: str | None = None
    email: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        # Indian phone number format
        cleaned = re.sub(r"[\s\-()]", "", v)
        if re.match(r"^(\+91)?[6-9]\d{9}$", cleaned):
            return f"+91{cleaned[-10:]}" if len(cleaned) == 10 else cleaned
        raise ValueError("Invalid Indian phone number")


class CSVUploadResponse(BaseModel):
    """CSV upload response."""
    filename: str
    rows_parsed: int
    transactions: list[TransactionCreate]
    upload_id: int


class DashboardSummary(BaseModel):
    """Dashboard summary."""
    total_income: Decimal
    total_expense: Decimal
    net_savings: Decimal
    category_breakdown: dict[str, Decimal]
    monthly_trend: list[dict[str, Any]]
    budget_status: list[dict[str, Any]]
    recent_transactions: list[Transaction]


class UserPreferences(BaseModel):
    """User preferences."""
    currency: str = "INR"
    budget_pct: float = 110.0
    alert_threshold: Decimal = Decimal("5000")
