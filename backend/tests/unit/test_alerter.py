"""Unit tests for alert service."""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock

from app.alerter import (
    AlertService,
    AlertConfig,
    SpendingAlert,
    TwilioClient,
    ResendClient,
    check_spending_alert,
    format_currency,
)


class TestFormatCurrency:
    """Test currency formatting."""

    def test_format_currency_inr(self):
        """Test INR currency formatting."""
        result = format_currency(Decimal("1234.56"))
        assert "₹" in result
        assert "1,234" in result or "1234" in result

    def test_format_currency_zero(self):
        """Test formatting zero amount."""
        result = format_currency(Decimal("0"))
        assert "0" in result

    def test_format_currency_large(self):
        """Test formatting large amount."""
        result = format_currency(Decimal("100000"))
        assert "1" in result or "100,000" in result or "100000" in result


class TestCheckSpendingAlert:
    """Test spending alert checking."""

    def test_no_alert_under_threshold(self):
        """Test no alert when under threshold."""
        result = check_spending_alert(
            spending=Decimal("3000"),
            budget_limit=Decimal("5000"),
            budget_pct=110.0,
            threshold=Decimal("5000"),
        )

        assert result["should_alert"] is False

    def test_alert_over_budget_pct(self):
        """Test alert when over budget percentage."""
        result = check_spending_alert(
            spending=Decimal("6000"),
            budget_limit=Decimal("5000"),
            budget_pct=110.0,
            threshold=Decimal("5000"),
        )

        assert result["should_alert"] is True
        assert result["pct_used"] >= 110.0
        assert result["over_budget"] is True

    def test_alert_over_absolute_threshold(self):
        """Test alert when over absolute threshold."""
        result = check_spending_alert(
            spending=Decimal("6000"),
            budget_limit=Decimal("10000"),
            budget_pct=110.0,
            threshold=Decimal("5000"),
        )

        assert result["should_alert"] is True
        assert result["over_threshold"] is True

    def test_priority_critical(self):
        """Test critical priority for very high spending."""
        result = check_spending_alert(
            spending=Decimal("9000"),
            budget_limit=Decimal("5000"),
            budget_pct=110.0,
            threshold=Decimal("5000"),
        )

        assert result["should_alert"] is True
        assert result["priority"] == "critical"

    def test_priority_high(self):
        """Test high priority."""
        result = check_spending_alert(
            spending=Decimal("7000"),
            budget_limit=Decimal("5000"),
            budget_pct=110.0,
            threshold=Decimal("5000"),
        )

        assert result["priority"] == "high"

    def test_priority_medium(self):
        """Test medium priority for over budget but not extreme."""
        result = check_spending_alert(
            spending=Decimal("5600"),
            budget_limit=Decimal("5000"),
            budget_pct=110.0,
            threshold=Decimal("5000"),
        )

        assert result["priority"] == "medium"

    def test_priority_low(self):
        """Test low priority for high spending but under budget."""
        result = check_spending_alert(
            spending=Decimal("5500"),
            budget_limit=Decimal("10000"),
            budget_pct=110.0,
            threshold=Decimal("5000"),
        )

        assert result["priority"] == "low"

    def test_zero_budget(self):
        """Test handling zero budget."""
        result = check_spending_alert(
            spending=Decimal("100"),
            budget_limit=Decimal("0"),
            budget_pct=110.0,
            threshold=Decimal("5000"),
        )

        # Should not crash
        assert "should_alert" in result


class TestSpendingAlert:
    """Test SpendingAlert model."""

    def test_spending_alert_creation(self):
        """Test creating spending alert."""
        alert = SpendingAlert(
            user_id="user-123",
            category="Groceries",
            current_spending=Decimal("6000"),
            budget_limit=Decimal("5000"),
            budget_pct_used=120.0,
            is_over_budget=True,
            is_over_threshold=True,
        )

        assert alert.user_id == "user-123"
        assert alert.category == "Groceries"
        assert alert.is_over_budget is True

    def test_spending_alert_with_forecast(self):
        """Test spending alert with forecast trend."""
        alert = SpendingAlert(
            user_id="user-123",
            category="Groceries",
            current_spending=Decimal("6000"),
            budget_limit=Decimal("5000"),
            budget_pct_used=120.0,
            is_over_budget=True,
            is_over_threshold=True,
            forecast_trend="increasing",
        )

        assert alert.forecast_trend == "increasing"


class TestAlertConfig:
    """Test AlertConfig."""

    def test_default_config(self):
        """Test default alert configuration."""
        config = AlertConfig(user_id="user-123")

        assert config.budget_pct == 110.0
        assert config.alert_threshold == Decimal("5000")
        assert config.sms_enabled is False
        assert config.email_enabled is True

    def test_custom_config(self):
        """Test custom alert configuration."""
        config = AlertConfig(
            user_id="user-123",
            budget_pct=120.0,
            alert_threshold=Decimal("10000"),
            sms_enabled=True,
            phone="+919876543210",
        )

        assert config.budget_pct == 120.0
        assert config.alert_threshold == Decimal("10000")
        assert config.sms_enabled is True


class TestAlertService:
    """Test AlertService."""

    def test_build_sms_message(self):
        """Test SMS message building."""
        service = AlertService()
        alert = SpendingAlert(
            user_id="user-123",
            category="Groceries",
            current_spending=Decimal("6000"),
            budget_limit=Decimal("5000"),
            budget_pct_used=120.0,
            is_over_budget=True,
            is_over_threshold=True,
        )

        message = service.build_sms_message(alert)

        assert "OVER BUDGET" in message or "High Spending" in message
        assert "Groceries" in message
        assert "₹" in message
        assert "120" in message or "120%" in message

    def test_build_email_content(self):
        """Test email content building."""
        service = AlertService()
        alert = SpendingAlert(
            user_id="user-123",
            category="Groceries",
            current_spending=Decimal("6000"),
            budget_limit=Decimal("5000"),
            budget_pct_used=120.0,
            is_over_budget=True,
            is_over_threshold=True,
        )

        subject, html, text = service.build_email_content(alert)

        assert "Groceries" in subject
        assert "120" in subject
        assert "html" in html.lower()
        assert "Groceries" in html

    @pytest.mark.asyncio
    async def test_send_spending_alert_email_only(self):
        """Test sending alert via email only."""
        # Mock Resend client
        mock_resend = Mock(spec=ResendClient)
        mock_resend.send_email = AsyncMock(return_value={"success": True, "id": "email-123"})

        service = AlertService(resend=mock_resend)
        alert = SpendingAlert(
            user_id="user-123",
            category="Groceries",
            current_spending=Decimal("6000"),
            budget_limit=Decimal("5000"),
            budget_pct_used=120.0,
            is_over_budget=True,
            is_over_threshold=True,
        )

        config = AlertConfig(
            user_id="user-123",
            email_enabled=True,
            email="user@example.com",
        )

        results = await service.send_spending_alert(config, alert)

        assert len(results) == 1
        assert results[0]["success"] is True
        assert results[0]["channel"] == "email"

    @pytest.mark.asyncio
    async def test_send_spending_alert_sms_only(self):
        """Test sending alert via SMS only."""
        # Mock Twilio client
        mock_twilio = Mock(spec=TwilioClient)
        mock_twilio.send_sms = AsyncMock(return_value={"success": True, "message_sid": "SM123"})

        service = AlertService(twilio=mock_twilio)
        alert = SpendingAlert(
            user_id="user-123",
            category="Groceries",
            current_spending=Decimal("6000"),
            budget_limit=Decimal("5000"),
            budget_pct_used=120.0,
            is_over_budget=True,
            is_over_threshold=True,
        )

        config = AlertConfig(
            user_id="user-123",
            sms_enabled=True,
            phone="+919876543210",
        )

        results = await service.send_spending_alert(config, alert)

        assert len(results) == 1
        assert results[0]["success"] is True
        assert results[0]["channel"] == "sms"

    @pytest.mark.asyncio
    async def test_send_spending_alert_both_channels(self):
        """Test sending alert via both SMS and email."""
        mock_twilio = Mock(spec=TwilioClient)
        mock_twilio.send_sms = AsyncMock(return_value={"success": True})

        mock_resend = Mock(spec=ResendClient)
        mock_resend.send_email = AsyncMock(return_value={"success": True})

        service = AlertService(twilio=mock_twilio, resend=mock_resend)
        alert = SpendingAlert(
            user_id="user-123",
            category="Groceries",
            current_spending=Decimal("6000"),
            budget_limit=Decimal("5000"),
            budget_pct_used=120.0,
            is_over_budget=True,
            is_over_threshold=True,
        )

        config = AlertConfig(
            user_id="user-123",
            sms_enabled=True,
            email_enabled=True,
            phone="+919876543210",
            email="user@example.com",
        )

        results = await service.send_spending_alert(config, alert)

        assert len(results) == 2
        assert all(r["success"] for r in results)

    @pytest.mark.asyncio
    async def test_send_spending_alert_disabled_channel(self):
        """Test not sending when channel is disabled."""
        mock_twilio = Mock(spec=TwilioClient)
        mock_twilio.send_sms = AsyncMock(return_value={"success": True})

        service = AlertService(twilio=mock_twilio)
        alert = SpendingAlert(
            user_id="user-123",
            category="Groceries",
            current_spending=Decimal("6000"),
            budget_limit=Decimal("5000"),
            budget_pct_used=120.0,
            is_over_budget=True,
            is_over_threshold=True,
        )

        # SMS disabled
        config = AlertConfig(
            user_id="user-123",
            sms_enabled=False,
        )

        results = await service.send_spending_alert(config, alert)

        assert len(results) == 0
        mock_twilio.send_sms.assert_not_called()


class TestTwilioClient:
    """Test Twilio client."""

    def test_twilio_not_configured(self):
        """Test Twilio when not installed."""
        with patch.dict("sys.modules", {"twilio": None}):
            # Re-import to get fresh module state
            import importlib
            import app.alerter
            importlib.reload(app.alerter)

            client = app.alerter.TwilioClient(
                account_sid="test",
                auth_token="test",
                from_number="+1234567890",
            )

            # Should not crash but be disabled
            assert client._enabled is False


class TestResendClient:
    """Test Resend client."""

    def test_resend_not_configured(self):
        """Test Resend when not configured."""
        client = ResendClient(api_key=None)
        assert client._enabled is False

    def test_resend_configured(self):
        """Test Resend when configured."""
        client = ResendClient(api_key="re_test_key")
        assert client._enabled is True
