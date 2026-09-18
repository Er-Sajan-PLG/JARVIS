"""Unit tests for push notification service."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.push import PushMessage, PushService, PushSubscription


@pytest.fixture
def push_service(tmp_path):
    # Isolated storage: the service persists to data/ by default, which would
    # leak test subscriptions into the real server state.
    return PushService(
        vapid_private_key="test_vapid_key",
        storage_path=tmp_path / "subs.json",
    )


@pytest.fixture
def subscription():
    return PushSubscription(
        endpoint="https://fcm.googleapis.com/fcm/send/test123",
        keys={
            "p256dh": "test_p256dh_key",
            "auth": "test_auth_key",
        },
        user_agent="Mozilla/5.0",
    )


class TestPushSubscription:
    def test_create_subscription(self):
        sub = PushSubscription(
            endpoint="https://example.com/push",
            keys={"p256dh": "key1", "auth": "key2"},
        )
        assert sub.endpoint == "https://example.com/push"
        assert sub.keys["p256dh"] == "key1"


class TestPushMessage:
    def test_create_message(self):
        msg = PushMessage(title="Test", body="Hello")
        assert msg.title == "Test"
        assert msg.body == "Hello"
        assert msg.icon == "/icon-192.png"

    def test_message_with_data(self):
        msg = PushMessage(title="Test", body="Hello", data={"key": "value"})
        assert msg.data["key"] == "value"


class TestPushService:
    def test_add_subscription(self, push_service, subscription):
        push_service.add_subscription(subscription)
        assert push_service.get_subscription_count() == 1

    def test_add_duplicate_subscription(self, push_service, subscription):
        push_service.add_subscription(subscription)
        push_service.add_subscription(subscription)
        assert push_service.get_subscription_count() == 1

    def test_remove_subscription(self, push_service, subscription):
        push_service.add_subscription(subscription)
        push_service.remove_subscription(subscription.endpoint)
        assert push_service.get_subscription_count() == 0

    @pytest.mark.asyncio
    async def test_send_without_vapid_key(self, tmp_path, monkeypatch):
        # The service falls back to VAPID_PRIVATE_KEY from the environment,
        # which the suite's conftest may populate via the repo .env.
        monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
        service = PushService(storage_path=tmp_path / "subs.json")
        result = await service.send(PushMessage(title="Test", body="Hello"))
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_send_success(self, push_service, subscription):
        push_service.add_subscription(subscription)
        
        mock_webpush = MagicMock()
        with patch.dict("sys.modules", {"pywebpush": MagicMock(webpush=mock_webpush)}):
            result = await push_service.send(PushMessage(title="Test", body="Hello"))
        
        # Should attempt to send
        assert result["total"] == 1

    def test_get_subscription_count(self, push_service):
        assert push_service.get_subscription_count() == 0
