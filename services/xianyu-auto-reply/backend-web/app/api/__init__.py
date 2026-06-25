"""
Backend-Web API模块

提供所有前端API接口
"""
from __future__ import annotations

# 先导入 deps，避免循环导入
from . import deps  # noqa: F401
from .routes import api_router

__all__ = ["api_router", "deps"]
