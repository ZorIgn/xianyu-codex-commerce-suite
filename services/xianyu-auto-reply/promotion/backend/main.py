"""推广返佣系统 - 后端服务启动入口（最小桩，业务逻辑见 _bootstrap.py）"""
from __future__ import annotations

import sys
from pathlib import Path

# 添加项目根目录到sys.path（兼容common模块导入，必须先于业务导入）
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from _bootstrap import app  # noqa: E402

if __name__ == "__main__":
    from _bootstrap import run_server
    run_server()
