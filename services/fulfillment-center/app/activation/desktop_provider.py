from __future__ import annotations

import asyncio
import ctypes
import json
import os
import re
import shlex
import subprocess
import time
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import psutil

from ..config import get_settings
from ..inventory import activation_eligibility, extract_oauth_fields
from ..settings_store import get_setting, update_settings


@dataclass(frozen=True)
class DesktopInstance:
    instance_id: str
    name: str
    codex_home: Path
    app_user_data_dir: Path
    last_pid: int | None = None
    launch_mode: str = "app"
    extra_args: str = ""


@dataclass(frozen=True)
class OAuthTokens:
    access_token: str
    refresh_token: str
    id_token: str
    account_id: str


def _credentials_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        result: dict[str, Any] = {}
        for entry in value:
            if not isinstance(entry, dict):
                continue
            key = entry.get("key") or entry.get("name")
            if key and entry.get("value") not in (None, ""):
                result[str(key)] = entry.get("value")
        return result
    return {}


def _extract_oauth_tokens(item: dict[str, Any]) -> OAuthTokens:
    oauth = extract_oauth_fields(item)
    return OAuthTokens(
        access_token=oauth["access_token"],
        refresh_token=oauth["refresh_token"],
        id_token=oauth["id_token"],
        account_id=oauth["account_id"],
    )


class DesktopProvider:
    """Switches OAuth in one fixed Cockpit CODEX_HOME and controls only its window."""

    _DESKTOP_NAMES = {"chatgpt.exe", "codex.exe"}
    _USER_DATA_RE = re.compile(
        r'--user-data-dir(?:=|\s+)(?:"([^"]+)"|(\S+))',
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        self.settings = get_settings()
        self.state_dir = self.settings.cockpit_state_dir
        self.last_pid: int | None = None

    def _cockpit_instances(self) -> list[dict[str, Any]]:
        path = self.state_dir / "codex_instances.json"
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return [
                entry for entry in data.get("instances", [])
                if isinstance(entry, dict)
            ]
        except Exception:
            return []

    def _resolve_configured_instance(
        self,
        *,
        configured_id: str = "",
        configured_name: str = "",
        configured_home: str = "",
        configured_app_data: str = "",
        instances: list[dict[str, Any]] | None = None,
    ) -> DesktopInstance:
        settings = get_settings()
        instances = instances if instances is not None else self._cockpit_instances()
        match: dict[str, Any] | None = None
        if configured_id:
            match = next(
                (entry for entry in instances if str(entry.get("id")) == configured_id),
                None,
            )
        if match is None and configured_name:
            match = next(
                (entry for entry in instances if str(entry.get("name")) == configured_name),
                None,
            )
        if match is None and configured_home:
            normalized = os.path.normcase(os.path.normpath(configured_home))
            match = next(
                (
                    entry for entry in instances
                    if os.path.normcase(os.path.normpath(str(entry.get("userDataDir") or "")))
                    == normalized
                ),
                None,
            )

        home_value = str(
            configured_home
            or str((match or {}).get("userDataDir") or "")
        ).strip()
        if not home_value:
            raise RuntimeError(
                f"Cockpit 实例未找到: {configured_name or configured_id or '未配置路径'}"
            )
        codex_home = Path(home_value)
        if not codex_home.is_dir():
            raise RuntimeError("固定 Cockpit 实例目录不存在: " + str(codex_home))

        app_value = str(
            configured_app_data
            or str(
                (match or {}).get("appUserDataDir")
                or (match or {}).get("app_user_data_dir")
                or ""
            )
        ).strip()
        if not app_value:
            raise RuntimeError(
                "实例缺少已初始化的桌面数据目录；请在实例池中同时配置 "
                "app_user_data_dir（通常位于 .antigravity_cockpit\\instances\\codex-app-data）"
            )
        app_user_data_dir = Path(app_value)
        if not app_user_data_dir.is_dir():
            raise RuntimeError("固定实例桌面数据目录不存在: " + str(app_user_data_dir))
        return DesktopInstance(
            instance_id=str((match or {}).get("id") or configured_id or codex_home.name),
            name=str((match or {}).get("name") or configured_name or codex_home.name),
            codex_home=codex_home,
            app_user_data_dir=app_user_data_dir,
            last_pid=int((match or {}).get("lastPid") or 0) or None,
            launch_mode=str((match or {}).get("launchMode") or "app"),
            extra_args=str((match or {}).get("extraArgs") or ""),
        )

    def resolve_instance(self) -> DesktopInstance:
        settings = get_settings()
        return self._resolve_configured_instance(
            configured_id=get_setting("desktop_instance_id", settings.desktop_instance_id),
            configured_name=get_setting("desktop_instance_name", settings.desktop_instance_name),
            configured_home=get_setting("desktop_profile_dir", str(settings.desktop_profile_dir or "")),
            configured_app_data=get_setting(
                "desktop_app_user_data_dir",
                str(getattr(settings, "desktop_app_user_data_dir", "") or ""),
            ),
        )

    def resolve_instances(self) -> list[DesktopInstance]:
        """Resolve the configured instance pool; empty pool means the legacy single instance."""
        settings = get_settings()
        raw = get_setting("desktop_instance_pool", settings.desktop_instance_pool).strip()
        if not raw:
            return [self.resolve_instance()]
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"桌面实例池 JSON 无效: {exc}") from exc
        entries = parsed.get("instances") if isinstance(parsed, dict) else parsed
        if not isinstance(entries, list) or not entries:
            raise RuntimeError("桌面实例池必须是非空 JSON 数组")
        cockpit_instances = self._cockpit_instances()
        resolved: list[DesktopInstance] = []
        seen: set[str] = set()
        for index, entry in enumerate(entries, start=1):
            if isinstance(entry, str):
                entry = {"profile_dir": entry}
            if not isinstance(entry, dict):
                raise RuntimeError(f"桌面实例池第 {index} 项必须是对象或路径字符串")
            instance = self._resolve_configured_instance(
                configured_id=str(entry.get("instance_id") or entry.get("id") or "").strip(),
                configured_name=str(entry.get("name") or "").strip(),
                configured_home=str(
                    entry.get("codex_home")
                    or entry.get("profile_dir")
                    or entry.get("userDataDir")
                    or ""
                ).strip(),
                configured_app_data=str(
                    entry.get("app_user_data_dir")
                    or entry.get("app_data_dir")
                    or entry.get("appUserDataDir")
                    or ""
                ).strip(),
                instances=cockpit_instances,
            )
            key = os.path.normcase(os.path.normpath(str(instance.codex_home)))
            if key in seen:
                raise RuntimeError(f"桌面实例池包含重复目录: {instance.codex_home}")
            seen.add(key)
            resolved.append(instance)
        return resolved
    @classmethod
    def _desktop_process(cls, process: psutil.Process) -> bool:
        try:
            return process.name().lower() in cls._DESKTOP_NAMES
        except (psutil.Error, OSError):
            return False

    @classmethod
    def _root_process(cls, process: psutil.Process) -> psutil.Process:
        current = process
        while True:
            try:
                parent = current.parent()
            except (psutil.Error, OSError):
                break
            if not parent or not cls._desktop_process(parent):
                break
            current = parent
        return current

    @staticmethod
    def _window_pids() -> set[int]:
        if os.name != "nt":
            return set()
        pids: set[int] = set()
        user32 = ctypes.windll.user32
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        @callback_type
        def callback(hwnd: int, _: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value:
                pids.add(int(pid.value))
            return True

        user32.EnumWindows(callback, 0)
        return pids

    @staticmethod
    def _command_line(process: psutil.Process) -> str:
        try:
            return " ".join(process.cmdline())
        except (psutil.Error, OSError):
            return ""

    @classmethod
    def _process_tree(cls, root_pid: int) -> list[psutil.Process]:
        try:
            root = psutil.Process(root_pid)
            return [root, *root.children(recursive=True)]
        except (psutil.Error, OSError):
            return []

    @classmethod
    def _discover_app_user_data_dir(cls, root_pid: int) -> Path | None:
        for process in cls._process_tree(root_pid):
            match = cls._USER_DATA_RE.search(cls._command_line(process))
            if not match:
                continue
            value = match.group(1) or match.group(2) or ""
            if value:
                return Path(value)
        return None

    @staticmethod
    def _same_path(left: Path | str, right: Path | str) -> bool:
        return os.path.normcase(os.path.normpath(str(left))) == os.path.normcase(
            os.path.normpath(str(right))
        )

    def _find_root_pid(
        self,
        instance: DesktopInstance,
        *,
        require_window: bool = True,
    ) -> int | None:
        window_pids = self._window_pids() if require_window else set()
        marker = str(instance.app_user_data_dir).lower().replace("/", "\\")
        roots: list[int] = []
        for process in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if not self._desktop_process(process):
                    continue
                command = " ".join(process.info.get("cmdline") or [])
                normalized = command.lower().replace("/", "\\")
                if marker and marker in normalized:
                    roots.append(int(self._root_process(process).pid))
            except (psutil.Error, OSError):
                continue

        for pid in dict.fromkeys(roots):
            if not require_window or pid in window_pids:
                return pid
        return None

    def _find_window_pid(self, instance: DesktopInstance) -> int | None:
        root_pid = self._find_root_pid(instance, require_window=False)
        if not root_pid:
            return None
        try:
            root = psutil.Process(root_pid)
            tree_pids = {
                root.pid,
                *(child.pid for child in root.children(recursive=True)),
            }
        except (psutil.Error, OSError):
            tree_pids = {root_pid}
        for window_pid in self._window_pids():
            if window_pid in tree_pids:
                return int(window_pid)
        return None

    def _remember_app_user_data_dir(self, path: Path) -> None:
        current = get_setting("desktop_app_user_data_dir", "")
        if current and self._same_path(current, path):
            return
        update_settings({"desktop_app_user_data_dir": str(path)})

    def _resolved_runtime(
        self,
        instance: DesktopInstance,
    ) -> tuple[DesktopInstance, int | None]:
        pid = self._find_root_pid(instance, require_window=False)
        if pid:
            discovered = self._discover_app_user_data_dir(pid)
            if discovered:
                instance = replace(instance, app_user_data_dir=discovered)
                self._remember_app_user_data_dir(discovered)
        return instance, pid

    def status(self) -> dict[str, Any]:
        try:
            instances = self.resolve_instances()
        except Exception as exc:
            return {"bound": False, "online": False, "error": str(exc), "pool_size": 0, "pool": []}

        pool: list[dict[str, Any]] = []
        for instance in instances:
            try:
                runtime, pid = self._resolved_runtime(instance)
                pool.append({
                    "bound": True,
                    "online": bool(pid),
                    "instance_id": runtime.instance_id,
                    "instance_name": runtime.name,
                    "profile_dir": str(runtime.codex_home),
                    "codex_home": str(runtime.codex_home),
                    "app_user_data_dir": str(runtime.app_user_data_dir),
                    "pid": pid,
                    "launch_mode": runtime.launch_mode,
                    "auth_ready": (runtime.codex_home / "auth.json").exists(),
                    "bridge": self.bridge_status(runtime),
                })
            except Exception as exc:
                pool.append({
                    "bound": False,
                    "online": False,
                    "instance_id": instance.instance_id,
                    "instance_name": instance.name,
                    "profile_dir": str(instance.codex_home),
                    "codex_home": str(instance.codex_home),
                    "app_user_data_dir": str(instance.app_user_data_dir),
                    "pid": None,
                    "error": str(exc),
                })
        primary = dict(pool[0]) if pool else {"bound": False, "online": False}
        self.last_pid = int(primary.get("pid") or 0) or None
        primary["pool_size"] = len(pool)
        primary["pool"] = pool
        primary["bridge"] = primary.get("bridge") or self.bridge_status()
        try:
            worker_count = max(1, int(float(get_setting("activation_worker_count", str(get_settings().activation_worker_count)))))
        except (TypeError, ValueError):
            worker_count = max(1, int(get_settings().activation_worker_count))
        primary["worker_capacity"] = min(len(pool), worker_count) if pool else 0
        return primary
    def _app_path(self) -> str:
        path = self.state_dir / "config.json"
        if not path.exists():
            return ""
        try:
            return str(
                json.loads(path.read_text(encoding="utf-8")).get("codex_app_path")
                or ""
            )
        except Exception:
            return ""

    @staticmethod
    def _with_user_data_arg(args: list[str], app_user_data_dir: Path) -> list[str]:
        result: list[str] = []
        skip_next = False
        for arg in args:
            if skip_next:
                skip_next = False
                continue
            lowered = arg.lower()
            if lowered == "--user-data-dir":
                skip_next = True
                continue
            if lowered.startswith("--user-data-dir="):
                continue
            result.append(arg)
        result.append(f"--user-data-dir={app_user_data_dir}")
        return result

    @staticmethod
    def _ps_quote(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    def _spawn_with_powershell(
        self,
        args: list[str],
        instance: DesktopInstance,
        env: dict[str, str],
    ) -> int | None:
        executable = args[0]
        argument_list = ", ".join(self._ps_quote(value) for value in args[1:])
        window_style = ""
        if get_setting("desktop_background_mode", "false").strip().lower() in {"1", "true", "yes", "on"}:
            window_style = " -WindowStyle Minimized"
        command = (
            "$arguments=@(" + argument_list + "); "
            "$process=Start-Process -FilePath "
            + self._ps_quote(executable)
            + " -ArgumentList $arguments -WorkingDirectory "
            + self._ps_quote(str(instance.codex_home))
            + window_style
            + " -PassThru; $process.Id"
        )
        result = subprocess.run(
            [
                r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            raise RuntimeError(
                result.stderr.strip() or "PowerShell 启动固定实例失败"
            )
        for line in reversed(result.stdout.splitlines()):
            if line.strip().isdigit():
                return int(line.strip())
        return None

    def _wait_for_root(
        self,
        instance: DesktopInstance,
        timeout_seconds: float,
    ) -> int | None:
        deadline = time.monotonic() + max(1.0, timeout_seconds)
        while time.monotonic() < deadline:
            pid = self._find_root_pid(instance, require_window=False)
            if pid:
                return pid
            time.sleep(0.5)
        return None

    def _launch(self, instance: DesktopInstance) -> int:
        instance, pid = self._resolved_runtime(instance)
        if pid:
            self.last_pid = pid
            return pid

        settings = get_settings()
        command = get_setting("desktop_launch_command", settings.desktop_launch_command)
        if command:
            args = shlex.split(command, posix=False)
        else:
            app_path = self._app_path()
            if not app_path:
                raise RuntimeError(
                    "未找到 ChatGPT/Codex 桌面程序路径，请在 Cockpit 设置中配置"
                )
            args = [app_path]
        if instance.extra_args:
            args.extend(shlex.split(instance.extra_args, posix=False))
        args = self._with_user_data_arg(args, instance.app_user_data_dir)

        if not instance.codex_home.is_dir():
            raise RuntimeError("固定 Cockpit 实例目录已不存在: " + str(instance.codex_home))
        if not instance.app_user_data_dir.is_dir():
            raise RuntimeError("固定桌面数据目录已不存在: " + str(instance.app_user_data_dir))

        env = os.environ.copy()
        env["CODEX_HOME"] = str(instance.codex_home)
        env["CODEX_ELECTRON_USER_DATA_PATH"] = str(instance.app_user_data_dir)

        direct_error = ""
        pid = None
        background = get_setting("desktop_background_mode", "false").strip().lower() in {"1", "true", "yes", "on"}
        if background:
            try:
                pid = self._spawn_with_powershell(args, instance, env)
            except Exception as exc:
                direct_error = str(exc)
        else:
            try:
                subprocess.Popen(
                    args,
                    cwd=str(instance.codex_home),
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                )
            except OSError as exc:
                direct_error = str(exc)

        if not pid:
            pid = self._wait_for_root(instance, min(15, settings.desktop_start_timeout_seconds))
        if not pid and not background:
            try:
                self._spawn_with_powershell(args, instance, env)
            except Exception as exc:
                message = str(exc)
                if direct_error:
                    message = f"{direct_error}; {message}"
                raise RuntimeError("启动固定桌面实例失败: " + message) from exc
            remaining = max(5, settings.desktop_start_timeout_seconds - 15)
            pid = self._wait_for_root(instance, remaining)
        if not pid:
            raise RuntimeError(
                f"固定桌面实例启动超时，未找到属于 {instance.name} 的窗口"
            )
        self.last_pid = pid
        return pid

    def _stop(self, instance: DesktopInstance) -> None:
        instance, visible_pid = self._resolved_runtime(instance)
        pid = visible_pid or self._find_root_pid(instance, require_window=False)
        if not pid:
            return

        processes: list[psutil.Process] = []
        try:
            root = psutil.Process(pid)
            processes = [root, *root.children(recursive=True)]
            for process in reversed(processes[1:]):
                try:
                    process.terminate()
                except (psutil.Error, OSError):
                    pass
            try:
                root.terminate()
            except (psutil.Error, OSError):
                pass

            try:
                _, alive = psutil.wait_procs(processes, timeout=8)
            except (psutil.Error, OSError):
                alive = [
                    process
                    for process in processes
                    if process.is_running()
                ]

            if alive and os.name == "nt":
                for process in reversed(alive):
                    try:
                        subprocess.run(
                            [
                                str(Path(os.environ.get("SystemRoot", r"C:\Windows"))
                                    / "System32"
                                    / "taskkill.exe"),
                                "/PID",
                                str(process.pid),
                                "/T",
                                "/F",
                            ],
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=10,
                            creationflags=getattr(
                                subprocess,
                                "CREATE_NO_WINDOW",
                                0,
                            ),
                        )
                    except (OSError, subprocess.SubprocessError):
                        pass
            else:
                for process in alive:
                    try:
                        process.kill()
                    except (psutil.Error, OSError):
                        pass

            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if not self._find_root_pid(instance, require_window=False):
                    break
                time.sleep(0.25)
            remaining = self._find_root_pid(instance, require_window=False)
            if remaining:
                raise RuntimeError(
                    f"固定桌面实例进程树未完全关闭，剩余 PID: {remaining}"
                )
        except psutil.NoSuchProcess:
            return
        except (psutil.Error, OSError) as exc:
            raise RuntimeError(f"关闭固定桌面实例失败: {exc}") from exc
        finally:
            self.last_pid = None
    @staticmethod
    def _auth_payload(tokens: OAuthTokens) -> dict[str, Any]:
        return {
            "OPENAI_API_KEY": None,
            "last_refresh": datetime.now(timezone.utc).isoformat().replace(
                "+00:00", "Z"
            ),
            "tokens": {
                "access_token": tokens.access_token,
                "account_id": tokens.account_id,
                "id_token": tokens.id_token,
                "refresh_token": tokens.refresh_token,
            },
        }

    @staticmethod
    def _missing_oauth_fields(tokens: OAuthTokens) -> list[str]:
        fields = {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "id_token": tokens.id_token,
            "account_id": tokens.account_id,
        }
        return [name for name, value in fields.items() if not value]

    def _write_auth(self, instance: DesktopInstance, tokens: OAuthTokens) -> Path:
        missing = self._missing_oauth_fields(tokens)
        if missing:
            raise RuntimeError(
                "库存缺少桌面 Codex OAuth 字段: " + ", ".join(missing)
            )
        if not instance.codex_home.is_dir():
            raise RuntimeError("固定 Cockpit 实例目录已不存在: " + str(instance.codex_home))
        auth_path = instance.codex_home / "auth.json"
        temp_path = instance.codex_home / f".auth.{os.getpid()}.{time.time_ns()}.tmp"
        temp_path.write_text(
            json.dumps(self._auth_payload(tokens), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temp_path, auth_path)
        return auth_path

    @staticmethod
    def _verify_auth(
        auth_path: Path,
        tokens: OAuthTokens,
        expected_email: str,
    ) -> bool:
        try:
            payload = json.loads(auth_path.read_text(encoding="utf-8"))
            saved = payload.get("tokens") if isinstance(payload, dict) else {}
            if not isinstance(saved, dict):
                return False
            if saved.get("access_token") != tokens.access_token:
                return False
            if (
                tokens.refresh_token
                and saved.get("refresh_token") != tokens.refresh_token
            ):
                return False
            if tokens.account_id and str(saved.get("account_id") or "") != tokens.account_id:
                return False

            expected = expected_email.strip().lower()
            if not expected:
                return True
            claimed_email = extract_oauth_fields(
                {
                    "primary_token": tokens.access_token,
                    "id_token": tokens.id_token,
                }
            )["email"]
            return not claimed_email or expected == claimed_email
        except Exception:
            return False

    def _bridge_root(self, instance: DesktopInstance | None = None) -> Path:
        root = Path(get_settings().database_path).resolve().parent / "desktop_bridge"
        if instance is not None:
            safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", instance.instance_id or instance.name).strip("_") or "default"
            root = root / safe_id[:96]
        return root

    def bridge_status(self, instance: DesktopInstance | None = None) -> dict[str, Any]:
        root = self._bridge_root(instance)
        heartbeat_path = root / "heartbeat.json"
        result: dict[str, Any] = {
            "online": False,
            "root": str(root),
            "pid": None,
            "age_seconds": None,
        }
        if not heartbeat_path.exists():
            return result
        try:
            heartbeat = json.loads(heartbeat_path.read_text(encoding="utf-8"))
            pid = int(heartbeat.get("pid") or 0)
            updated_at = str(heartbeat.get("updated_at") or "")
            updated = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            age = max(
                0.0,
                (datetime.now(timezone.utc) - updated.astimezone(timezone.utc)).total_seconds(),
            )
            process = psutil.Process(pid)
            is_powershell = process.name().lower().startswith("powershell")
            online = bool(
                heartbeat.get("ready")
                and process.is_running()
                and is_powershell
                and age < 10
            )
            result.update(
                {
                    "online": online,
                    "pid": pid,
                    "age_seconds": round(age, 3),
                }
            )
        except (ValueError, TypeError, OSError, psutil.Error, json.JSONDecodeError):
            pass
        return result

    def _ensure_bridge(self, instance: DesktopInstance | None = None) -> dict[str, Any]:
        bridge = self.bridge_status(instance)
        if bridge.get("online"):
            return bridge

        stale_pid = int(bridge.get("pid") or 0)
        if stale_pid:
            try:
                process = psutil.Process(stale_pid)
                command = " ".join(process.cmdline()).lower().replace("/", "\\")
                if (
                    process.name().lower().startswith("powershell")
                    and "desktop_bridge.ps1" in command
                ):
                    process.terminate()
                    process.wait(timeout=5)
            except (psutil.Error, OSError):
                pass

        project_root = Path(__file__).resolve().parents[2]
        script = project_root / "start-desktop-bridge.ps1"
        if not script.is_file():
            raise RuntimeError(f"桌面桥接启动脚本不存在: {script}")
        powershell = (
            Path(os.environ.get("SystemRoot", r"C:\Windows"))
            / "System32"
            / "WindowsPowerShell"
            / "v1.0"
            / "powershell.exe"
        )
        result = subprocess.run(
            [
                str(powershell),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                "-BridgeRoot",
                str(self._bridge_root(instance)),
            ],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=25,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            raise RuntimeError(
                result.stderr.strip()
                or result.stdout.strip()
                or "桌面激活桥接自动启动失败"
            )

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            bridge = self.bridge_status(instance)
            if bridge.get("online"):
                return bridge
            time.sleep(0.1)
        raise RuntimeError("桌面激活桥接启动后未产生有效心跳")

    @staticmethod
    def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
        temp.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(temp, path)

    def _ui(
        self,
        operation: str,
        pid: int,
        prompt: str = "",
        instance: DesktopInstance | None = None,
    ) -> dict[str, Any]:
        self._ensure_bridge(instance)

        root = self._bridge_root(instance)
        request_dir = root / "requests"
        response_dir = root / "responses"
        request_id = uuid.uuid4().hex
        request_path = request_dir / f"{request_id}.json"
        response_path = response_dir / f"{request_id}.json"
        timeout_seconds = (
            get_settings().desktop_response_timeout_seconds
            if operation == "send"
            else 30
        )
        payload = {
            "request_id": request_id,
            "operation": operation,
            "target_pid": int(pid),
            "prompt_b64": (
                base64.b64encode(prompt.encode("utf-8")).decode("ascii")
                if prompt
                else ""
            ),
            "timeout_seconds": int(timeout_seconds),
            "allow_foreground_fallback": get_setting("desktop_allow_foreground_fallback", "false").strip().lower() in {"1", "true", "yes", "on"},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._write_json_atomic(request_path, payload)

        deadline = time.monotonic() + timeout_seconds + 20
        while time.monotonic() < deadline:
            if response_path.exists():
                try:
                    wrapper = json.loads(response_path.read_text(encoding="utf-8"))
                finally:
                    try:
                        response_path.unlink()
                    except FileNotFoundError:
                        pass
                if not wrapper.get("ok"):
                    raise RuntimeError(
                        str(wrapper.get("error") or "桌面 UI Automation 执行失败")
                    )
                result = wrapper.get("result")
                if not isinstance(result, dict):
                    raise RuntimeError("桌面 UI Automation 返回格式错误")
                return result
            time.sleep(0.1)

        try:
            request_path.unlink()
        except FileNotFoundError:
            pass
        if operation == "send":
            raise RuntimeError(
                "桌面消息请求等待超时，发送结果未知，系统不会自动重发"
            )
        raise RuntimeError("桌面 UI 快照请求等待超时")

    def _wait_for_ui_ready(
        self,
        instance: DesktopInstance,
        pid: int,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + max(5, int(timeout_seconds))
        last_snapshot: dict[str, Any] = {}
        last_error = ""
        while time.monotonic() < deadline:
            try:
                target_pid = self._find_window_pid(instance) or pid
                last_snapshot = self._ui("snapshot", target_pid, instance=instance)
                last_snapshot["target_pid"] = int(target_pid)
                if last_snapshot.get("composer_ready"):
                    return last_snapshot
                if last_snapshot.get("onboarding_visible"):
                    self._ui("prepare", target_pid, instance=instance)
            except Exception as exc:
                last_error = str(exc)
            time.sleep(0.75)
        if last_snapshot.get("login_visible"):
            detail = "固定实例仍停留在登录页，OAuth 凭据未建立桌面会话"
        elif last_snapshot.get("onboarding_visible"):
            detail = "固定实例首次使用引导未能自动完成"
        else:
            detail = last_error or str(
                last_snapshot.get("window") or "window unavailable"
            )
        raise RuntimeError(f"固定实例界面未在时限内就绪: {detail}")

    async def activate(
        self,
        item: dict[str, Any],
        prompt: str = "你好",
        stage_callback: Callable[[str], None] | None = None,
        instance: DesktopInstance | None = None,
    ) -> dict[str, Any]:
        settings = get_settings()
        eligible, eligibility_reason = activation_eligibility(item)
        if not eligible:
            return {
                "ok": False,
                "error": f"库存不可正式激活: {eligibility_reason}",
                "stage": "ineligible",
                "sent_unknown": False,
            }
        if settings.dry_run:
            return {
                "ok": True,
                "reply": "dry-run: 已模拟在固定桌面实例中发送你好",
                "stage": "dry_run",
            }

        stage = "switching_account"
        pid: int | None = None

        def report_stage(
            worker_stage: str,
            result_stage: str | None = None,
        ) -> None:
            nonlocal stage
            stage = result_stage or worker_stage
            if stage_callback:
                stage_callback(worker_stage)

        try:
            report_stage("switching_account")
            instance = instance or self.resolve_instance()
            instance, _ = self._resolved_runtime(instance)
            tokens = _extract_oauth_tokens(item)
            missing = self._missing_oauth_fields(tokens)
            if missing:
                return {
                    "ok": False,
                    "error": (
                        "库存缺少桌面 Codex OAuth 字段: "
                        + ", ".join(missing)
                    ),
                    "stage": stage,
                    "sent_unknown": False,
                }

            await asyncio.to_thread(self._stop, instance)
            auth_path = await asyncio.to_thread(self._write_auth, instance, tokens)

            report_stage("verifying_account")
            verified = await asyncio.to_thread(
                self._verify_auth,
                auth_path,
                tokens,
                str(item.get("email") or ""),
            )
            if not verified:
                return {
                    "ok": False,
                    "error": "固定实例 auth.json 账号校验失败，已阻止发送",
                    "stage": stage,
                    "sent_unknown": False,
                }

            report_stage("opening_codex", "starting_desktop")
            pid = await asyncio.to_thread(self._launch, instance)
            snapshot = await asyncio.to_thread(
                self._wait_for_ui_ready,
                instance,
                pid,
                settings.desktop_start_timeout_seconds,
            )
            if not snapshot.get("window"):
                return {
                    "ok": False,
                    "error": "固定实例窗口尚未就绪",
                    "stage": stage,
                    "pid": pid,
                    "sent_unknown": False,
                }

            pid = int(snapshot.get("target_pid") or snapshot.get("process_id") or pid)
            prepared = await asyncio.to_thread(self._ui, "prepare", pid, instance=instance)
            if not prepared.get("new_chat"):
                raise RuntimeError("固定桌面实例无法创建独立新对话，已阻止发送")
            snapshot = await asyncio.to_thread(
                self._wait_for_ui_ready,
                instance,
                pid,
                min(20, settings.desktop_start_timeout_seconds),
            )
            pid = int(snapshot.get("target_pid") or snapshot.get("process_id") or pid)
            refreshed_window_pid = await asyncio.to_thread(
                self._find_window_pid,
                instance,
            )
            if refreshed_window_pid:
                pid = int(refreshed_window_pid)

            report_stage("sending")
            response = await asyncio.to_thread(self._ui, "send", pid, "你好", instance=instance)
            report_stage("waiting_response")
        except Exception as exc:
            sent_unknown = stage in {"sending", "waiting_response"}
            return {
                "ok": False,
                "error": str(exc),
                "stage": stage,
                "pid": pid,
                "sent_unknown": sent_unknown,
            }

        if not response.get("response_detected") or not response.get("reply"):
            return {
                "ok": False,
                "error": "桌面端未检测到 Codex 回复",
                "stage": "waiting_response",
                "pid": pid,
                "sent_unknown": True,
            }
        instance_closed = False
        cleanup_error = ""
        if settings.desktop_autoclose:
            try:
                await asyncio.to_thread(self._stop, instance)
                instance_closed = not bool(
                    await asyncio.to_thread(
                        self._find_root_pid,
                        instance,
                        require_window=False,
                    )
                )
                if not instance_closed:
                    cleanup_error = "固定桌面实例在激活成功后仍未退出"
            except Exception as exc:
                cleanup_error = str(exc)
        return {
            "ok": True,
            "reply": str(response.get("reply") or "")[:2000],
            "stage": "completed",
            "pid": pid,
            "instance_id": instance.instance_id,
            "instance_name": instance.name,
            "app_user_data_dir": str(instance.app_user_data_dir),
            "instance_closed": instance_closed,
            "cleanup_error": cleanup_error,
            "sent_unknown": False,
        }
