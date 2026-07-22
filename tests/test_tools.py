"""
Tests for backend tools, particularly the send_email SMTP logic.
Uses mocking to avoid actual network calls.
"""

import os
import smtplib
import sys
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "Friday_OS", "Backend")
)


class TestSendEmail:
    """Test send_email SMTP logic with a mock server."""

    @patch("tools.tools.smtplib.SMTP")
    def test_send_email_success(self, mock_smtp):
        """Verify send_email creates a single SMTP connection and sends."""
        from tools.tools import send_email

        # Mock the SMTP instance
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        # Set up env vars
        with patch.dict(
            os.environ,
            {
                "GMAIL_USER": "test@gmail.com",
                "GMAIL_APP_PASSWORD": "test_password",
            },
        ):
            # Run the tool (it's async, so we need to run it)
            import asyncio

            result = asyncio.run(
                send_email(
                    context=MagicMock(),
                    to_email="recipient@example.com",
                    subject="Test Subject",
                    message="Test message body",
                )
            )

        # Verify single SMTP connection was created
        mock_smtp.assert_called_once_with("smtp.gmail.com", 587)

        # Verify TLS was enabled
        mock_server.starttls.assert_called_once()

        # Verify login was called
        mock_server.login.assert_called_once_with("test@gmail.com", "test_password")

        # Verify sendmail was called
        mock_server.sendmail.assert_called_once()

        # Verify quit was called
        mock_server.quit.assert_called_once()

        # Verify success message
        assert "successfully" in result.lower()

    @patch("tools.tools.smtplib.SMTP")
    def test_send_email_missing_credentials(self, mock_smtp):
        """Verify send_email returns error when credentials are missing."""
        from tools.tools import send_email

        # Clear env vars
        with patch.dict(os.environ, {}, clear=True):
            import asyncio

            result = asyncio.run(
                send_email(
                    context=MagicMock(),
                    to_email="recipient@example.com",
                    subject="Test",
                    message="Test",
                )
            )

        # SMTP should NOT be called if credentials are missing
        mock_smtp.assert_not_called()
        assert "not configured" in result.lower()

    @patch("tools.tools.smtplib.SMTP")
    def test_send_email_smtp_auth_error(self, mock_smtp):
        """Verify send_email handles SMTP authentication errors."""
        from tools.tools import send_email

        mock_server = MagicMock()
        mock_smtp.return_value = mock_server
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(
            535, b"Authentication failed"
        )

        with patch.dict(
            os.environ,
            {
                "GMAIL_USER": "test@gmail.com",
                "GMAIL_APP_PASSWORD": "wrong_password",
            },
        ):
            import asyncio

            result = asyncio.run(
                send_email(
                    context=MagicMock(),
                    to_email="recipient@example.com",
                    subject="Test",
                    message="Test",
                )
            )

        assert "authentication" in result.lower()

    @patch("tools.tools.smtplib.SMTP")
    def test_send_email_single_connection(self, mock_smtp):
        """
        Critical test: Verify only ONE SMTP connection is created.
        This tests the fix for the double-connect bug.
        """
        from tools.tools import send_email

        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        with patch.dict(
            os.environ,
            {
                "GMAIL_USER": "test@gmail.com",
                "GMAIL_APP_PASSWORD": "test_password",
            },
        ):
            import asyncio

            result = asyncio.run(
                send_email(
                    context=MagicMock(),
                    to_email="recipient@example.com",
                    subject="Test",
                    message="Test",
                )
            )

        # SMTP should be called exactly once (not twice as in the original bug)
        assert mock_smtp.call_count == 1
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
