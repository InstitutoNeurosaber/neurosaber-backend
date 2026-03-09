import pytest

from app.core.auth import verify_admin_api_key
from app.exceptions import UnauthorizedError


class TestVerifyAdminApiKey:
    def test_valid_key(self, monkeypatch):
        monkeypatch.setattr(
            "app.core.config.settings.ADMIN_API_KEY", "my-secret-key"
        )
        assert verify_admin_api_key(api_key="my-secret-key") is True

    def test_invalid_key(self, monkeypatch):
        monkeypatch.setattr(
            "app.core.config.settings.ADMIN_API_KEY", "my-secret-key"
        )
        with pytest.raises(UnauthorizedError):
            verify_admin_api_key(api_key="wrong-key")

    def test_missing_key(self, monkeypatch):
        monkeypatch.setattr(
            "app.core.config.settings.ADMIN_API_KEY", "my-secret-key"
        )
        with pytest.raises(UnauthorizedError):
            verify_admin_api_key(api_key=None)

    def test_server_key_not_configured(self, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.ADMIN_API_KEY", "")
        with pytest.raises(UnauthorizedError):
            verify_admin_api_key(api_key="any-key")
