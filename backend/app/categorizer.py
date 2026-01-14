"""LLM-based transaction categorization."""
import json
import time
from decimal import Decimal
from typing import Any

import litellm
from pydantic import BaseModel

from .models import Category, TransactionCreate


# Categorization prompt template
CATEGORIZE_PROMPT = """You are a financial transaction classifier. Classify this transaction into ONE category.

Categories: {categories}

Transaction: "{description}"
Amount: ₹{amount}

Return ONLY a JSON object with this format:
{{"category": "CategoryName", "confidence": 0.95}}

Rules:
- Be strict but accurate
- Use "Other" only if no category fits
- "Subscriptions" = recurring digital services (Netflix, Spotify, SaaS)
- "Dining" = restaurants, cafes, food delivery
- "Groceries" = supermarkets, food items for home
- "Transport" = rides, fuel, public transit
- "Utilities" = electricity, water, internet, phone bills
- "Shopping" = physical goods, clothing, electronics
- "Entertainment" = movies, games, events, hobbies
- "Health" = pharmacy, doctor, fitness
- "Income" = salary, refunds, cash deposits
- "Savings" = transfers to savings, investments

JSON response:"""


class Categorizer:
    """LLM-powered transaction categorizer."""

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self.categories = Category.all()

    def _build_prompt(self, description: str, amount: Decimal) -> str:
        """Build categorization prompt."""
        return CATEGORIZE_PROMPT.format(
            categories=", ".join(self.categories),
            description=description,
            amount=amount,
        )

    async def categorize(
        self, transaction: TransactionCreate
    ) -> dict[str, Any]:
        """
        Categorize a single transaction.

        Returns:
            Dict with category, confidence, and processing time
        """
        start = time.perf_counter()

        prompt = self._build_prompt(
            transaction.description, transaction.amount
        )

        try:
            response = await litellm.acompletion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=100,
            )

            content = response.choices[0].message.content or "{}"

            # Parse JSON response
            result = json.loads(content)

            # Validate category
            category = result.get("category", "Other")
            if category not in self.categories:
                category = "Other"

            confidence = float(result.get("confidence", 0.5))

            return {
                "description": transaction.description,
                "category": category,
                "confidence": confidence,
                "processing_time_ms": int(
                    (time.perf_counter() - start) * 1000
                ),
            }

        except json.JSONDecodeError as e:
            return {
                "description": transaction.description,
                "category": "Other",
                "confidence": 0.0,
                "error": f"Parse error: {e}",
                "processing_time_ms": int((time.perf_counter() - start) * 1000),
            }
        except Exception as e:
            return {
                "description": transaction.description,
                "category": "Other",
                "confidence": 0.0,
                "error": str(e),
                "processing_time_ms": int((time.perf_counter() - start) * 1000),
            }

    async def categorize_batch(
        self, transactions: list[TransactionCreate], max_concurrent: int = 10
    ) -> list[dict[str, Any]]:
        """
        Categorize multiple transactions concurrently.

        Uses semaphore to limit concurrent API calls.
        """
        import asyncio

        semaphore = asyncio.Semaphore(max_concurrent)

        async def categorize_with_limit(tx: TransactionCreate) -> dict[str, Any]:
            async with semaphore:
                return await self.categorize(tx)

        tasks = [categorize_with_limit(tx) for tx in transactions]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append({
                    "description": transactions[i].description,
                    "category": "Other",
                    "confidence": 0.0,
                    "error": str(result),
                    "processing_time_ms": 0,
                })
            else:
                processed.append(result)

        return processed


class CategorizeBatchResult(BaseModel):
    """Batch categorization result."""
    results: list[dict[str, Any]]
    total: int
    avg_confidence: float
    total_processing_time_ms: int


async def categorize_batch(
    transactions: list[dict],
) -> CategorizeBatchResult:
    """
    LangGraph tool function for batch categorization.
    """
    categorizer = Categorizer()

    # Convert dicts to TransactionCreate
    tx_objects = [
        TransactionCreate(
            date=t["date"],
            description=t["description"],
            amount=Decimal(str(t["amount"])),
        )
        for t in transactions
    ]

    results = await categorizer.categorize_batch(tx_objects)

    # Calculate metrics
    valid_confidences = [
        r["confidence"] for r in results if "confidence" in r
    ]
    avg_confidence = (
        sum(valid_confidences) / len(valid_confidences) if valid_confidences else 0
    )

    total_time = sum(
        r.get("processing_time_ms", 0) for r in results
    )

    return CategorizeBatchResult(
        results=results,
        total=len(results),
        avg_confidence=avg_confidence,
        total_processing_time_ms=total_time,
    )
