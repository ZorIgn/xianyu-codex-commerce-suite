"""
认证服务

功能：
1. 用户名/邮箱密码认证
2. 密码验证（支持SHA256和passlib格式）
3. 登录时间记录
4. 访问令牌生成
5. 登录失败次数限制（最大3次，锁定2小时）
"""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from typing import Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import get_settings
from common.models.user import User
from common.utils.time_utils import BEIJING_TZ, get_beijing_now

# 登录失败限制配置
MAX_LOGIN_FAIL_COUNT = 3  # 最大失败次数
LOGIN_LOCK_HOURS = 2  # 锁定时长（小时）
MIN_PASSWORD_LENGTH = 6
PASSWORD_SETUP_REQUIRED_MESSAGE = "首次使用，请在部署机器本机设置管理员密码"

class AuthService:
    """Encapsulates authentication related domain logic."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    @staticmethod
    def is_password_setup_required(user: User) -> bool:
        """Return whether the account still has no configured password.

        The initial administrator is represented by an empty password hash so
        this remains compatible with the existing NOT NULL database column.
        """
        return not bool((user.password_hash or "").strip())

    async def get_by_username(self, username: str) -> User | None:
        if not username:
            return None
        stmt = select(User).where(func.lower(User.username) == username.lower())
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        if not email:
            return None
        stmt = select(User).where(func.lower(User.email) == email.lower())
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def is_login_locked(self, user: User) -> bool:
        return self._check_login_locked(user)[0]

    def _check_login_locked(self, user: User) -> Tuple[bool, Optional[str]]:
        """
        检查用户是否被锁定
        返回: (是否锁定, 锁定提示信息)
        """
        if user.login_locked_until:
            now = get_beijing_now()
            # 处理时区问题：如果数据库时间没有时区信息，视为北京时间
            locked_until = user.login_locked_until
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=BEIJING_TZ)
            
            if locked_until > now:
                # 计算剩余锁定时间
                remaining = locked_until - now
                remaining_minutes = int(remaining.total_seconds() / 60)
                if remaining_minutes > 60:
                    remaining_str = f"{remaining_minutes // 60}小时{remaining_minutes % 60}分钟"
                else:
                    remaining_str = f"{remaining_minutes}分钟"
                return True, f"账号已被锁定，请{remaining_str}后再试"
        return False, None

    async def _handle_login_fail(self, user: User) -> str:
        """
        处理登录失败，增加失败次数
        返回: 错误提示信息
        """
        user.login_fail_count = (user.login_fail_count or 0) + 1
        remaining_attempts = MAX_LOGIN_FAIL_COUNT - user.login_fail_count
        
        if user.login_fail_count >= MAX_LOGIN_FAIL_COUNT:
            # 达到最大失败次数，锁定账号（使用北京时间）
            user.login_locked_until = get_beijing_now() + timedelta(hours=LOGIN_LOCK_HOURS)
            await self.session.flush()
            await self.session.commit()
            return f"密码错误次数过多，账号已被锁定{LOGIN_LOCK_HOURS}小时"
        
        await self.session.flush()
        await self.session.commit()
        return f"用户名或密码错误，还剩{remaining_attempts}次尝试机会"

    async def _reset_login_fail(self, user: User) -> None:
        """登录成功后重置失败次数"""
        if user.login_fail_count > 0 or user.login_locked_until:
            user.login_fail_count = 0
            user.login_locked_until = None
            await self.session.flush()

    async def authenticate_by_username(self, username: str, password: str) -> Tuple[Optional[User], Optional[str]]:
        """
        通过用户名认证
        返回: (用户对象, 错误信息)
        """
        if not username:
            return None, "请输入用户名"
        user = await self.get_by_username(username)
        
        if not user:
            return None, "用户名或密码错误"

        if self.is_password_setup_required(user):
            return None, PASSWORD_SETUP_REQUIRED_MESSAGE
        
        # 检查是否被锁定
        is_locked, lock_msg = self._check_login_locked(user)
        if is_locked:
            return None, lock_msg
        
        # 验证密码
        if not self._verify_user_password(user, password):
            error_msg = await self._handle_login_fail(user)
            return None, error_msg
        
        # 登录成功，重置失败次数
        await self._reset_login_fail(user)
        return user, None

    async def authenticate_by_email(self, email: str, password: str) -> Tuple[Optional[User], Optional[str]]:
        """
        通过邮箱认证
        返回: (用户对象, 错误信息)
        """
        if not email:
            return None, "请输入邮箱"
        user = await self.get_by_email(email)
        
        if not user:
            return None, "邮箱或密码错误"

        if self.is_password_setup_required(user):
            return None, PASSWORD_SETUP_REQUIRED_MESSAGE
        
        # 检查是否被锁定
        is_locked, lock_msg = self._check_login_locked(user)
        if is_locked:
            return None, lock_msg
        
        # 验证密码
        if not self._verify_user_password(user, password):
            error_msg = await self._handle_login_fail(user)
            return None, error_msg
        
        # 登录成功，重置失败次数
        await self._reset_login_fail(user)
        return user, None

    def _verify_user_password(self, user: User, password: Optional[str]) -> bool:
        if not password:
            return False
        stored_hash = (user.password_hash or "").strip()
        if not stored_hash:
            return False
        if len(stored_hash) == 64 and all(c in "0123456789abcdefABCDEF" for c in stored_hash):
            return sha256(password.encode("utf-8")).hexdigest() == stored_hash.lower()
        try:
            return security.verify_password(password, stored_hash)
        except Exception:
            return False

    async def set_password(
        self,
        user: User,
        password: str,
        *,
        initial_only: bool = False,
    ) -> None:
        """Set an administrator password and clear authentication lock state."""
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"密码长度不能少于{MIN_PASSWORD_LENGTH}位")
        if initial_only and not self.is_password_setup_required(user):
            raise ValueError("管理员密码已经设置，请使用本机重置命令")

        user.password_hash = security.get_password_hash(password)
        user.login_fail_count = 0
        user.login_locked_until = None
        await self.session.flush()
        await self.session.commit()

    async def mark_login(self, user: User) -> None:
        user.last_login_at = get_beijing_now()
        await self.session.flush()
        await self.session.commit()

    def create_access_token(self, user: User) -> str:
        payload = {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role.value,
        }
        return security.create_access_token(
            payload,
            expires_delta=timedelta(minutes=self.settings.access_token_expire_minutes),
        )

    def create_refresh_token(self, user: User) -> str:
        """创建刷新令牌"""
        payload = {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role.value,
        }
        return security.create_refresh_token(
            payload,
            expires_delta=timedelta(minutes=self.settings.refresh_token_expire_minutes),
        )
