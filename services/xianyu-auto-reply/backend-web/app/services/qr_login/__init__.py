"""
二维码登录服务模块

提供闲鱼二维码扫码登录功能
"""
from __future__ import annotations

from .manager import QRLoginManager, qr_login_manager

__all__ = ["QRLoginManager", "qr_login_manager"]
