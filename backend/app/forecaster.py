"""Prophet-based forecasting with LLM sanity check."""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import litellm
import pandas as pd
from prophet import Prophet

from .models import Transaction

logger = logging.getLogger(__name__)


# LLM sanity check prompt
SANITY_CHECK_PROMPT = """You are a financial analyst reviewing a forecast prediction.

Historical spending pattern: {history_summary}
Prophet forecast: ₹{forecast_amount} for {category} on {date}

Is this forecast reasonable given the historical pattern?
Respond with JSON:
{{"is_plausible": true/false, "reason": "brief explanation", "suggested_adjustment": null or number}}

JSON response:"""


def prepare_prophet_data(
    transactions: list[Transaction], category: str | None = None
) -> pd.DataFrame:
    """
    Prepare transaction data for Prophet.

    Args:
        transactions: List of transactions
        category: Optional category filter

    Returns:
        DataFrame with 'ds' (date) and 'y' (amount) columns
    """
    # Filter by category if specified
    if category:
        txs = [t for t in transactions if t.category == category]
    else:
        txs = transactions

    # Exclude income transactions
    txs = [t for t in txs if not t.is_income]

    if not txs:
        raise ValueError("No transactions found for forecasting")

    # Aggregate by date
    df = pd.DataFrame([
        {
            "ds": tx.date.date() if hasattr(tx.date, 'date') else tx.date,
            "y": float(tx.amount),
        }
        for tx in txs
    ])

    if df.empty:
        raise ValueError("No valid data after filtering")

    # Group by date and sum
    df = df.groupby("ds")["y"].sum().reset_index()

    # Fill missing dates with 0
    date_range = pd.date_range(df["ds"].min(), df["ds"].max(), freq="D")
    df = df.set_index("ds").reindex(date_range, fill_value=0).reset_index()
    df.columns = ["ds", "y"]

    return df


def forecast_with_prophet(
    df: pd.DataFrame,
    periods: int = 30,
    category: str | None = None,
) -> dict[str, Any]:
    """
    Generate forecast using Prophet.

    Args:
        df: DataFrame with 'ds' (dates) and 'y' (amounts)
        periods: Days to forecast ahead
        category: Category name for reference

    Returns:
        Forecast results with predictions and confidence intervals
    """
    model = Prophet(
        daily_seasonality=False,
        weekly_seasonality=True,
        yearly_seasonality=True,
        changepoint_prior_scale=0.05,
    )

    # Fit model
    model.fit(df)

    # Create future dataframe
    future = model.make_future_dataframe(periods=periods)

    # Predict
    forecast = model.predict(future)

    # Get last prediction
    last_row = forecast.iloc[-1]

    return {
        "category": category,
        "forecast_date": last_row["ds"].isoformat(),
        "predicted_amount": round(float(last_row["yhat"]), 2),
        "confidence_lower": round(float(last_row["yhat_lower"]), 2),
        "confidence_upper": round(float(last_row["yhat_upper"]), 2),
        "trend": round(float(last_row["trend"]), 2),
        "weekly_seasonality": round(float(last_row["weekly"]), 2),
        "yearly_seasonality": round(float(last_row["yearly"]), 2),
        "forecast_df": forecast.tail(periods + 7).to_dict(orient="records"),
    }


async def sanity_check_forecast(
    forecast: dict[str, Any],
    history_summary: dict[str, Any],
) -> dict[str, Any]:
    """
    Use LLM to sanity check the Prophet forecast.

    Args:
        forecast: Prophet forecast result
        history_summary: Summary statistics of historical data

    Returns:
        LLM assessment with is_plausible flag
    """
    prompt = SANITY_CHECK_PROMPT.format(
        history_summary=json.dumps(history_summary),
        forecast_amount=forecast["predicted_amount"],
        category=forecast.get("category", "All"),
        date=forecast["forecast_date"],
    )

    try:
        response = await litellm.acompletion(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=200,
        )

        content = response.choices[0].message.content or "{}"
        result = json.loads(content)

        # Apply adjustment if suggested
        if result.get("suggested_adjustment"):
            forecast["predicted_amount"] = result["suggested_adjustment"]
            forecast["adjusted"] = True

        forecast["llm_sanity_check"] = {
            "is_plausible": result.get("is_plausible", True),
            "reason": result.get("reason", "No issues detected"),
        }

    except Exception as e:
        logger.warning(f"LLM sanity check failed: {e}")
        forecast["llm_sanity_check"] = {
            "is_plausible": True,
            "reason": "Check skipped due to error",
        }

    return forecast


def calculate_history_summary(
    transactions: list[Transaction], category: str | None = None
) -> dict[str, Any]:
    """Calculate summary statistics for historical data."""
    if category:
        txs = [t for t in transactions if t.category == category]
    else:
        txs = [t for t in transactions if not t.is_income]

    if not txs:
        return {"count": 0, "total": 0, "avg_daily": 0, "avg_monthly": 0}

    amounts = [float(t.amount) for t in txs]
    dates = [t.date for t in txs]

    if len(dates) < 2:
        return {"count": len(amounts), "total": sum(amounts), "avg_daily": 0, "avg_monthly": 0}

    date_range = (max(dates) - min(dates)).days or 1

    return {
        "count": len(amounts),
        "total": round(sum(amounts), 2),
        "avg_daily": round(sum(amounts) / date_range, 2),
        "avg_monthly": round(sum(amounts) / (date_range / 30), 2),
        "max_single": max(amounts) if amounts else 0,
        "min_single": min(amounts) if amounts else 0,
    }


async def generate_forecast(
    transactions: list[dict],
    months_ahead: int = 1,
    category: str | None = None,
) -> dict[str, Any]:
    """
    Main forecast function for LangGraph integration.

    Args:
        transactions: List of transaction dicts
        months_ahead: Number of months to forecast
        category: Optional category filter

    Returns:
        Complete forecast with LLM sanity check
    """
    # Convert to Transaction objects
    txs = [
        Transaction(
            date=t["date"],
            description=t["description"],
            amount=Decimal(str(t["amount"])),
            category=t.get("category"),
            is_income=t.get("is_income", False),
        )
        for t in transactions
    ]

    # Prepare data for Prophet
    df = prepare_prophet_data(txs, category)

    # Calculate periods based on months
    periods = months_ahead * 30

    # Generate forecast
    forecast = forecast_with_prophet(df, periods=periods, category=category)

    # Get history summary for sanity check
    history_summary = calculate_history_summary(txs, category)

    # Run LLM sanity check
    forecast = await sanity_check_forecast(forecast, history_summary)

    # Add metadata
    forecast["generated_at"] = datetime.utcnow().isoformat()
    forecast["input_transactions"] = len(transactions)
    forecast["category_filter"] = category

    return forecast
