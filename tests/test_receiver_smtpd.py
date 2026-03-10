import ssl
import tempfile
from asyncio import Queue
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path

import pytest
from aiosmtpd.smtp import AuthResult, LoginPassword

from push8x.config import Bind, Config, ReceiverSmtpd, ReceiverSmtpdAccount
from push8x.constans import Msg, MsgContentFormat, ReceiverType
from push8x.receiver.smtpd import ReceiverSmtpd as ReceiverSmtpdClass
from push8x.receiver.smtpd import (
    ReceiverSmtpdAuthenticator,
    ReceiverSmtpdHandler,
    ReceiverSmtpdHttpAuth,
    ReceiverSmtpdSMTP,
)

# --- Fixtures ---


@dataclass
class MockAccount:
    """Mock account for testing."""

    username: str
    password: str
    from_value: str | None = None
    mark: str = ""


@pytest.fixture
def mock_config(mocker):
    """Create a mock config for testing."""
    config = mocker.MagicMock(spec=Config)
    config.receiver = mocker.MagicMock()
    config.receiver.smtpd = mocker.MagicMock(spec=ReceiverSmtpd)
    config.receiver.smtpd.bind = mocker.MagicMock(spec=Bind)
    config.receiver.smtpd.bind.host = "127.0.0.1"
    config.receiver.smtpd.bind.port = 8025
    config.receiver.smtpd.behind_proxy = False
    config.receiver.smtpd.accounts = []
    config.receiver.smtpd.sender_ip_whitelist = set()
    config.receiver.smtpd.from_value_regex = None
    config.receiver.smtpd.to_value_regex = None
    config.receiver.smtpd.starttls_certfile = None
    config.receiver.smtpd.starttls_keyfile = None
    config.receiver.smtpd.host = "127.0.0.1"
    config.receiver.smtpd.port = 8025
    return config


@pytest.fixture
def mock_accounts():
    """Create mock accounts for testing."""
    return [
        ReceiverSmtpdAccount(
            username="user1@example.com",
            password="password1",
            from_value="noreply@example.com",
            mark="mark1",
        ),
        ReceiverSmtpdAccount(
            username="user2@example.com",
            password="password2",
            from_value=None,
            mark="",
        ),
    ]


# --- Tests for SmtpdAuthenticator ---


class TestSmtpdAuthenticator:
    """Tests for SmtpdAuthenticator class."""

    def test_init(self):
        """Test SmtpdAuthenticator initialization."""
        accounts = [
            MockAccount(username="test@example.com", password="secret"),
        ]
        authenticator = ReceiverSmtpdAuthenticator(accounts)
        assert authenticator.auth is not None

    def test_call_login_success(self, mocker):
        """Test successful LOGIN authentication."""
        accounts = [
            MockAccount(username="test@example.com", password="secret"),
        ]
        authenticator = ReceiverSmtpdAuthenticator(accounts)

        session = mocker.MagicMock()
        auth_data = LoginPassword(login=b"test@example.com", password=b"secret")

        result = authenticator(
            server=mocker.MagicMock(),
            session=session,
            envelope=mocker.MagicMock(),
            mechanism="LOGIN",
            auth_data=auth_data,
        )

        assert result == AuthResult(success=True, handled=True)
        assert hasattr(session, "ext_auth_ext")
        assert session.ext_auth_ext["username"] == "test@example.com"

    def test_call_plain_success(self, mocker):
        """Test successful PLAIN authentication."""
        accounts = [
            MockAccount(username="test@example.com", password="secret"),
        ]
        authenticator = ReceiverSmtpdAuthenticator(accounts)

        session = mocker.MagicMock()
        auth_data = LoginPassword(login=b"test@example.com", password=b"secret")

        result = authenticator(
            server=mocker.MagicMock(),
            session=session,
            envelope=mocker.MagicMock(),
            mechanism="PLAIN",
            auth_data=auth_data,
        )

        assert result == AuthResult(success=True, handled=True)

    def test_call_wrong_password(self, mocker):
        """Test authentication with wrong password."""
        accounts = [
            MockAccount(username="test@example.com", password="secret"),
        ]
        authenticator = ReceiverSmtpdAuthenticator(accounts)

        session = mocker.MagicMock()
        auth_data = LoginPassword(login=b"test@example.com", password=b"wrongpassword")

        result = authenticator(
            server=mocker.MagicMock(),
            session=session,
            envelope=mocker.MagicMock(),
            mechanism="LOGIN",
            auth_data=auth_data,
        )

        assert result == AuthResult(success=False, handled=True)

    def test_call_unknown_user(self, mocker):
        """Test authentication with unknown username."""
        accounts = [
            MockAccount(username="test@example.com", password="secret"),
        ]
        authenticator = ReceiverSmtpdAuthenticator(accounts)

        session = mocker.MagicMock()
        auth_data = LoginPassword(login=b"unknown@example.com", password=b"secret")

        result = authenticator(
            server=mocker.MagicMock(),
            session=session,
            envelope=mocker.MagicMock(),
            mechanism="LOGIN",
            auth_data=auth_data,
        )

        assert result == AuthResult(success=False, handled=True)

    def test_call_unsupported_mechanism(self, mocker):
        """Test authentication with unsupported mechanism."""
        accounts = [
            MockAccount(username="test@example.com", password="secret"),
        ]
        authenticator = ReceiverSmtpdAuthenticator(accounts)

        session = mocker.MagicMock()
        auth_data = LoginPassword(login=b"test@example.com", password=b"secret")

        result = authenticator(
            server=mocker.MagicMock(),
            session=session,
            envelope=mocker.MagicMock(),
            mechanism="CRAM-MD5",
            auth_data=auth_data,
        )

        assert result == AuthResult(success=False, handled=False)

    def test_call_invalid_auth_data(self, mocker):
        """Test authentication with invalid auth_data type."""
        accounts = [
            MockAccount(username="test@example.com", password="secret"),
        ]
        authenticator = ReceiverSmtpdAuthenticator(accounts)

        session = mocker.MagicMock()

        result = authenticator(
            server=mocker.MagicMock(),
            session=session,
            envelope=mocker.MagicMock(),
            mechanism="LOGIN",
            auth_data="invalid",
        )

        assert result == AuthResult(success=False, handled=False)

    def test_call_with_ext_data(self, mocker):
        """Test authentication stores ext data in session."""
        accounts = [
            MockAccount(
                username="test@example.com",
                password="secret",
                from_value="noreply@example.com",
                mark="mymark",
            ),
        ]
        authenticator = ReceiverSmtpdAuthenticator(accounts)

        session = mocker.MagicMock()
        auth_data = LoginPassword(login=b"test@example.com", password=b"secret")

        result = authenticator(
            server=mocker.MagicMock(),
            session=session,
            envelope=mocker.MagicMock(),
            mechanism="LOGIN",
            auth_data=auth_data,
        )

        assert result == AuthResult(success=True, handled=True)
        assert session.ext_auth_ext["from_value"] == "noreply@example.com"
        assert session.ext_auth_ext["mark"] == "mymark"


# --- Tests for ReceiverSmtpdHttpAuth ---


class TestReceiverSmtpdHttpAuth:
    """Tests for ReceiverSmtpdHttpAuth class."""

    def test_init(self, mock_config):
        """Test ReceiverSmtpdHttpAuth initialization."""
        mock_config.receiver.smtpd.accounts = [
            MockAccount(username="test@example.com", password="secret"),
        ]
        http_auth = ReceiverSmtpdHttpAuth(
            config=mock_config,
            smtpd_host="127.0.0.1",
            smtpd_port=8025,
        )

        assert http_auth.response_success_headers[0] == b"Auth-Status: OK"
        assert http_auth.response_failed.status == HTTPStatus.OK

    def test_check_headers_success(self, mock_config):
        """Test successful HTTP auth check."""
        mock_config.receiver.smtpd.accounts = [
            MockAccount(username="test@example.com", password="secret"),
        ]
        http_auth = ReceiverSmtpdHttpAuth(
            config=mock_config,
            smtpd_host="127.0.0.1",
            smtpd_port=8025,
        )

        headers = {
            "auth-user": "test@example.com",
            "auth-pass": "secret",
            "client-ip": "192.168.1.1",
        }

        result = http_auth.auth_nginx_mail_auth_http(headers)
        assert result.status == HTTPStatus.OK
        assert b"Auth-Status: OK" in result.headers

    def test_check_headers_wrong_password(self, mock_config):
        """Test HTTP auth check with wrong password."""
        mock_config.receiver.smtpd.accounts = [
            MockAccount(username="test@example.com", password="secret"),
        ]
        http_auth = ReceiverSmtpdHttpAuth(
            config=mock_config,
            smtpd_host="127.0.0.1",
            smtpd_port=8025,
        )

        headers = {
            "auth-user": "test@example.com",
            "auth-pass": "wrongpassword",
            "client-ip": "192.168.1.1",
        }

        result = http_auth.auth_nginx_mail_auth_http(headers)
        assert result.status == HTTPStatus.OK
        assert b"Auth-Status: Invalid login or password" in result.headers

    def test_check_headers_ip_blocked(self, mock_config):
        """Test HTTP auth check with blocked IP."""
        mock_config.receiver.smtpd.sender_ip_whitelist = {"10.0.0.1"}
        mock_config.receiver.smtpd.accounts = [
            MockAccount(username="test@example.com", password="secret"),
        ]
        http_auth = ReceiverSmtpdHttpAuth(
            config=mock_config,
            smtpd_host="127.0.0.1",
            smtpd_port=8025,
        )

        headers = {
            "auth-user": "test@example.com",
            "auth-pass": "secret",
            "client-ip": "192.168.1.1",  # Not in whitelist
        }

        result = http_auth.auth_nginx_mail_auth_http(headers)
        assert result.status == HTTPStatus.OK
        assert b"Auth-Status: Your IP address not in whitelist" in result.headers

    def test_check_headers_ip_in_whitelist(self, mock_config):
        """Test HTTP auth check with IP in whitelist."""
        mock_config.receiver.smtpd.sender_ip_whitelist = {"192.168.1.1"}
        mock_config.receiver.smtpd.accounts = [
            MockAccount(username="test@example.com", password="secret"),
        ]
        http_auth = ReceiverSmtpdHttpAuth(
            config=mock_config,
            smtpd_host="127.0.0.1",
            smtpd_port=8025,
        )

        headers = {
            "auth-user": "test@example.com",
            "auth-pass": "secret",
            "client-ip": "192.168.1.1",  # In whitelist
        }

        result = http_auth.auth_nginx_mail_auth_http(headers)
        assert result.status == HTTPStatus.OK
        assert b"Auth-Status: OK" in result.headers

    def test_check_headers_missing_credentials(self, mock_config):
        """Test HTTP auth check with missing credentials."""
        mock_config.receiver.smtpd.accounts = [
            MockAccount(username="test@example.com", password="secret"),
        ]
        http_auth = ReceiverSmtpdHttpAuth(
            config=mock_config,
            smtpd_host="127.0.0.1",
            smtpd_port=8025,
        )

        headers = {
            "client-ip": "192.168.1.1",
            # Missing auth-user and auth-pass
        }

        result = http_auth.auth_nginx_mail_auth_http(headers)
        assert result.status == HTTPStatus.OK
        assert b"Auth-Status: Invalid login or password" in result.headers


# --- Tests for SmtpdHandler ---


class TestSmtpdHandler:
    """Tests for SmtpdHandler class."""

    @pytest.fixture
    def handler(self, mock_config):
        """Create a SmtpdHandler for testing."""
        q = Queue()
        return ReceiverSmtpdHandler(config=mock_config, process_q=q)

    @pytest.fixture
    def sample_envelope(self, mocker):
        """Create a sample email envelope."""
        envelope = mocker.MagicMock()
        envelope.original_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Test Subject
Content-Type: text/plain

This is a test email body.
"""
        return envelope

    @pytest.fixture
    def sample_session(self, mocker):
        """Create a sample SMTP session."""
        session = mocker.MagicMock()
        # Explicitly set ext_auth_ext to empty dict for unauthenticated session
        session.ext_auth_ext = {}
        return session

    @pytest.mark.asyncio
    async def test_handle_data_basic(
        self, handler, sample_envelope, sample_session, mocker
    ):
        """Test basic email handling."""
        result = await handler.handle_DATA(
            server=mocker.MagicMock(),
            session=sample_session,
            envelope=sample_envelope,
        )

        assert result == "250 OK"

        # Check message was queued
        msg = handler.q.get_nowait()
        assert msg.from_value == "sender@example.com"
        assert msg.to_value == "recipient@example.com"
        assert msg.title == "Test Subject"
        assert msg.content_format == MsgContentFormat.PLAIN

    @pytest.mark.asyncio
    async def test_handle_data_with_html(self, handler, sample_session, mocker):
        """Test HTML email handling."""
        envelope = mocker.MagicMock()
        envelope.original_content = b"""From: sender@example.com
To: recipient@example.com
Subject: HTML Test
Content-Type: text/html

<html><body>HTML content</body></html>
"""

        result = await handler.handle_DATA(
            server=mocker.MagicMock(),
            session=sample_session,
            envelope=envelope,
        )

        assert result == "250 OK"

        msg = handler.q.get_nowait()
        assert msg.content_format == MsgContentFormat.HTML
        assert "<html>" in msg.content

    @pytest.mark.asyncio
    async def test_handle_data_with_auth(self, handler, sample_envelope, mocker):
        """Test email handling with SMTP AUTH."""
        sample_session = mocker.MagicMock()
        sample_session.ext_auth_ext = {
            "username": "user1@example.com",
            "from_value": "sender@example.com",
            "mark": "testmark",
        }

        result = await handler.handle_DATA(
            server=mocker.MagicMock(),
            session=sample_session,
            envelope=sample_envelope,
        )

        assert result == "250 OK"

        msg = handler.q.get_nowait()
        assert msg.receiver_ext.get("mark") == "testmark"

    @pytest.mark.asyncio
    async def test_handle_data_from_value_mismatch(
        self, handler, sample_envelope, mocker
    ):
        """Test email with mismatched from_value."""
        sample_session = mocker.MagicMock()
        sample_session.ext_auth_ext = {
            "username": "user1@example.com",
            "from_value": "different@example.com",  # Different from envelope
            "mark": "",
        }

        result = await handler.handle_DATA(
            server=mocker.MagicMock(),
            session=sample_session,
            envelope=sample_envelope,
        )

        assert "550" in result
        assert "not equal email from" in result

    @pytest.mark.asyncio
    async def test_handle_data_from_value_regex(
        self, handler, mock_config, sample_envelope, sample_session, mocker
    ):
        """Test email with from_value_regex check."""
        mock_config.receiver.smtpd.from_value_regex = r".*@allowed\.com$"

        result = await handler.handle_DATA(
            server=mocker.MagicMock(),
            session=sample_session,
            envelope=sample_envelope,
        )

        assert "550" in result
        assert "not allowed" in result

    @pytest.mark.asyncio
    async def test_handle_data_from_value_regex_match(
        self, mock_config, sample_session, mocker
    ):
        """Test email matching from_value_regex."""
        mock_config.receiver.smtpd.from_value_regex = r".*@example\.com$"

        q = Queue()
        handler = ReceiverSmtpdHandler(config=mock_config, process_q=q)

        envelope = mocker.MagicMock()
        envelope.original_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Test

Body
"""

        result = await handler.handle_DATA(
            server=mocker.MagicMock(),
            session=sample_session,
            envelope=envelope,
        )

        assert result == "250 OK"

    @pytest.mark.asyncio
    async def test_handle_data_to_value_regex(
        self, mock_config, sample_session, mocker
    ):
        """Test email with to_value_regex check - recipient not allowed."""
        mock_config.receiver.smtpd.to_value_regex = r".*@allowed\.com$"

        q = Queue()
        handler = ReceiverSmtpdHandler(config=mock_config, process_q=q)

        envelope = mocker.MagicMock()
        envelope.original_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Test

Body
"""

        result = await handler.handle_DATA(
            server=mocker.MagicMock(),
            session=sample_session,
            envelope=envelope,
        )

        assert "550" in result
        assert "not allowed" in result

    @pytest.mark.asyncio
    async def test_handle_data_to_value_regex_match(
        self, mock_config, sample_session, mocker
    ):
        """Test email matching to_value_regex - recipient allowed."""
        mock_config.receiver.smtpd.to_value_regex = r".*@example\.com$"

        q = Queue()
        handler = ReceiverSmtpdHandler(config=mock_config, process_q=q)

        envelope = mocker.MagicMock()
        envelope.original_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Test

Body
"""

        result = await handler.handle_DATA(
            server=mocker.MagicMock(),
            session=sample_session,
            envelope=envelope,
        )

        assert result == "250 OK"

    @pytest.mark.asyncio
    async def test_handle_data_with_attachment(
        self, mock_config, sample_session, mocker
    ):
        """Test email handling with attachment."""
        q = Queue()
        handler = ReceiverSmtpdHandler(config=mock_config, process_q=q)

        # Create a multipart email with attachment
        email_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Email with Attachment
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="----=_Part_0"

------=_Part_0
Content-Type: text/plain; charset="utf-8"
Content-Transfer-Encoding: 7bit

This is the email body.

------=_Part_0
Content-Type: text/plain; name="test.txt"
Content-Transfer-Encoding: base64
Content-Disposition: attachment; filename="test.txt"

VGhpcyBpcyBhIHRlc3QgZmlsZS4=

------=_Part_0--
"""
        envelope = mocker.MagicMock()
        envelope.original_content = email_content

        result = await handler.handle_DATA(
            server=mocker.MagicMock(),
            session=sample_session,
            envelope=envelope,
        )

        assert result == "250 OK"

        msg = handler.q.get_nowait()
        assert msg.title == "Email with Attachment"
        assert len(msg.attachments) == 1
        assert msg.attachments[0]["filename"] == "test.txt"
        assert msg.attachments[0]["content_type"] == "text/plain"

    @pytest.mark.asyncio
    async def test_handle_data_with_multiple_attachments(
        self, mock_config, sample_session, mocker
    ):
        """Test email handling with multiple attachments."""
        q = Queue()
        handler = ReceiverSmtpdHandler(config=mock_config, process_q=q)

        # Create a multipart email with multiple attachments
        email_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Email with Multiple Attachments
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="----=_Part_0"

------=_Part_0
Content-Type: text/plain; charset="utf-8"

Email body here.

------=_Part_0
Content-Type: text/plain; name="file1.txt"
Content-Transfer-Encoding: base64
Content-Disposition: attachment; filename="file1.txt"

RmlsZSAxIGNvbnRlbnQ=

------=_Part_0
Content-Type: application/pdf; name="document.pdf"
Content-Transfer-Encoding: base64
Content-Disposition: attachment; filename="document.pdf"

JVBERi0xLjQKJeLjz9MKMSAwIG9iago8PAovVHlwZSAvQ2F0YWxvZwovUGFnZXMgMiAwIFIKPj4K

------=_Part_0--
"""
        envelope = mocker.MagicMock()
        envelope.original_content = email_content

        result = await handler.handle_DATA(
            server=mocker.MagicMock(),
            session=sample_session,
            envelope=envelope,
        )

        assert result == "250 OK"

        msg = handler.q.get_nowait()
        assert len(msg.attachments) == 2

        # Check first attachment
        assert msg.attachments[0]["filename"] == "file1.txt"
        assert msg.attachments[0]["content_type"] == "text/plain"

        # Check second attachment
        assert msg.attachments[1]["filename"] == "document.pdf"
        assert msg.attachments[1]["content_type"] == "application/pdf"

    @pytest.mark.asyncio
    async def test_handle_data_with_html_and_attachment(
        self, mock_config, sample_session, mocker
    ):
        """Test email handling with HTML content and attachment."""
        q = Queue()
        handler = ReceiverSmtpdHandler(config=mock_config, process_q=q)

        # Create a multipart email with HTML and attachment
        email_content = b"""From: sender@example.com
To: recipient@example.com
Subject: HTML Email with Attachment
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="----=_Part_0"

------=_Part_0
Content-Type: text/html; charset="utf-8"

<html><body><h1>HTML Content</h1></body></html>

------=_Part_0
Content-Type: image/png; name="image.png"
Content-Transfer-Encoding: base64
Content-Disposition: attachment; filename="image.png"

iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==

------=_Part_0--
"""
        envelope = mocker.MagicMock()
        envelope.original_content = email_content

        result = await handler.handle_DATA(
            server=mocker.MagicMock(),
            session=sample_session,
            envelope=envelope,
        )

        assert result == "250 OK"

        msg = handler.q.get_nowait()
        # Should detect HTML content
        assert msg.content_format == MsgContentFormat.HTML
        assert "<html>" in msg.content
        # Should have attachment
        assert len(msg.attachments) == 1
        assert msg.attachments[0]["filename"] == "image.png"
        assert msg.attachments[0]["content_type"] == "image/png"

    @pytest.mark.asyncio
    async def test_handle_data_behind_proxy_missing_xclient(self, mock_config, mocker):
        """Test email handling behind proxy without XCLIENT data."""
        mock_config.receiver.smtpd.behind_proxy = True

        q = Queue()
        handler = ReceiverSmtpdHandler(config=mock_config, process_q=q)

        envelope = mocker.MagicMock()
        envelope.original_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Test

Body
"""

        session = mocker.MagicMock()
        # Explicitly set ext_xclient to None (MagicMock would return MagicMock by default)
        session.ext_xclient = None

        result = await handler.handle_DATA(
            server=mocker.MagicMock(),
            session=session,
            envelope=envelope,
        )

        assert "550" in result
        assert "failed to get XCLIENT" in result

    @pytest.mark.asyncio
    async def test_handle_data_behind_proxy_with_xclient(self, mock_config, mocker):
        """Test email handling behind proxy with valid XCLIENT data."""
        import json

        mock_config.receiver.smtpd.behind_proxy = True

        q = Queue()
        handler = ReceiverSmtpdHandler(config=mock_config, process_q=q)

        envelope = mocker.MagicMock()
        envelope.original_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Test

Body
"""

        session = mocker.MagicMock()
        # Set XCLIENT data with LOGIN info
        login_info = {
            "from_value": "sender@example.com",
            "mark": "proxy_mark",
        }
        session.ext_xclient = {
            "ADDR": "192.168.1.100",
            "LOGIN": json.dumps(login_info),
        }

        result = await handler.handle_DATA(
            server=mocker.MagicMock(),
            session=session,
            envelope=envelope,
        )

        assert result == "250 OK"

        msg = handler.q.get_nowait()
        assert msg.receiver_ext.get("mark") == "proxy_mark"

    @pytest.mark.asyncio
    async def test_handle_data_behind_proxy_from_value_mismatch(
        self, mock_config, mocker
    ):
        """Test email behind proxy with mismatched from_value."""
        import json

        mock_config.receiver.smtpd.behind_proxy = True

        q = Queue()
        handler = ReceiverSmtpdHandler(config=mock_config, process_q=q)

        envelope = mocker.MagicMock()
        envelope.original_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Test

Body
"""

        session = mocker.MagicMock()
        # Set XCLIENT with different from_value
        login_info = {
            "from_value": "different@example.com",
            "mark": "",
        }
        session.ext_xclient = {
            "ADDR": "192.168.1.100",
            "LOGIN": json.dumps(login_info),
        }

        result = await handler.handle_DATA(
            server=mocker.MagicMock(),
            session=session,
            envelope=envelope,
        )

        assert "550" in result
        assert "not equal email from" in result

    @pytest.mark.asyncio
    async def test_handle_data_behind_proxy_no_from_value_check(
        self, mock_config, mocker
    ):
        """Test email behind proxy without from_value in XCLIENT."""
        import json

        mock_config.receiver.smtpd.behind_proxy = True

        q = Queue()
        handler = ReceiverSmtpdHandler(config=mock_config, process_q=q)

        envelope = mocker.MagicMock()
        envelope.original_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Test

Body
"""

        session = mocker.MagicMock()
        # No from_value in login_info - should not check
        login_info = {
            "mark": "my_mark",
        }
        session.ext_xclient = {
            "ADDR": "192.168.1.100",
            "LOGIN": json.dumps(login_info),
        }

        result = await handler.handle_DATA(
            server=mocker.MagicMock(),
            session=session,
            envelope=envelope,
        )

        assert result == "250 OK"

        msg = handler.q.get_nowait()
        assert msg.receiver_ext.get("mark") == "my_mark"


# --- Tests for ReceiverSmtpd ---


class TestReceiverSmtpd:
    """Tests for ReceiverSmtpd class."""

    def test_init_no_auth(self, mock_config):
        """Test initialization without accounts."""
        mock_config.receiver.smtpd.accounts = []

        ruler_q = Queue()
        receiver = ReceiverSmtpdClass(config=mock_config, ruler_q=ruler_q)

        assert receiver.authenticator is None
        assert receiver.tls_context is None

    def test_init_with_auth(self, mock_config, mock_accounts):
        """Test initialization with accounts."""
        mock_config.receiver.smtpd.accounts = mock_accounts

        ruler_q = Queue()
        receiver = ReceiverSmtpdClass(config=mock_config, ruler_q=ruler_q)

        assert receiver.authenticator is not None

    def test_init_with_starttls(self, mock_config):
        """Test initialization with STARTTLS."""
        # Create temporary cert and key files
        with tempfile.TemporaryDirectory() as tmpdir:
            cert_path = Path(tmpdir) / "cert.pem"
            key_path = Path(tmpdir) / "key.pem"

            # Generate self-signed certificate
            import datetime

            from cryptography import x509
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.x509.oid import NameOID

            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            subject = issuer = x509.Name(
                [
                    x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
                ]
            )
            now = datetime.datetime.now(datetime.UTC)
            cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(now)
                .not_valid_after(now + datetime.timedelta(days=1))
                .sign(key, hashes.SHA256())
            )

            cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            key_path.write_bytes(
                key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

            mock_config.receiver.smtpd.starttls_certfile = str(cert_path)
            mock_config.receiver.smtpd.starttls_keyfile = str(key_path)

            ruler_q = Queue()
            receiver = ReceiverSmtpdClass(config=mock_config, ruler_q=ruler_q)

            assert receiver.tls_context is not None
            assert isinstance(receiver.tls_context, ssl.SSLContext)

    def test_type_property(self, mock_config):
        """Test type property returns SMTPD."""
        ruler_q = Queue()
        receiver = ReceiverSmtpdClass(config=mock_config, ruler_q=ruler_q)

        assert receiver.type == ReceiverType.SMTPD


# --- Tests for SMTP class ---


class TestSMTPClass:
    """Tests for custom SMTP class."""

    def test_init_without_proxy(self, mocker):
        """Test SMTP initialization without proxy protocol."""
        handler = mocker.MagicMock()
        smtp = ReceiverSmtpdSMTP(behind_proxy=False, handler=handler)
        # Should not have _proxy_timeout set
        assert smtp._proxy_timeout is None

    def test_init_with_proxy(self, mocker):
        """Test SMTP initialization with proxy protocol."""
        handler = mocker.MagicMock()
        smtp = ReceiverSmtpdSMTP(behind_proxy=True, handler=handler)
        # Should have _proxy_timeout set
        assert smtp._proxy_timeout == 3.0


# --- Integration tests ---


class TestIntegration:
    """Integration tests for SMTPd receiver."""

    @pytest.mark.asyncio
    async def test_full_flow_no_auth(self, mock_config, mocker):
        """Test full email flow without authentication."""
        mock_config.receiver.smtpd.accounts = []

        ruler_q = Queue()
        receiver = ReceiverSmtpdClass(config=mock_config, ruler_q=ruler_q)

        # Simulate receiving an email
        q = receiver.q
        await q.put(
            Msg(
                receiver=ReceiverType.SMTPD,
                receiver_smtpd_session=mocker.MagicMock(),
                receiver_webhook_headers=None,
                receiver_ext={},
                ruler_matched_rules=[],
                from_name="Sender",
                from_value="sender@example.com",
                to_name="Recipient",
                to_value="recipient@example.com",
                title="Test",
                content="Body",
                content_format=MsgContentFormat.PLAIN,
                attachments=[],
                ext={},
            )
        )

        # Message should be in queue
        assert q.qsize() == 1

    @pytest.mark.asyncio
    async def test_authenticator_integration(self, mock_accounts, mocker):
        """Test authenticator integration with accounts."""
        authenticator = ReceiverSmtpdAuthenticator(mock_accounts)

        # Test with valid credentials
        session = mocker.MagicMock()
        auth_data = LoginPassword(login=b"user1@example.com", password=b"password1")

        result = authenticator(
            server=mocker.MagicMock(),
            session=session,
            envelope=mocker.MagicMock(),
            mechanism="LOGIN",
            auth_data=auth_data,
        )

        assert result.success is True
        assert session.ext_auth_ext["from_value"] == "noreply@example.com"
        assert session.ext_auth_ext["mark"] == "mark1"
