"""Local administrator password setup and recovery command.

This command is intentionally interactive so the new password is never placed
in shell history, source code, process arguments, or application logs.
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from app.services.auth import AuthService, MIN_PASSWORD_LENGTH
from common.db.session import async_session_maker
from common.models.user import UserRole


async def _change_password(action: str, username: str, password: str) -> None:
    async with async_session_maker() as session:
        auth_service = AuthService(session)
        user = await auth_service.get_by_username(username)
        if not user or user.role != UserRole.ADMIN:
            raise RuntimeError("未找到管理员账号")
        await auth_service.set_password(user, password, initial_only=action == "setup")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="在本机设置或重置闲鱼管理后台管理员密码")
    parser.add_argument(
        "action",
        choices=("setup", "reset"),
        help="setup 只允许首次设置；reset 显式重置密码并解除登录锁定",
    )
    parser.add_argument("--username", default="admin", help="管理员用户名，默认使用 admin")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    password = getpass.getpass("请输入新管理员密码: ")
    confirmation = getpass.getpass("请再次输入新管理员密码: ")
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"密码长度不能少于{MIN_PASSWORD_LENGTH}位", file=sys.stderr)
        return 2
    if password != confirmation:
        print("两次输入的密码不一致", file=sys.stderr)
        return 2

    try:
        asyncio.run(_change_password(args.action, args.username, password))
    except (RuntimeError, ValueError) as exc:
        print(f"操作失败: {exc}", file=sys.stderr)
        return 1

    if args.action == "setup":
        print("管理员密码已设置，请使用新密码登录")
    else:
        print("管理员密码已重置，登录锁定已解除，请使用新密码登录")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
