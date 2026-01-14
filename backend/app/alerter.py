"""Alert service for SMS (Twilio) and Email (Resend)."""
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AlertChannel(str, Enum):
    """Alert delivery channels."""
    SMS = "sms"
    EMAIL = "email"


class AlertPriority(str, Enum):
    """Alert priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AlertConfig:
    """Alert configuration for a user."""
    user_id: str
    budget_pct: float = 110.0
    alert_threshold: Decimal = Decimal("5000")
    sms_enabled: bool = False
    email_enabled: bool = True
    phone: str | None = None
    email: str | None = None


class AlertMessage(BaseModel):
    """Alert message model."""
    channel: AlertChannel
    priority: AlertPriority
    title: str
    body: str
    metadata: dict[str, Any] = {}


class SpendingAlert(BaseModel):
    """Spending alert data."""
    user_id: str
    category: str
    current_spending: Decimal
    budget_limit: Decimal
    budget_pct_used: float
    is_over_budget: bool
    is_over_threshold: bool
    forecast_trend: str | None = None


def format_currency(amount: Decimal, currency: str = "INR") -> str:
    """Format currency for display."""
    return f"₹{float(amount):,.2f}"


def check_spending_alert(
    spending: Decimal,
    budget_limit: Decimal,
    budget_pct: float = 110.0,
    threshold: Decimal = Decimal("5000"),
) -> dict[str, Any]:
    """
    Check if spending triggers an alert.

    Returns:
        Dict with alert status and details
    """
    pct_used = (float(spending) / float(budget_limit) * 100) if float(budget_limit) > 0 else 0
    over_budget = pct_used >= budget_pct
    over_threshold = float(spending) >= float(threshold)

    # Determine priority
    if pct_used >= 150:
        priority = AlertPriority.CRITICAL
    elif pct_used >= 125:
        priority = AlertPriority.HIGH
    elif over_budget:
        priority = AlertPriority.MEDIUM
    elif over_threshold:
        priority = AlertPriority.LOW
    else:
        return {"should_alert": False}

    return {
        "should_alert": True,
        "priority": priority.value,
        "pct_used": round(pct_used, 1),
        "over_budget": over_budget,
        "over_threshold": over_threshold,
    }


class TwilioClient:
    """Twilio SMS client wrapper."""

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
    ):
        try:
            from twilio.rest import Client

            self.client = Client(account_sid, auth_token)
            self.from_number = from_number
            self._enabled = True
        except ImportError:
            logger.warning("Twilio not installed, SMS disabled")
            self._enabled = False

    async def send_sms(
        self,
        to: str,
        body: str,
    ) -> dict[str, Any]:
        """Send SMS via Twilio."""
        if not self._enabled:
            return {"success": False, "error": "Twilio not configured"}

        try:
            message = self.client.messages.create(
                body=body,
                from_=self.from_number,
                to=to,
            )
            return {
                "success": True,
                "message_sid": message.sid,
                "status": message.status,
            }
        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
            return {"success": False, "error": str(e)}


class ResendClient:
    """Resend email client wrapper."""

    def __init__(self, api_key: str | None = None):
        try:
            import resend

            self._enabled = bool(api_key)
            self.api_key = api_key
            if api_key:
                resend.api_key = api_key
        except ImportError:
            logger.warning("Resend not installed, email disabled")
            self._enabled = False

    async def send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
    ) -> dict[str, Any]:
        """Send email via Resend."""
        if not self._enabled:
            return {"success": False, "error": "Resend not configured"}

        try:
            import resend

            params = {
                "from": "Finance AI <alerts@yourdomain.com>",
                "to": [to],
                "subject": subject,
                "html": html_body,
            }
            if text_body:
                params["text"] = text_body

            response = resend.Emails.send(params)
            return {
                "success": True,
                "id": response.get("id"),
            }
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return {"success": False, "error": str(e)}


class AlertService:
    """Combined alert service."""

    def __init__(
        self,
        twilio: TwilioClient | None = None,
        resend: ResendClient | None = None,
    ):
        self.twilio = twilio
        self.resend = resend

    def build_sms_message(self, alert: SpendingAlert) -> str:
        """Build SMS alert message."""
        status = "OVER BUDGET" if alert.is_over_budget else "High Spending"
        return (
            f"Finance AI Alert: {status}\n"
            f"Category: {alert.category}\n"
            f"Spent: {format_currency(alert.current_spending)}\n"
            f"Budget: {format_currency(alert.budget_limit)}\n"
            f"Used: {alert.budget_pct_used:.0f}%\n"
            f"{'⚠️ Forecast trending up' if alert.forecast_trend == 'increasing' else ''}"
        )

    def build_email_content(self, alert: SpendingAlert) -> tuple[str, str]:
        """Build email subject and body."""
        subject = f"Finance AI Alert: {alert.category} spending at {alert.budget_pct_used:.0f}%"

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #d32f2f;">💰 Spending Alert</h2>
            <p><strong>Category:</strong> {alert.category}</p>
            <p><strong>Current Spending:</strong> {format_currency(alert.current_spending)}</p>
            <p><strong>Budget Limit:</strong> {format_currency(alert.budget_limit)}</p>
            <p><strong>Budget Used:</strong> {alert.budget_pct_used:.1f}%</p>
            <p><strong>Status:</strong> {
                '<span style="color: red;">Over Budget</span>' if alert.is_over_budget else 'Normal'
            }</p>
            {'<p><strong>⚠️ Forecast suggests spending may increase</strong></p>' if alert.forecast_trend == 'increasing' else ''}
            <hr>
            <p style="color: #666; font-size: 12px;">
                Manage your alerts at your dashboard.
            </p>
        </body>
        </html>
        """

        text = f"""
        Spending Alert

        Category: {alert.category}
        Current Spending: {format_currency(alert.current_spending)}
        Budget Limit: {format_currency(alert.budget_limit)}
        Budget Used: {alert.budget_pct_used:.1f}%
        Status: {'Over Budget' if alert.is_over_budget else 'Normal'}
        """

        return subject, html, text

    async def send_spending_alert(
        self,
        config: AlertConfig,
        alert: SpendingAlert,
    ) -> list[dict[str, Any]]:
        """
        Send spending alert via configured channels.

        Returns:
            List of send results
        """
        results = []

        # SMS alert
        if config.sms_enabled and config.phone and self.twilio:
            message = self.build_sms_message(alert)
            result = await self.twilio.send_sms(config.phone, message)
            result["channel"] = AlertChannel.SMS.value
            results.append(result)

        # Email alert
        if config.email_enabled and config.email and self.resend:
            subject, html, text = self.build_email_content(alert)
            result = await self.resend.send_email(
                to=config.email,
                subject=subject,
                html_body=html,
                text_body=text,
            )
            result["channel"] = AlertChannel.EMAIL.value
            results.append(result)

        return results


# Factory function for creating alert service
def create_alert_service() -> AlertService:
    """Create alert service from environment variables."""
    import os

    twilio = None
    if os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN"):
        twilio = TwilioClient(
            account_sid=os.getenv("TWILIO_ACCOUNT_SID"),
            auth_token=os.getenv("TWILIO_AUTH_TOKEN"),
            from_number=os.getenv("TWILIO_FROM_NUMBER", "+1234567890"),
        )

    resend = None
    if os.getenv("RESEND_API_KEY"):
        resend = ResendClient(api_key=os.getenv("RESEND_API_KEY"))

    return AlertService(twilio=twilio, resend=resend)
