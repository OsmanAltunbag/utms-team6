"""
Unit tests for NotificationService and notification worker (SPEC-020).
"""

import time
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.enums import NotifChannel, NotifStatus
from app.domain.notification import Notification
from app.services.notification_service import NotificationService
from app.workers.celery_app import celery_app
from app.workers.notification_tasks import (
    RETRY_BASE_SECONDS,
    _retry_delay,
    send_notification_impl,
)


@pytest.fixture
def db():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


def _make_notification(**kwargs) -> Notification:
    n = Notification()
    n.id = kwargs.get("id", uuid.uuid4())
    n.user_id = kwargs.get("user_id", uuid.uuid4())
    n.application_id = kwargs.get("application_id", uuid.uuid4())
    n.channel = NotifChannel.EMAIL
    n.subject = kwargs.get("subject", "Test Subject")
    n.body = kwargs.get("body", "Test body")
    n.template_name = kwargs.get("template_name", "status_changed.html")
    n.template_context = kwargs.get(
        "template_context",
        {"old_status": "Submitted", "new_status": "Verified", "note": "OK"},
    )
    n.status = kwargs.get("status", NotifStatus.PENDING)
    n.retry_count = kwargs.get("retry_count", 0)
    n.max_retries = 5
    n.sent_at = None
    n.error_message = None
    n.created_at = datetime.now(timezone.utc)
    return n


# T1 — Enqueue creates PENDING row and dispatches task
async def test_enqueue_creates_notification_and_dispatches(db):
    service = NotificationService(db)
    service._repo = AsyncMock()
    service._repo.save = AsyncMock(side_effect=lambda n: n)

    user_id = uuid.uuid4()
    with patch.object(service, "_dispatch") as mock_dispatch:
        result = await service.enqueue(
            user_id=user_id,
            subject="UTMS Test",
            body="Hello",
            application_id=uuid.uuid4(),
            template_name="status_changed.html",
            template_context={"new_status": "Verified"},
        )

    service._repo.save.assert_awaited_once()
    mock_dispatch.assert_called_once()
    assert result.subject == "UTMS Test"


# T6 — Delivery log returns application notifications
async def test_get_delivery_log(db):
    service = NotificationService(db)
    app_id = uuid.uuid4()
    expected = [_make_notification(application_id=app_id)]
    service._repo = AsyncMock()
    service._repo.get_by_application = AsyncMock(return_value=expected)

    result = await service.get_delivery_log(app_id)

    assert result == expected
    service._repo.get_by_application.assert_awaited_once_with(app_id)


# T2 — SMTP success marks notification SENT
def test_send_notification_success():
    notif = _make_notification()
    user = MagicMock()
    user.email = "applicant@test.com"

    mock_session = MagicMock()

    def fake_get(model, obj_id):
        from app.domain.notification import Notification as N
        from app.domain.user import User as U
        if model is N:
            return notif
        if model is U:
            return user
        return None

    mock_session.get = MagicMock(side_effect=fake_get)

    with (
        patch("app.workers.notification_tasks.create_engine"),
        patch("app.workers.notification_tasks.Session") as mock_session_cls,
        patch("app.workers.notification_tasks.smtp_send") as mock_smtp,
    ):
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        send_notification_impl(str(notif.id))

    assert notif.status == NotifStatus.SENT
    assert notif.sent_at is not None
    mock_smtp.assert_called_once()


# T3/T4 — SMTP failure increments retry; permanent failure after max
def test_send_notification_failure_marks_failed_after_max_retries():
    notif = _make_notification(retry_count=4)
    user = MagicMock()
    user.email = "applicant@test.com"

    mock_session = MagicMock()

    def fake_get(model, obj_id):
        from app.domain.notification import Notification as N
        from app.domain.user import User as U
        if model is N:
            return notif
        if model is U:
            return user
        return None

    mock_session.get = MagicMock(side_effect=fake_get)

    with (
        patch("app.workers.notification_tasks.create_engine"),
        patch("app.workers.notification_tasks.Session") as mock_session_cls,
        patch("app.workers.notification_tasks.smtp_send", side_effect=RuntimeError("SMTP down")),
        pytest.raises(RuntimeError),
    ):
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        send_notification_impl(str(notif.id))

    assert notif.status == NotifStatus.FAILED
    assert notif.retry_count == 5
    assert "SMTP down" in (notif.error_message or "")


def test_exponential_backoff_delays():
    assert _retry_delay(0) == 60
    assert _retry_delay(1) == 120
    assert _retry_delay(2) == 240
    assert _retry_delay(3) == 480
    assert _retry_delay(4) == 960


def test_celery_config_task_acks_late_and_prefetch():
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.worker_prefetch_multiplier == 1


# T7 — 1000 notifications dispatched quickly (mocked)
async def test_enqueue_bulk_dispatches_1000_within_five_minutes(db):
    service = NotificationService(db)
    items = [
        {
            "user_id": uuid.uuid4(),
            "subject": f"Result {i}",
            "body": "Your result is ready",
            "template_name": "results_announced.html",
            "template_context": {"result": "Accepted"},
        }
        for i in range(1000)
    ]

    with patch.object(service, "_dispatch") as mock_dispatch:
        start = time.perf_counter()
        count = await service.enqueue_bulk(items)
        elapsed = time.perf_counter() - start

    assert count == 1000
    assert mock_dispatch.call_count == 1000
    assert elapsed < 300  # well under 5 minutes with mocks
