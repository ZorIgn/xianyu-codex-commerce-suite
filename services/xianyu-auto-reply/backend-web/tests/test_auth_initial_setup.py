from __future__ import annotations

import asyncio
import sys
import unittest
from datetime import timedelta
from pathlib import Path

from starlette.requests import Request

SERVICE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SERVICE_ROOT / "backend-web"))
sys.path.insert(0, str(SERVICE_ROOT))

from app.admin_password import _build_parser  # noqa: E402
from app.api.routes.auth import _is_loopback_request, router as auth_router  # noqa: E402
from app.core.security import verify_password  # noqa: E402
from app.services.auth import AuthService  # noqa: E402
from common.models.user import User, UserRole, UserStatus  # noqa: E402
from common.utils.time_utils import get_beijing_now  # noqa: E402


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _Session:
    def __init__(self, user: User):
        self.user = user
        self.commit_count = 0

    async def execute(self, _statement):
        return _ScalarResult(self.user)

    async def flush(self):
        return None

    async def commit(self):
        self.commit_count += 1


def _admin(password_hash: str = "") -> User:
    return User(
        id=1,
        username="admin",
        email="admin@example.com",
        password_hash=password_hash,
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
        login_fail_count=0,
    )


def _request(host: str, headers: dict[str, str] | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/local-setup-password",
        "headers": [
            (key.lower().encode("ascii"), value.encode("ascii"))
            for key, value in (headers or {}).items()
        ],
        "client": (host, 12345),
        "server": ("127.0.0.1", 8089),
        "scheme": "http",
        "query_string": b"",
    }
    return Request(scope)


class AuthInitialSetupTests(unittest.TestCase):
    def test_fresh_admin_is_explicitly_in_first_setup_state(self):
        service = AuthService(_Session(_admin()))
        self.assertTrue(service.is_password_setup_required(_admin()))

    def test_existing_admin_password_is_not_treated_as_first_setup(self):
        service = AuthService(_Session(_admin("stored-hash")))
        self.assertFalse(service.is_password_setup_required(_admin("stored-hash")))

    def test_first_setup_does_not_consume_login_failure_attempts(self):
        user = _admin()
        session = _Session(user)
        service = AuthService(session)

        authenticated, message = asyncio.run(service.authenticate_by_username("admin", "ignored"))

        self.assertIsNone(authenticated)
        self.assertIn("首次使用", message)
        self.assertEqual(user.login_fail_count, 0)
        self.assertEqual(session.commit_count, 0)

    def test_setting_password_clears_an_existing_lock(self):
        user = _admin("old-hash")
        user.login_fail_count = 3
        user.login_locked_until = get_beijing_now() + timedelta(minutes=5)
        session = _Session(user)
        service = AuthService(session)
        new_password = "test-only-password"

        asyncio.run(service.set_password(user, new_password))

        self.assertEqual(user.login_fail_count, 0)
        self.assertIsNone(user.login_locked_until)
        self.assertTrue(user.password_hash)
        self.assertTrue(verify_password(new_password, user.password_hash))
        self.assertEqual(session.commit_count, 1)

    def test_initial_setup_cannot_overwrite_an_existing_password(self):
        user = _admin("already-configured")
        session = _Session(user)
        service = AuthService(session)

        with self.assertRaises(ValueError):
            asyncio.run(
                service.set_password(
                    user,
                    "test-only-password",
                    initial_only=True,
                )
            )

        self.assertEqual(user.password_hash, "already-configured")
        self.assertEqual(session.commit_count, 0)

    def test_local_password_endpoints_reject_non_loopback_peers(self):
        self.assertTrue(_is_loopback_request(_request("127.0.0.1")))
        self.assertTrue(_is_loopback_request(_request("::1")))
        self.assertFalse(_is_loopback_request(_request("192.0.2.10")))
        self.assertFalse(
            _is_loopback_request(_request("127.0.0.1", {"X-Forwarded-For": "192.0.2.10"}))
        )
        self.assertTrue(
            _is_loopback_request(_request("127.0.0.1", {"X-Forwarded-For": "127.0.0.1"}))
        )

    def test_cli_exposes_explicit_setup_and_reset_actions(self):
        parser = _build_parser()
        self.assertEqual(parser.parse_args(["setup"]).action, "setup")
        self.assertEqual(parser.parse_args(["reset", "--username", "admin"]).action, "reset")
        option_strings = {
            option
            for action in parser._actions
            for option in action.option_strings
        }
        self.assertNotIn("--password", option_strings)
        self.assertNotIn("--new-password", option_strings)

    def test_http_surface_has_only_one_time_local_setup(self):
        paths = {route.path for route in auth_router.routes}
        self.assertIn("/setup-status", paths)
        self.assertIn("/local-setup-password", paths)
        self.assertNotIn("/local-reset-password", paths)

    def test_database_seed_uses_empty_hash_without_overwriting_existing_admin(self):
        source = (SERVICE_ROOT / "common" / "db" / "init_database.py").read_text(encoding="utf-8")
        seed = source[source.index("async def create_default_admin"):source.index("async def init_system_settings")]
        self.assertNotIn("get_password_hash", seed)
        self.assertIn("VALUES ('admin', 'admin@example.com', '', 'ACTIVE', 'ADMIN'", seed)
        self.assertIn("管理员用户已存在，跳过创建", seed)

    def test_reset_wrapper_uses_repository_venv_and_no_password_argument(self):
        wrapper = (SERVICE_ROOT.parent.parent / "reset-admin-password.bat").read_text(encoding="utf-8")
        self.assertIn(".venv-xianyu\\Scripts\\python.exe", wrapper)
        self.assertIn("pushd \"%SERVICE_ROOT%\\backend-web\"", wrapper)
        self.assertIn("-m app.admin_password reset --username admin", wrapper)
        self.assertNotIn("new_password", wrapper)


if __name__ == "__main__":
    unittest.main()
