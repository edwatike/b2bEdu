import os
import sys
import time
import threading
import subprocess
import argparse
import json
import urllib.request
from dataclasses import dataclass
from typing import Optional


def _force_utf8_stdio() -> None:
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_force_utf8_stdio()

_LOG_FILE_PATH: Optional[str] = None


def _log_file_path() -> str:
    global _LOG_FILE_PATH
    if _LOG_FILE_PATH:
        return _LOG_FILE_PATH
    try:
        ts = time.strftime("%Y%m%d-%H%M%S")
        base = _abs("TEMP")
        os.makedirs(base, exist_ok=True)
        _LOG_FILE_PATH = os.path.join(base, f"launcher-ui-{ts}.log")
    except Exception:
        _LOG_FILE_PATH = os.path.abspath("launcher-ui.log")
    return _LOG_FILE_PATH


def _write_log_file(line: str) -> None:
    try:
        with open(_log_file_path(), "a", encoding="utf-8", errors="replace") as f:
            f.write(line + "\n")
    except Exception:
        return


_PRINT_LOCK = threading.Lock()
_DASH_LOCK = threading.Lock()

_LAST_DASH_SIGNATURE: Optional[str] = None
_LAST_DASH_PRINT_TS: float = 0.0

try:
    from rich.console import Console  # type: ignore
    from rich.text import Text  # type: ignore
    from rich.table import Table  # type: ignore

    _RICH_CONSOLE: Optional[Console] = Console(
        color_system="auto",
        soft_wrap=True,
        highlight=False,
        markup=False,
    )
except Exception:
    _RICH_CONSOLE = None
    Text = None  # type: ignore
    Table = None  # type: ignore

try:
    import colorama  # type: ignore

    colorama.just_fix_windows_console()
    _COLORAMA = colorama
except Exception:
    _COLORAMA = None


BACKEND_PORT = 8000
PARSER_PORT = 9000
FRONTEND_PORT = 3000
CDP_PORT = 7000
FRONTEND_URL = f"http://localhost:{FRONTEND_PORT}"

MODE2_FRONTEND_URL = (os.environ.get("B2B_MODE2_FRONTEND_URL") or "https://v0-front-two-taupe.vercel.app").strip()

NGROK_API_URL = "http://127.0.0.1:4040/api/tunnels"

PRODUCTION_DOMAIN = "b2bedu.ru"
PRODUCTION_URL = f"https://{PRODUCTION_DOMAIN}"

# ── OAuth credentials per launch mode ──────────────────────────────────
OAUTH_LOCAL = {
    "YANDEX_CLIENT_ID": "78b3e3ec886f4a7f9a1e522e8faf423c",
    "YANDEX_CLIENT_SECRET": "654c229b062a4d5fadf250ed1dec4e84",
    "YANDEX_REDIRECT_URI": "http://localhost:3000/api/yandex/callback",
}
OAUTH_PRODUCTION = {
    "YANDEX_CLIENT_ID": "f13aa94092e74191ab90ac908df3c42b",
    "YANDEX_CLIENT_SECRET": "170746997c17407bb388dd7872d2666a",
    "YANDEX_REDIRECT_URI": "https://v0-front-two-taupe.vercel.app/api/yandex/callback",
}

_LAUNCH_MODE: str = "local"  # "local" or "production"

_LAST_CDP_BROWSER: Optional[str] = None
_LAST_CDP_USED_TEMP_PROFILE: bool = False
_LAST_CDP_PROFILE_DIR: Optional[str] = None
_LAST_CDP_USER_DATA_DIR: Optional[str] = None

_CHROME_CDP_LOG_HANDLES: list[object] = []


@dataclass
class ManagedProcess:
    name: str
    popen: subprocess.Popen

    def pid(self) -> int:
        return int(self.popen.pid or 0)


def _pause_if_frozen(exit_code: int) -> None:
    if exit_code == 0:
        return
    if not getattr(sys, "frozen", False):
        return
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    try:
        input("\n[INFO] Press Enter to close...")
    except Exception:
        return


def _is_repo_root(path: str) -> bool:
    if not path or not os.path.isdir(path):
        return False
    return (
        os.path.isdir(os.path.join(path, "backend"))
        and os.path.isdir(os.path.join(path, "parser_service"))
        and os.path.isdir(os.path.join(path, "frontend"))
    )


def _repo_root() -> str:
    override = (os.environ.get("B2B_REPO_ROOT") or "").strip().strip('"')
    if override:
        override = os.path.abspath(override)
        if _is_repo_root(override):
            return override
        raise RuntimeError(f"Invalid B2B_REPO_ROOT (not a repo root): {override}")

    cwd = os.path.abspath(os.getcwd())
    if _is_repo_root(cwd):
        return cwd

    if getattr(sys, "frozen", False):
        base = os.path.abspath(os.path.dirname(sys.executable))
    else:
        base = os.path.abspath(os.path.dirname(__file__))

    cur = base
    for _ in range(10):
        if _is_repo_root(cur):
            return cur
        parent = os.path.dirname(cur)
        if not parent or parent == cur:
            break
        cur = parent

    raise RuntimeError(f"Repo root not found from base: {base}")


def _abs(*parts: str) -> str:
    return os.path.abspath(os.path.join(_repo_root(), *parts))


def _venv_python(service_dir: str) -> str:
    root = _repo_root()
    root_candidate_clean = os.path.join(root, ".venv_clean", "Scripts", "python.exe")
    if os.path.exists(root_candidate_clean):
        return root_candidate_clean
    root_candidate = os.path.join(root, ".venv", "Scripts", "python.exe")
    if os.path.exists(root_candidate):
        return root_candidate
    candidate = os.path.join(service_dir, "venv", "Scripts", "python.exe")
    if os.path.exists(candidate):
        return candidate
    return sys.executable


def _latest_mtime_in_dir(path: str) -> float:
    try:
        latest = 0.0
        for root, dirs, files in os.walk(path):
            # Skip heavy folders
            base = os.path.basename(root).lower()
            if base in {"node_modules", ".next", ".git", "dist", "build"}:
                dirs[:] = []
                continue
            for name in files:
                try:
                    fp = os.path.join(root, name)
                    mt = os.path.getmtime(fp)
                    if mt > latest:
                        latest = mt
                except Exception:
                    continue
        return float(latest)
    except Exception:
        return 0.0


def _frontend_needs_rebuild(frontend_dir: str) -> bool:
    try:
        build_id = os.path.join(frontend_dir, ".next", "BUILD_ID")
        prerender = os.path.join(frontend_dir, ".next", "prerender-manifest.json")
        if not os.path.exists(build_id) or not os.path.exists(prerender):
            return True

        build_ts = 0.0
        try:
            build_ts = max(os.path.getmtime(build_id), os.path.getmtime(prerender))
        except Exception:
            build_ts = 0.0

        # Only scan key source dirs to keep this quick
        src_dirs = [
            os.path.join(frontend_dir, "app"),
            os.path.join(frontend_dir, "components"),
            os.path.join(frontend_dir, "lib"),
            os.path.join(frontend_dir, "styles"),
            os.path.join(frontend_dir, "public"),
        ]
        latest_src = 0.0
        for d in src_dirs:
            if os.path.isdir(d):
                latest_src = max(latest_src, _latest_mtime_in_dir(d))
        return latest_src > build_ts
    except Exception:
        return False


def _stream_lines(prefix: str, stream, is_err: bool, on_line=None) -> None:
    try:
        for line in iter(stream.readline, ""):
            if not line:
                break
            line = line.rstrip("\n")
            ts = time.strftime("%H:%M:%S")
            level = _classify_level(line, is_err)
            if not _should_suppress_line(prefix, line, level):
                if on_line is not None:
                    try:
                        on_line(prefix, line, is_err)
                    except Exception:
                        pass
                _print_log_line(ts=ts, prefix=prefix, line=line, is_err=is_err)
    except Exception:
        return


def _classify_level(line: str, is_err: bool) -> str:
    s = line.lower()
    if "traceback" in s:
        return "error"
    if " error" in s or s.startswith("error") or "[err" in s or " err " in s or "winerror" in s:
        return "error"
    if "warn" in s or "warning" in s or "[warn" in s:
        return "warn"
    if "info" in s or " started" in s or "application startup complete" in s:
        return "info"
    if "ready" in s or "running on" in s or " 200 " in s or "200 ok" in s:
        return "ok"
    if is_err:
        return "warn"
    return "plain"


def _should_suppress_line(service: str, line: str, level: str) -> bool:
    # Always show logs in the launcher window (single-pane view).
    return False

    if level in ("error", "warn"):
        return False

    s = line.strip()
    if not s:
        return True

    if service == "FRONTEND":
        low = s.lower()
        # Whitelist: keep only startup / ready lines.
        if "next.js" in low:
            return False
        if low.startswith("- local:") or low.startswith("- network:") or low.startswith("- environments"):
            return False
        if "ready" in low or "starting" in low:
            return False
        # Everything else (including request logs) is noise.
        return True

    if service == "BACKEND":
        low = s.lower()
        # Whitelist: keep only lifecycle lines.
        if "fastapi app instance created" in low:
            return False
        if "application startup complete" in low:
            return False
        if "uvicorn running on" in low:
            return False
        if "starting uvicorn" in low:
            return False
        if "backend starting up" in low or "backend shutting down" in low:
            return False
        # Everything else is noise (requests/repos/debug).
        return True

    if service == "PARSER":
        low = s.lower()
        # Whitelist: keep lifecycle.
        if "uvicorn running on" in low:
            return False
        if "application startup complete" in low:
            return False
        if "started server process" in low:
            return False
        # Everything else is noise unless warn/error (handled above).
        return True

    return False


def _print_log_line(*, ts: str, prefix: str, line: str, is_err: bool) -> None:
    level = _classify_level(line, is_err)

    if _RICH_CONSOLE is not None and Text is not None:
        if level == "error":
            style = "bold red"
        elif level == "warn":
            style = "bold yellow"
        elif level == "ok":
            style = "green"
        elif level == "info":
            style = "cyan"
        else:
            style = ""

        msg = Text(f"[{ts}] [{prefix}] ")
        if style:
            msg.append(line, style=style)
        else:
            msg.append(line)

        with _PRINT_LOCK:
            try:
                _RICH_CONSOLE.print(msg)
            except Exception:
                pass
        _write_log_file(f"[{ts}] [{prefix}] {line}")
        return

    if _COLORAMA is not None:
        if level == "error":
            color = _COLORAMA.Fore.RED
        elif level == "warn":
            color = _COLORAMA.Fore.YELLOW
        elif level == "ok":
            color = _COLORAMA.Fore.GREEN
        elif level == "info":
            color = _COLORAMA.Fore.CYAN
        else:
            color = ""
        reset = _COLORAMA.Style.RESET_ALL
    else:
        if level == "error":
            color = "\x1b[31m"
        elif level == "warn":
            color = "\x1b[33m"
        elif level == "ok":
            color = "\x1b[32m"
        elif level == "info":
            color = "\x1b[36m"
        else:
            color = ""
        reset = "\x1b[0m" if color else ""

    out = sys.stderr if level == "error" else sys.stdout
    with _PRINT_LOCK:
        try:
            out.write(f"[{ts}] [{prefix}] {color}{line}{reset}\n")
            out.flush()
        except Exception:
            pass
    _write_log_file(f"[{ts}] [{prefix}] {line}")


def _log_system(message: str, level: str = "info") -> None:
    ts = time.strftime("%H:%M:%S")
    prefix = "LAUNCHER"
    is_err = level.lower() in ("error", "err")
    _print_log_line(ts=ts, prefix=prefix, line=message, is_err=is_err)


def _dashboard_row_style(status: str) -> str:
    s = (status or "").upper()
    if s == "READY":
        return "green"
    if s == "FAILED":
        return "bold red"
    if s == "STARTING":
        return "yellow"
    if s == "WAITING":
        return "dim yellow"
    if s == "SKIPPED":
        return "dim"
    return ""


def _short_error(line: str, limit: int = 140) -> str:
    s = (line or "").strip().replace("\t", " ")
    while "  " in s:
        s = s.replace("  ", " ")
    if len(s) <= limit:
        return s
    return s[: limit - 3] + "..."


def _print_dashboard(state: dict[str, dict[str, object]]) -> None:
    if not state:
        return

    global _LAST_DASH_SIGNATURE, _LAST_DASH_PRINT_TS
    # Only re-print dashboard on meaningful state changes (status / last_error),
    # not on PID-only updates.
    _dashboard_services = ["PARSER", "BACKEND", "FRONTEND", "CDP"]
    if "TUNNEL" in state:
        _dashboard_services.append("TUNNEL")
    signature = "|".join(
        [
            ",".join(
                [
                    name,
                    str(state.get(name, {}).get("status", "")),
                    str(state.get(name, {}).get("last_error", "")),
                ]
            )
            for name in _dashboard_services
        ]
    )
    # If status/last_error didn't change, do not re-print dashboard.
    if signature == _LAST_DASH_SIGNATURE:
        return
    _LAST_DASH_SIGNATURE = signature
    _LAST_DASH_PRINT_TS = time.time()
    def _crop(s: object, width: int) -> str:
        t = str(s or "")
        if width <= 0:
            return ""
        if len(t) <= width:
            return t.ljust(width)
        if width <= 1:
            return t[:width]
        return (t[: width - 1] + "…")

    # A readable fixed-width table that works in any console.
    cols = [
        ("Service", 9),
        ("Port", 5),
        ("PID", 7),
        ("Status", 10),
        ("URL", 31),
        ("LastError", 48),
    ]

    def _hline(left: str, mid: str, right: str) -> str:
        return left + mid.join(["─" * w for _, w in cols]) + right

    header = "│" + "│".join([_crop(name, w) for name, w in cols]) + "│"
    top = _hline("┌", "┬", "┐")
    sep = _hline("├", "┼", "┤")
    bot = _hline("└", "┴", "┘")

    rows: list[str] = []
    for name in _dashboard_services:
        row = state.get(name, {})
        cells = [
            _crop(name, cols[0][1]),
            _crop(row.get("port", ""), cols[1][1]),
            _crop(row.get("pid", ""), cols[2][1]),
            _crop(row.get("status", ""), cols[3][1]),
            _crop(row.get("url", ""), cols[4][1]),
            _crop(row.get("last_error", ""), cols[5][1]),
        ]
        rows.append("│" + "│".join(cells) + "│")

    plain_lines = [top, header, sep, *rows, bot]
    plain_table = "\n".join(plain_lines)

    if _RICH_CONSOLE is not None and Table is not None:
        try:
            table = Table(show_header=True, header_style="bold")
            table.add_column("Service", no_wrap=True)
            table.add_column("Port", justify="right", no_wrap=True)
            table.add_column("PID", justify="right", no_wrap=True)
            table.add_column("Status", no_wrap=True)
            table.add_column("URL")
            table.add_column("LastError")

            for name in _dashboard_services:
                row = state.get(name, {})
                port = str(row.get("port", ""))
                pid = str(row.get("pid", ""))
                status = str(row.get("status", ""))
                url = str(row.get("url", ""))
                last_error = str(row.get("last_error", ""))
                style = _dashboard_row_style(status)
                table.add_row(name, port, pid, status, url, last_error, style=style or None)

            with _PRINT_LOCK:
                _RICH_CONSOLE.print(table)
            _write_log_file(plain_table)
            return
        except Exception as e:
            # Some PyInstaller builds may ship incomplete rich unicode tables.
            # Fall back to plain output instead of crashing the launcher.
            try:
                _log_system(f"Rich dashboard failed, falling back to plain output: {type(e).__name__}: {e}", level="warn")
            except Exception:
                pass
            try:
                globals()["_RICH_CONSOLE"] = None
            except Exception:
                pass

    with _PRINT_LOCK:
        try:
            sys.stdout.write(plain_table + "\n")
            sys.stdout.flush()
        except Exception:
            pass
    _write_log_file(plain_table)


def _start_process(
    *,
    name: str,
    args: list[str],
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
    on_line=None,
) -> ManagedProcess:
    merged_env = {**os.environ, **(env or {})}
    merged_env.setdefault("PYTHONUNBUFFERED", "1")
    p = subprocess.Popen(
        args,
        cwd=cwd,
        env=merged_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    if p.stdout is not None:
        threading.Thread(target=_stream_lines, args=(name, p.stdout, False, on_line), daemon=True).start()
    if p.stderr is not None:
        threading.Thread(target=_stream_lines, args=(name, p.stderr, True, on_line), daemon=True).start()

    return ManagedProcess(name=name, popen=p)


def _taskkill_tree(pid: int) -> None:
    if pid <= 0:
        return
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        return


def _taskkill_tree_by_name(name: str) -> None:
    if not name:
        return
    try:
        subprocess.run(["taskkill", "/IM", name, "/T", "/F"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        return


def _wait_no_process(name: str, timeout_sec: int = 10) -> None:
    end = time.time() + timeout_sec
    while time.time() < end:
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", f"Get-Process -Name {name} -ErrorAction SilentlyContinue"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=5,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if not (r.stdout or "").strip():
                return
        except subprocess.TimeoutExpired:
            return
        except Exception:
            return
        time.sleep(0.5)


def _pids_listening_on_port(port: int) -> list[int]:
    pids: set[int] = set()

    # Preferred (language-independent) way on Windows.
    try:
        ps = (
            "$p=(Get-NetTCPConnection -State Listen -LocalPort "
            + str(port)
            + " -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess); "
            "if ($null -ne $p) { $p }"
        )
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        for raw in (r.stdout or "").splitlines():
            s = raw.strip()
            if not s:
                continue
            try:
                pid = int(s)
            except Exception:
                continue
            if pid > 0 and pid != os.getpid():
                pids.add(pid)
        if pids:
            return sorted(pids)
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass

    # Fallback: parse netstat output.
    try:
        r = subprocess.run(
            ["cmd", "/c", f"netstat -ano | findstr :{port}"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return []
    except Exception:
        return []

    for raw in (r.stdout or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if "LISTEN" not in line.upper():
            continue
        parts = line.split()
        if not parts:
            continue
        pid_s = parts[-1]
        try:
            pid = int(pid_s)
        except Exception:
            continue
        if pid > 0 and pid != os.getpid():
            pids.add(pid)

    return sorted(pids)


def _free_ports(ports: list[int]) -> None:
    for port in ports:
        pids = _pids_listening_on_port(port)
        if not pids:
            continue
        for pid in pids:
            _log_system(f"Port {port} is in use by PID {pid}. Stopping it...", level="warn")
            _taskkill_tree(pid)
        # Wait up to 10s for port to be released
        deadline = time.time() + 10
        while time.time() < deadline:
            if not _pids_listening_on_port(port):
                break
            time.sleep(0.5)


def _wait_http_ready(url: str, timeout_sec: int) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if _http_ok(url, timeout_sec=2):
            return True
        time.sleep(1)
    return False


def _http_ok(url: str, timeout_sec: int = 2) -> bool:
    try:
        import urllib.request
        import urllib.error

        req = urllib.request.Request(url, method="GET")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=timeout_sec) as resp:
            return 200 <= int(getattr(resp, "status", 0) or 0) < 500
    except Exception:
        return False


def _find_chrome_exe() -> Optional[str]:
    candidates = [
        os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def _find_ngrok_exe() -> Optional[str]:
    override = (os.environ.get("NGROK_EXE") or "").strip().strip('"')
    if override:
        override = os.path.abspath(override)
        if os.path.exists(override):
            return override

    candidates = [
        _abs("ngrok.exe"),
        os.path.join(_repo_root(), "ngrok.exe"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def _ngrok_public_url(timeout_sec: int = 20) -> Optional[str]:
    deadline = time.time() + max(1, int(timeout_sec))
    while time.time() < deadline:
        try:
            resp = urllib.request.urlopen(NGROK_API_URL, timeout=2)
            raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
            tunnels = data.get("tunnels") if isinstance(data, dict) else None
            if isinstance(tunnels, list):
                for t in tunnels:
                    if not isinstance(t, dict):
                        continue
                    public_url = t.get("public_url")
                    if isinstance(public_url, str) and public_url.startswith("https://"):
                        return public_url
        except Exception:
            pass
        time.sleep(1)
    return None


def _start_ngrok_backend_tunnel(on_line=None) -> Optional[ManagedProcess]:
    exe = _find_ngrok_exe()
    if not exe:
        _log_system("ngrok.exe not found. Set NGROK_EXE or place ngrok.exe in repo root.", level="error")
        return None

    args = [exe, "http", str(BACKEND_PORT), "--log", "stdout"]
    mp = _start_process(
        name="NGROK",
        args=args,
        cwd=_repo_root(),
        env={**os.environ},
        on_line=on_line,
    )
    return mp


def _find_comet_exe() -> Optional[str]:
    override = (os.environ.get("COMET_EXE") or "").strip().strip('"')
    if override:
        override = os.path.abspath(override)
        if os.path.exists(override):
            return override
        # Intentionally suppress COMET_EXE-missing warnings: users often have placeholder values.

    local = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("PROGRAMFILES", "C:\\Program Files")
    program_files_x86 = os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")

    candidates = [
        os.path.join(local, "Perplexity", "Comet", "Application", "comet.exe"),
        os.path.join(local, "Perplexity", "Comet", "Application", "Comet.exe"),
        os.path.join(local, "Comet", "Application", "comet.exe"),
        os.path.join(local, "Comet", "Application", "Comet.exe"),
        os.path.join(local, "Programs", "Comet", "Comet.exe"),
        os.path.join(local, "Programs", "Comet", "comet.exe"),
        os.path.join(program_files, "Comet", "Application", "comet.exe"),
        os.path.join(program_files, "Comet", "Application", "Comet.exe"),
        os.path.join(program_files_x86, "Comet", "Application", "comet.exe"),
        os.path.join(program_files_x86, "Comet", "Application", "Comet.exe"),
        os.path.join(program_files, "Perplexity", "Comet", "Application", "comet.exe"),
        os.path.join(program_files, "Perplexity", "Comet", "Application", "Comet.exe"),
        os.path.join(program_files_x86, "Perplexity", "Comet", "Application", "comet.exe"),
        os.path.join(program_files_x86, "Perplexity", "Comet", "Application", "Comet.exe"),
    ]

    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def _resolve_chrome_user_data_dir() -> Optional[str]:
    override = (os.environ.get("B2B_CDP_USER_DATA_DIR") or "").strip().strip('"')
    if override:
        override = os.path.abspath(override)
        if os.path.isdir(override):
            return override
    local = os.environ.get("LOCALAPPDATA", "")
    candidate = os.path.join(local, "Google", "Chrome", "User Data")
    if os.path.isdir(candidate):
        return candidate
    return None


def _default_chrome_user_data_dir() -> Optional[str]:
    local = os.environ.get("LOCALAPPDATA", "")
    candidate = os.path.join(local, "Google", "Chrome", "User Data")
    if os.path.isdir(candidate):
        return candidate
    return None


def _ensure_non_default_user_data_dir(user_data_dir: str) -> str:
    if not user_data_dir:
        return user_data_dir
    try:
        default_dir = _default_chrome_user_data_dir()
        if not default_dir:
            return user_data_dir
        if os.path.normcase(os.path.abspath(user_data_dir)) != os.path.normcase(os.path.abspath(default_dir)):
            return user_data_dir

        link_dir = _abs("TEMP", "chrome-user-data")
        try:
            os.makedirs(os.path.dirname(link_dir), exist_ok=True)
        except Exception:
            return user_data_dir

        if os.path.isdir(link_dir):
            return link_dir

        r = subprocess.run(
            [
                "cmd",
                "/c",
                "mklink",
                "/J",
                link_dir,
                default_dir,
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if r.returncode == 0 and os.path.isdir(link_dir):
            return link_dir
    except Exception:
        pass
    return user_data_dir


def _list_chrome_profiles(user_data_dir: str) -> list[str]:
    if not user_data_dir or not os.path.isdir(user_data_dir):
        return []
    profiles: list[str] = []
    default_dir = os.path.join(user_data_dir, "Default")
    if os.path.isdir(default_dir):
        profiles.append("Default")

    extra: list[str] = []
    for entry in os.listdir(user_data_dir):
        if not entry.startswith("Profile "):
            continue
        full = os.path.join(user_data_dir, entry)
        if os.path.isdir(full):
            extra.append(entry)

    def _profile_key(name: str) -> tuple[int, str]:
        tail = name.replace("Profile", "").strip()
        try:
            return (int(tail), name)
        except Exception:
            return (9999, name)

    extra_sorted = sorted(extra, key=_profile_key)
    for name in extra_sorted:
        if name not in profiles:
            profiles.append(name)
    return profiles


def _resolve_chrome_profile_dir(user_data_dir: Optional[str]) -> str:
    override = (os.environ.get("B2B_CDP_PROFILE_DIR") or "").strip()
    if override:
        return override
    if not user_data_dir:
        return "Default"

    profiles = _list_chrome_profiles(user_data_dir)
    if "Default" in profiles:
        return "Default"
    if profiles:
        return profiles[0]
    return "Default"


def _start_chrome_cdp(
    prefer: Optional[str] = None,
    force_temp_profile: bool = False,
    profile_dir_override: Optional[str] = None,
    user_data_dir_override: Optional[str] = None,
) -> Optional[subprocess.Popen]:
    global _LAST_CDP_BROWSER, _LAST_CDP_USED_TEMP_PROFILE, _LAST_CDP_PROFILE_DIR, _LAST_CDP_USER_DATA_DIR
    chrome = _find_chrome_exe()
    if not chrome:
        _log_system("Chrome not found. Skipping CDP launch.", level="warn")
        _LAST_CDP_BROWSER = "chrome"
        _LAST_CDP_USED_TEMP_PROFILE = False
        return None

    # If the CDP port is already in use, do not spawn another browser.
    if _pids_listening_on_port(CDP_PORT):
        _log_system(f"CDP port {CDP_PORT} already in use. Skipping browser launch.", level="warn")
        return None

    _log_system(f"Launching Chrome with CDP on port {CDP_PORT}: {chrome}", level="info")

    # Strict mode: only real Chrome profiles, no temp/comet fallback.
    user_data_dir = (user_data_dir_override or os.environ.get("B2B_CDP_USER_DATA_DIR") or "").strip()
    if not user_data_dir:
        user_data_dir = _resolve_chrome_user_data_dir() or ""
    if not user_data_dir:
        _log_system("Chrome user data dir not found. Real profile required; CDP launch skipped.", level="warn")
        return None

    user_data_dir = _ensure_non_default_user_data_dir(user_data_dir)

    profile_dir = (profile_dir_override or os.environ.get("B2B_CDP_PROFILE_DIR") or "").strip()
    if not profile_dir:
        profile_dir = _resolve_chrome_profile_dir(user_data_dir)
    if not profile_dir:
        profile_dir = "Default"

    profile_path = os.path.join(user_data_dir, profile_dir)
    if not os.path.isdir(profile_path):
        _log_system(f"Chrome profile not found: {profile_dir} (user-data: {user_data_dir})", level="warn")
        return None

    use_real_profile = "1"
    if force_temp_profile:
        _log_system("Temp profile disabled; using real Chrome profile.", level="warn")
    # If Chrome is already running with the real profile, it will ignore remote-debugging-port.
    # To guarantee CDP availability, optionally close Chrome before launch.
    kill_running_chrome = (os.environ.get("B2B_CDP_KILL_CHROME") or "").strip().lower()
    if kill_running_chrome in {"", "0", "false", "no"}:
        kill_running_chrome = "0"
    else:
        kill_running_chrome = "1"
    _LAST_CDP_BROWSER = "chrome"
    _LAST_CDP_USED_TEMP_PROFILE = False
    _LAST_CDP_PROFILE_DIR = profile_dir
    _LAST_CDP_USER_DATA_DIR = user_data_dir
    _log_system(f"CDP profile: {profile_dir} (real)", level="info")

    args = [
        chrome,
        f"--remote-debugging-port={CDP_PORT}",
        "--remote-debugging-address=127.0.0.1",
        f"--user-data-dir={user_data_dir}",
        f"--profile-directory={profile_dir}",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if (os.environ.get("B2B_CDP_HEADLESS") or "").strip().lower() in {"1", "true", "yes"}:
        args.append("--headless=new")
    open_url = (os.environ.get("B2B_CDP_OPEN_URL") or "").strip().lower()
    if open_url in {"0", "false", "no"}:
        open_url = "0"
    else:
        open_url = "1"
    if open_url == "1":
        args.extend(["--new-window", FRONTEND_URL])

    try:
        if use_real_profile == "1" and kill_running_chrome == "1":
            _log_system("Closing running Chrome instances to enable CDP on real profile...", level="warn")
            _taskkill_tree_by_name("chrome.exe")
            _wait_no_process("chrome", timeout_sec=15)
            # Clean stale singleton locks that can prevent CDP from binding.
            try:
                for fname in ("DevToolsActivePort", "SingletonLock", "SingletonSocket", "SingletonCookie"):
                    fpath = os.path.join(user_data_dir, fname)
                    if os.path.exists(fpath):
                        os.remove(fpath)
            except Exception:
                pass

        try:
            chrome_log_path = os.path.join(_abs("TEMP"), "chrome-cdp.log")
            os.makedirs(os.path.dirname(chrome_log_path), exist_ok=True)
            chrome_log = open(chrome_log_path, "a", encoding="utf-8", errors="replace")
            _CHROME_CDP_LOG_HANDLES.append(chrome_log)
            _log_system(f"Chrome CDP log: {chrome_log_path}", level="info")
            return subprocess.Popen(args, stdout=chrome_log, stderr=chrome_log)
        except Exception:
            return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        _log_system(f"Failed to start Chrome: {type(e).__name__}: {e}", level="warn")
        return None


def _ask_launch_mode() -> str:
    """Ask user to choose between local and production (Vercel + ngrok) mode."""
    global _LAUNCH_MODE

    override = (os.environ.get("B2B_LAUNCH_MODE") or "").strip().lower()
    if override in ("local", "production"):
        _LAUNCH_MODE = override
        _log_system(f"Launch mode from env: {_LAUNCH_MODE}", level="info")
        return _LAUNCH_MODE

    print()
    print("=" * 58)
    print("  B2B Platform — Выбор режима запуска")
    print("=" * 58)
    print()
    print("  [1] Local — всё локально")
    print("      Frontend:  http://localhost:3000")
    print("      Backend:   http://localhost:8000")
    print("      OAuth:     localhost redirect")
    print()
    print("  [2] Production — Vercel фронт + ngrok backend")
    print(f"      Frontend:  {MODE2_FRONTEND_URL}")
    print("      Backend:   ngrok → localhost:8000")
    print("      OAuth:     Vercel redirect")
    print()
    print("=" * 58)

    def _input_with_timeout(prompt: str, timeout_sec: int) -> Optional[str]:
        result: dict[str, Optional[str]] = {"value": None}
        done = threading.Event()

        def _worker() -> None:
            try:
                result["value"] = input(prompt)
            except Exception:
                result["value"] = None
            finally:
                done.set()

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        done.wait(timeout=timeout_sec)
        return result["value"]

    timeout_sec = 30
    while True:
        raw = _input_with_timeout("  Выберите режим [1/2] (auto=1 in 30s): ", timeout_sec)
        if raw is None:
            choice = "1"
        else:
            choice = str(raw).strip()
        if choice in ("1", ""):
            _LAUNCH_MODE = "local"
            break
        if choice == "2":
            _LAUNCH_MODE = "production"
            break
        print("  Введите 1 или 2")

    _log_system(f"Launch mode: {_LAUNCH_MODE}", level="info")
    return _LAUNCH_MODE


def _detect_vpn_tun() -> Optional[str]:
    """Detect if a VPN TUN adapter (sing-box, Hiddify, etc.) is active."""
    try:
        import subprocess as _sp
        out = _sp.check_output(
            ["powershell", "-NoProfile", "-Command",
             "Get-NetAdapter | Where-Object {$_.Status -eq 'Up' -and $_.InterfaceDescription -match 'sing-tun|happ-tun|wintun|wireguard'} | Select-Object -ExpandProperty Name"],
            timeout=10, text=True, stderr=_sp.DEVNULL,
        ).strip()
        if out:
            return out
    except Exception:
        pass
    return None


def _find_cloudflared_exe() -> Optional[str]:
    """Find cloudflared.exe in the repo root."""
    candidates = [
        _abs("cloudflared.exe"),
        _abs("cloudflared-new.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def _find_cloudflared_config() -> Optional[str]:
    """Find the cloudflared config for b2bedu.ru tunnel."""
    candidates = [
        _abs("cloudflared-b2bedu.yml"),
        _abs("cloudflared.yml"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def _start_cloudflared_tunnel(on_line=None) -> Optional[ManagedProcess]:
    """Start cloudflared tunnel for production mode."""
    exe = _find_cloudflared_exe()
    if not exe:
        _log_system("cloudflared.exe not found. Cannot start tunnel.", level="error")
        return None

    config = _find_cloudflared_config()
    if not config:
        _log_system("Cloudflare tunnel config not found.", level="error")
        return None

    _log_system(f"Starting Cloudflare Tunnel: {exe}", level="info")
    _log_system(f"Config: {config}", level="info")

    args = [exe, "tunnel", "--config", config, "run"]

    mp = _start_process(
        name="TUNNEL",
        args=args,
        cwd=_repo_root(),
        env={**os.environ},
        on_line=on_line,
    )
    return mp


def _wait_tunnel_ready(timeout_sec: int = 30) -> bool:
    """Wait for the tunnel to establish connection by checking if the domain resolves."""
    import urllib.request
    import urllib.error

    deadline = time.time() + timeout_sec
    _log_system(f"Waiting for {PRODUCTION_URL} to become available (up to {timeout_sec}s)...", level="info")
    while time.time() < deadline:
        try:
            req = urllib.request.Request(PRODUCTION_URL, method="HEAD")
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=5) as resp:
                status = int(getattr(resp, "status", 0) or 0)
                if 200 <= status < 500:
                    return True
        except Exception:
            pass
        time.sleep(2)
    return False


def main() -> int:
    global _LAUNCH_MODE
    _LAUNCH_MODE = ""  # Initialize global variable
    
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--repo-root", dest="repo_root", default=None)
    parser.add_argument("--mode", dest="mode", default=None, choices=["local", "production"])
    args, _ = parser.parse_known_args()
    if args.repo_root:
        os.environ["B2B_REPO_ROOT"] = args.repo_root
    if args.mode:
        os.environ["B2B_LAUNCH_MODE"] = args.mode

    root = _repo_root()

    # Ask user to choose launch mode (local or production)
    launch_mode = _ask_launch_mode()
    is_production = launch_mode == "production"

    if is_production:
        # Временно отключаем проверку VPN для тестирования режима 2
        pass

    parser_dir = _abs("parser_service")
    backend_dir = _abs("backend")
    frontend_dir = _abs("frontend", "moderator-dashboard-ui")

    frontend_build_id = os.path.join(frontend_dir, ".next", "BUILD_ID")
    frontend_prerender_manifest = os.path.join(frontend_dir, ".next", "prerender-manifest.json")

    procs: list[ManagedProcess] = []
    chrome_proc: Optional[subprocess.Popen] = None
    cdp_last_launch_ts: float = 0.0
    cdp_launched_once: bool = False
    cdp_user_data_dir: Optional[str] = None
    cdp_profile_dir: Optional[str] = None

    dashboard: dict[str, dict[str, object]] = {
        "PARSER": {"port": PARSER_PORT, "pid": "", "status": "STARTING", "url": f"http://127.0.0.1:{PARSER_PORT}", "last_error": ""},
        "BACKEND": {"port": BACKEND_PORT, "pid": "", "status": "STARTING", "url": f"http://127.0.0.1:{BACKEND_PORT}", "last_error": ""},
        "FRONTEND": {"port": FRONTEND_PORT, "pid": "", "status": "STARTING", "url": FRONTEND_URL, "last_error": ""},
        "CDP": {"port": CDP_PORT, "pid": "", "status": "STARTING", "url": f"http://127.0.0.1:{CDP_PORT}", "last_error": ""},
    }
    if is_production:
        dashboard["FRONTEND"]["status"] = "SKIPPED"
        dashboard["FRONTEND"]["pid"] = ""
        dashboard["FRONTEND"]["url"] = MODE2_FRONTEND_URL
        dashboard["FRONTEND"]["last_error"] = "vercel frontend"
        dashboard["NGROK"] = {"port": BACKEND_PORT, "pid": "", "status": "WAITING", "url": "", "last_error": "waiting for backend"}

    def on_line(service: str, line: str, is_err: bool) -> None:
        lvl = _classify_level(line, is_err)
        if lvl != "error":
            return
        if service not in dashboard:
            return
        short = _short_error(line)
        with _DASH_LOCK:
            dashboard[service]["last_error"] = short

    def _is_core_ready() -> bool:
        if is_production:
            return (
                str(dashboard["PARSER"].get("status")) == "READY"
                and str(dashboard["BACKEND"].get("status")) == "READY"
            )
        return (
            str(dashboard["PARSER"].get("status")) == "READY"
            and str(dashboard["BACKEND"].get("status")) == "READY"
            and str(dashboard["FRONTEND"].get("status")) == "READY"
        )

    try:
        ports_to_free = [BACKEND_PORT, PARSER_PORT]
        if not is_production:
            ports_to_free.append(FRONTEND_PORT)
        if (os.environ.get("B2B_CDP_FORCE_RESTART") or "").strip().lower() in {"1", "true", "yes"}:
            ports_to_free.append(CDP_PORT)
        _free_ports(ports_to_free)
        _print_dashboard(dashboard)

        parser_py = _venv_python(parser_dir)
        backend_py = _venv_python(backend_dir)

        parser_env = {**os.environ}
        parser_env["CHROME_CDP_URL"] = f"http://127.0.0.1:{CDP_PORT}"
        parser_env["USE_CHROME_CDP"] = "true"
        start_specs: dict[str, dict[str, object]] = {}
        restart_state: dict[str, dict[str, object]] = {}
        health_fail_streak: dict[str, int] = {}
        try:
            cdp_timeout_real = int((os.environ.get("B2B_CDP_STARTUP_TIMEOUT") or "60").strip() or "60")
        except Exception:
            cdp_timeout_real = 60

        cdp_user_data_dir = _resolve_chrome_user_data_dir()
        cdp_profile_dir = _resolve_chrome_profile_dir(cdp_user_data_dir)

        def _rate_limited(service: str) -> bool:
            st = restart_state.setdefault(service, {"window_start": 0.0, "count": 0, "last": 0.0, "cooldown": 2.0})
            now = time.time()
            ws = float(st.get("window_start") or 0.0)
            if ws <= 0.0 or (now - ws) > 600:
                st["window_start"] = now
                st["count"] = 0
                st["cooldown"] = 2.0
            st["count"] = int(st.get("count") or 0)
            if int(st["count"]) >= 8:
                return True
            last = float(st.get("last") or 0.0)
            cd = float(st.get("cooldown") or 2.0)
            if last > 0.0 and (now - last) < cd:
                return True
            return False

        def _bump_restart(service: str) -> None:
            st = restart_state.setdefault(service, {"window_start": time.time(), "count": 0, "last": 0.0, "cooldown": 2.0})
            st["count"] = int(st.get("count") or 0) + 1
            st["last"] = time.time()
            st["cooldown"] = min(float(st.get("cooldown") or 2.0) * 2.0, 60.0)

        def _start_named(service: str) -> ManagedProcess:
            spec = start_specs[service]
            mp = _start_process(
                name=service,
                args=list(spec["args"]),
                cwd=str(spec.get("cwd") or "") or None,
                env=dict(spec.get("env") or {}),
                on_line=on_line,
            )
            return mp

        def _replace_proc(service: str, mp: ManagedProcess) -> None:
            for i, p in enumerate(procs):
                if p.name == service:
                    procs[i] = mp
                    return
            procs.append(mp)

        def _restart_service(service: str, reason: str) -> None:
            if service not in start_specs:
                return
            if _rate_limited(service):
                _log_system(f"{service} restart rate-limited: {reason}", level="warn")
                return
            _bump_restart(service)
            _log_system(f"Restarting {service}: {reason}", level="warn")
            port_map = {
                "PARSER": PARSER_PORT,
                "BACKEND": BACKEND_PORT,
                "FRONTEND": FRONTEND_PORT,
                "CDP": CDP_PORT,
            }
            if service in port_map:
                _free_ports([port_map[service]])
            for p in list(procs):
                if p.name == service:
                    try:
                        _taskkill_tree(p.pid())
                    except Exception:
                        pass
            try:
                mp = _start_named(service)
                _replace_proc(service, mp)
                if service in dashboard:
                    dashboard[service]["pid"] = mp.pid()
                    dashboard[service]["status"] = "STARTING"
                    dashboard[service]["last_error"] = reason
                health_fail_streak[service] = 0
                _print_dashboard(dashboard)
            except Exception as e:
                if service in dashboard:
                    dashboard[service]["status"] = "FAILED"
                    dashboard[service]["last_error"] = str(e)[:200]
                    _print_dashboard(dashboard)

        start_specs["PARSER"] = {
            "args": [parser_py, "-u", _abs("parser_service", "run_api.py")],
            "cwd": parser_dir,
            "env": parser_env,
        }
        mp_parser = _start_named("PARSER")
        _replace_proc("PARSER", mp_parser)
        dashboard["PARSER"]["pid"] = mp_parser.pid()
        _print_dashboard(dashboard)

        time.sleep(1)
        backend_env = {**os.environ}
        if is_production:
            # Mode 2: allow Vercel frontend origin + ngrok origins
            extra_origins = f",{MODE2_FRONTEND_URL}"
            backend_env["CORS_ORIGINS"] = backend_env.get("CORS_ORIGINS", "") + extra_origins
        start_specs["BACKEND"] = {
            "args": [backend_py, "-u", _abs("backend", "run_api.py")],
            "cwd": backend_dir,
            "env": backend_env,
        }
        mp_backend = _start_named("BACKEND")
        _replace_proc("BACKEND", mp_backend)
        dashboard["BACKEND"]["pid"] = mp_backend.pid()
        _print_dashboard(dashboard)

        if not is_production:
            fe_env = {**os.environ}
            fe_env["NODE_OPTIONS"] = "--max-old-space-size=2048"
            fe_env["NEXT_TELEMETRY_DISABLED"] = "1"
            fe_env["NEXT_PUBLIC_API_URL"] = f"http://127.0.0.1:{BACKEND_PORT}"
            fe_env["NEXT_PUBLIC_PARSER_URL"] = f"http://127.0.0.1:{PARSER_PORT}"
            fe_env["PORT"] = str(FRONTEND_PORT)
            # Mode 1: inject Yandex OAuth credentials for local frontend
            for k, v in OAUTH_LOCAL.items():
                fe_env[k] = v

            try:
                if _frontend_needs_rebuild(frontend_dir):
                    fe_env["FORCE_BUILD"] = "1"
            except Exception:
                pass

            start_specs["FRONTEND"] = {
                "args": [
                    "cmd",
                    "/c",
                    (
                        "(if /I \"%FORCE_BUILD%\"==\"1\" (npm run clean && npm run build)) "
                        "&& (if not exist .next\\BUILD_ID (npm run build)) "
                        "&& (if not exist .next\\prerender-manifest.json (npm run build)) "
                        f"&& npm run start -- -p {FRONTEND_PORT}"
                    ),
                ],
                "cwd": frontend_dir,
                "env": {**fe_env, "NODE_ENV": "production"},
            }
            mp_frontend = _start_named("FRONTEND")
            _replace_proc("FRONTEND", mp_frontend)
            dashboard["FRONTEND"]["pid"] = mp_frontend.pid()
            _print_dashboard(dashboard)

        if _wait_http_ready(f"http://127.0.0.1:{PARSER_PORT}/health", 60):
            dashboard["PARSER"]["status"] = "READY"
        else:
            dashboard["PARSER"]["status"] = "FAILED"
            dashboard["PARSER"]["last_error"] = "health check timeout"
        _print_dashboard(dashboard)

        if _wait_http_ready(f"http://127.0.0.1:{BACKEND_PORT}/health", 60):
            dashboard["BACKEND"]["status"] = "READY"
        else:
            dashboard["BACKEND"]["status"] = "FAILED"
            dashboard["BACKEND"]["last_error"] = "health check timeout"
        _print_dashboard(dashboard)

        if not is_production:
            if _wait_http_ready(f"{FRONTEND_URL}/login", 120):
                dashboard["FRONTEND"]["status"] = "READY"
            else:
                dashboard["FRONTEND"]["status"] = "FAILED"
                dashboard["FRONTEND"]["last_error"] = "login page timeout"
            _print_dashboard(dashboard)

        if _is_core_ready():
            # Reuse existing CDP if already running to avoid spawning many windows.
            if _http_ok(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout_sec=2):
                dashboard["CDP"]["status"] = "READY"
                dashboard["CDP"]["last_error"] = ""
            else:
                if chrome_proc is not None and chrome_proc.poll() is None:
                    # CDP is still starting; don't spawn another browser.
                    dashboard["CDP"]["status"] = "STARTING"
                    dashboard["CDP"]["last_error"] = "waiting for cdp to become ready"
                elif cdp_launched_once and (os.environ.get("B2B_CDP_ALLOW_RESTART") or "").strip().lower() not in {"1", "true", "yes"}:
                    # Only launch once by default to prevent multiple windows.
                    dashboard["CDP"]["status"] = "FAILED"
                    dashboard["CDP"]["last_error"] = "cdp launch already attempted; restart disabled"
                else:
                    chrome_proc = _start_chrome_cdp(
                        prefer="chrome",
                        profile_dir_override=cdp_profile_dir,
                        user_data_dir_override=cdp_user_data_dir,
                    )
                    cdp_launched_once = True
                if chrome_proc is not None and chrome_proc.pid:
                    dashboard["CDP"]["pid"] = int(chrome_proc.pid)
                    cdp_last_launch_ts = time.time()
                if chrome_proc is not None:
                    if _wait_http_ready(f"http://127.0.0.1:{CDP_PORT}/json/version", cdp_timeout_real):
                        dashboard["CDP"]["status"] = "READY"
                        dashboard["CDP"]["last_error"] = ""
                    else:
                        dashboard["CDP"]["status"] = "FAILED"
                        profile_label = cdp_profile_dir or "Default"
                        dashboard["CDP"]["last_error"] = f"cdp /json/version timeout (profile {profile_label})"
        else:
            dashboard["CDP"]["status"] = "SKIPPED"
            dashboard["CDP"]["last_error"] = "waiting for core services READY"

        _print_dashboard(dashboard)

        ngrok_proc: Optional[ManagedProcess] = None
        if is_production and _is_core_ready():
            dashboard["NGROK"]["status"] = "STARTING"
            dashboard["NGROK"]["last_error"] = ""
            _print_dashboard(dashboard)
            ngrok_proc = _start_ngrok_backend_tunnel(on_line=on_line)
            if ngrok_proc is not None:
                _replace_proc("NGROK", ngrok_proc)
                dashboard["NGROK"]["pid"] = ngrok_proc.pid()
                _print_dashboard(dashboard)
                public_url = _ngrok_public_url(timeout_sec=20)
                if public_url:
                    dashboard["NGROK"]["status"] = "READY"
                    dashboard["NGROK"]["url"] = public_url
                    dashboard["NGROK"]["last_error"] = "set this URL as NEXT_PUBLIC_API_URL / BACKEND_URL in Vercel"
                    _log_system(f"Backend public URL: {public_url}", level="ok")
                else:
                    dashboard["NGROK"]["status"] = "READY"
                    dashboard["NGROK"]["last_error"] = "ngrok running (public url not detected)"
            else:
                dashboard["NGROK"]["status"] = "FAILED"
                dashboard["NGROK"]["last_error"] = "ngrok.exe not found"
            _print_dashboard(dashboard)
        elif is_production and not _is_core_ready():
            dashboard["NGROK"]["status"] = "SKIPPED"
            dashboard["NGROK"]["last_error"] = "core services not ready"
            _print_dashboard(dashboard)

        health_urls = {
            "PARSER": f"http://127.0.0.1:{PARSER_PORT}/health",
            "BACKEND": f"http://127.0.0.1:{BACKEND_PORT}/health",
            "CDP": f"http://127.0.0.1:{CDP_PORT}/json/version",
        }
        if not is_production:
            health_urls["FRONTEND"] = f"{FRONTEND_URL}/login"
        # Backend can be temporarily slow under heavy batch operations.
        # Use gentler probing/restart thresholds to avoid restart storms.
        health_timeout_sec = {
            "PARSER": 2,
            "BACKEND": 15,
            "FRONTEND": 3,
            "CDP": 2,
        }
        health_fail_threshold = {
            "PARSER": 3,
            "BACKEND": 20,
            "FRONTEND": 3,
            "CDP": 3,
        }

        last_health_ts = 0.0

        while True:
            core_ready = _is_core_ready()
            for mp in list(procs):
                code = mp.popen.poll()
                if code is None:
                    continue
                svc = mp.name
                url = health_urls.get(svc)
                # If the tracked process exited but the service is actually healthy
                # (for example, after a fast handoff/rebind), adopt current listener
                # and avoid restart loops/false FAILED status.
                timeout = int(health_timeout_sec.get(svc, 2))
                if url and _http_ok(url, timeout_sec=timeout):
                    port = int(dashboard.get(svc, {}).get("port") or 0)
                    listener_pids = _pids_listening_on_port(port) if port > 0 else []
                    if svc in dashboard:
                        dashboard[svc]["status"] = "READY"
                        dashboard[svc]["last_error"] = ""
                        if listener_pids:
                            dashboard[svc]["pid"] = int(listener_pids[0])
                        _print_dashboard(dashboard)
                    try:
                        procs.remove(mp)
                    except Exception:
                        pass
                    continue
                if mp.name in dashboard:
                    dashboard[mp.name]["status"] = "FAILED"
                    if not str(dashboard[mp.name].get("last_error") or "").strip():
                        dashboard[mp.name]["last_error"] = f"exit code {code}"
                    _print_dashboard(dashboard)
                _restart_service(mp.name, f"exit code {code}")

            now = time.time()
            if now - last_health_ts >= 5.0:
                last_health_ts = now
                for svc, url in health_urls.items():
                    timeout = int(health_timeout_sec.get(svc, 2))
                    ok = _http_ok(url, timeout_sec=timeout)
                    if ok:
                        health_fail_streak[svc] = 0
                        if svc in dashboard and str(dashboard[svc].get("status")) not in {"READY", "SKIPPED"}:
                            dashboard[svc]["status"] = "READY"
                            dashboard[svc]["last_error"] = ""
                            _print_dashboard(dashboard)
                            continue
                        if svc in dashboard and str(dashboard[svc].get("last_error") or "").strip():
                            dashboard[svc]["last_error"] = ""
                            _print_dashboard(dashboard)
                        continue

                    health_fail_streak[svc] = int(health_fail_streak.get(svc) or 0) + 1
                    fail_threshold = int(health_fail_threshold.get(svc, 3))
                    if health_fail_streak[svc] >= fail_threshold:
                        health_fail_streak[svc] = 0

                        if svc == "CDP":
                            if not core_ready:
                                continue
                            # Give CDP time to boot before attempting any restart.
                            if cdp_last_launch_ts and (time.time() - cdp_last_launch_ts) < 30:
                                continue
                            # Never spawn a second browser if one is already running.
                            if chrome_proc is not None and chrome_proc.poll() is None:
                                dashboard["CDP"]["status"] = "STARTING"
                                dashboard["CDP"]["last_error"] = "cdp still starting; restart skipped"
                                _print_dashboard(dashboard)
                                continue
                            # If another process already owns the port, don't spawn more windows.
                            if _pids_listening_on_port(CDP_PORT) and chrome_proc is None:
                                dashboard["CDP"]["status"] = "FAILED"
                                dashboard["CDP"]["last_error"] = "cdp port in use; skipping restart"
                                _print_dashboard(dashboard)
                                continue
                            if cdp_launched_once and (os.environ.get("B2B_CDP_ALLOW_RESTART") or "").strip().lower() not in {"1", "true", "yes"}:
                                dashboard["CDP"]["status"] = "FAILED"
                                dashboard["CDP"]["last_error"] = "cdp restart disabled"
                                _print_dashboard(dashboard)
                                continue
                            if _rate_limited("CDP"):
                                continue
                            _bump_restart("CDP")
                            try:
                                if chrome_proc is not None:
                                    chrome_proc.terminate()
                            except Exception:
                                pass
                            chrome_proc = _start_chrome_cdp(
                                prefer="chrome",
                                profile_dir_override=cdp_profile_dir,
                                user_data_dir_override=cdp_user_data_dir,
                            )
                            if chrome_proc is not None and chrome_proc.pid:
                                dashboard["CDP"]["pid"] = int(chrome_proc.pid)
                                cdp_last_launch_ts = time.time()
                            dashboard["CDP"]["status"] = "STARTING"
                            dashboard["CDP"]["last_error"] = "health check failed"
                            _print_dashboard(dashboard)
                            continue

                        if svc == "TUNNEL":
                            # Tunnel health is checked by process liveness, not HTTP.
                            # If tunnel process exited, it will be caught in the process poll loop above.
                            continue

                        if svc in ("PARSER", "BACKEND", "FRONTEND"):
                            # Backend can transiently fail health probes during heavy bulk operations
                            # (for example, mass Checko enrichment). Do not restart it based solely
                            # on health probe failures; restart only on real process exit.
                            if svc == "BACKEND":
                                if svc in dashboard:
                                    dashboard[svc]["status"] = "STARTING"
                                    dashboard[svc]["last_error"] = "health check failed (restart suppressed)"
                                    _print_dashboard(dashboard)
                                continue

                            # Avoid restart storms: if service port is already owned, likely transient timeout.
                            # This is especially important for BACKEND during heavy bulk operations.
                            svc_port = int(dashboard.get(svc, {}).get("port") or 0)
                            if svc_port > 0:
                                owners = _pids_listening_on_port(svc_port)
                                if owners:
                                    if svc in dashboard:
                                        dashboard[svc]["status"] = "STARTING"
                                        dashboard[svc]["last_error"] = "health probe timeout; listener still alive"
                                        dashboard[svc]["pid"] = int(owners[0])
                                        _print_dashboard(dashboard)
                                    continue
                            _restart_service(svc, "health check failed")

            time.sleep(1)

    except KeyboardInterrupt:
        _log_system("Stopping...", level="info")
        return 0
    finally:
        for mp in reversed(procs):
            try:
                _taskkill_tree(mp.pid())
            except Exception:
                pass
        if chrome_proc is not None:
            try:
                chrome_proc.terminate()
            except Exception:
                pass
        # Kill any remaining ngrok processes started by this launcher
        if is_production:
            _taskkill_tree_by_name("ngrok.exe")


if __name__ == "__main__":
    raise SystemExit(main())
