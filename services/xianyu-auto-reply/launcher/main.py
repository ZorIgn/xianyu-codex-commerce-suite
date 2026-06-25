"""启动器主入口（最小桩，业务逻辑见 _bootstrap.py）"""
import datetime
import sys
import traceback
from pathlib import Path


def _is_frozen_early() -> bool:
    """早期编译模式检测（在 sys.path 设置前使用）"""
    if getattr(sys, "frozen", False):
        return True
    if sys.platform == "win32":
        exe_name = Path(sys.executable).name.lower()
        if exe_name not in ("python.exe", "pythonw.exe", "python3.exe", "python"):
            if not exe_name.startswith("python"):
                return True
    return False


def _resolve_project_root() -> Path:
    """获取项目根目录"""
    if _is_frozen_early():
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


def _write_fatal_log(stage: str) -> None:
    """记录启动期未捕获异常"""
    try:
        log_dir = _resolve_project_root() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / "launcher_error.log").open("a", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write(
                f"[{datetime.datetime.now().isoformat(timespec='seconds')}] "
                f"启动失败 stage={stage}\n"
            )
            f.write(f"sys.argv={sys.argv}\n")
            f.write(f"sys.executable={sys.executable}\n")
            f.write(f"project_root={_resolve_project_root()}\n")
            f.write(f"sys.path={sys.path}\n")
            f.write(traceback.format_exc())
            f.write("\n")
    except Exception:
        pass


project_root = _resolve_project_root()
sys.path.insert(0, str(project_root))


def _run_main() -> None:
    """运行启动器主逻辑"""
    try:
        from _bootstrap import main as bootstrap_main  # type: ignore  # noqa: E402
    except Exception:
        from launcher._bootstrap import main as bootstrap_main  # type: ignore  # noqa: E402
    bootstrap_main()


if __name__ == "__main__":
    try:
        _run_main()
    except SystemExit:
        raise
    except BaseException:
        _write_fatal_log("main")
        sys.exit(1)
