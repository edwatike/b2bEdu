import os
import sys
import time
import threading
import subprocess
import argparse
from dataclasses import dataclass
from typing import Optional


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
    candidate = os.path.join(service_dir, "venv", "Scripts", "python.exe")
    if os.path.exists(candidate):
        return candidate
    return sys.executable


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
            _RICH_CONSOLE.print(msg)
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
        out.write(f"[{ts}] [{prefix}] {color}{line}{reset}\n")
        out.flush()


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
    signature = "|".join(
        [
            ",".join(
                [
                    name,
                    str(state.get(name, {}).get("status", "")),
                    str(state.get(name, {}).get("last_error", "")),
                ]
            )
            for name in ("PARSER", "BACKEND", "FRONTEND", "CDP")
        ]
    )
    # If status/last_error didn't change, do not re-print dashboard.
    if signature == _LAST_DASH_SIGNATURE:
        return
    _LAST_DASH_SIGNATURE = signature
    _LAST_DASH_PRINT_TS = time.time()
    if _RICH_CONSOLE is not None and Table is not None:
        table = Table(show_header=True, header_style="bold")
        table.add_column("Service", no_wrap=True)
        table.add_column("Port", justify="right", no_wrap=True)
        table.add_column("PID", justify="right", no_wrap=True)
        table.add_column("Status", no_wrap=True)
        table.add_column("URL")
        table.add_column("LastError")

        for name in ("PARSER", "BACKEND", "FRONTEND", "CDP"):
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
        return

    lines: list[str] = []
    lines.append("B2B Launcher")
    for name in ("PARSER", "BACKEND", "FRONTEND", "CDP"):
        row = state.get(name, {})
        lines.append(
            f"- {name}: port={row.get('port','')} pid={row.get('pid','')} status={row.get('status','')} url={row.get('url','')} last_error={row.get('last_error','')}"
        )
    with _PRINT_LOCK:
        for l in lines:
            sys.stdout.write(l + "\n")
        sys.stdout.flush()


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
    except Exception:
        pass

    # Fallback: parse netstat output.
    try:
        r = subprocess.run(
            ["cmd", "/c", f"netstat -ano | findstr :{port}"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
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
        for pid in _pids_listening_on_port(port):
            _log_system(f"Port {port} is in use by PID {pid}. Stopping it...", level="warn")
            _taskkill_tree(pid)


def _wait_http_ready(url: str, timeout_sec: int) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            cmd = (
                "try { "
                f"$r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 '{url}'; "
                "if ($null -ne $r -and $r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 } else { exit 1 } "
                "} catch { exit 1 }"
            )
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if r.returncode == 0:
                return True
        except Exception:
            pass
        time.sleep(1)
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


def _start_chrome_cdp() -> Optional[subprocess.Popen]:
    comet = _find_comet_exe()
    chrome = _find_chrome_exe()

    browser = comet or chrome
    if not browser:
        _log_system("Comet/Chrome not found. Skipping CDP launch.", level="warn")
        return None

    if comet:
        _log_system(f"Launching Comet with CDP on port {CDP_PORT}: {comet}", level="info")
    else:
        _log_system(f"Comet not found, falling back to Chrome with CDP on port {CDP_PORT}: {chrome}", level="warn")

    user_data_dir = _abs("TEMP", "comet-profile")
    os.makedirs(user_data_dir, exist_ok=True)

    args = [
        browser,
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={user_data_dir}",
        "--new-window",
        FRONTEND_URL,
    ]

    try:
        return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        _log_system(f"Failed to start Chrome: {type(e).__name__}: {e}", level="warn")
        return None


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--repo-root", dest="repo_root", default=None)
    args, _ = parser.parse_known_args()
    if args.repo_root:
        os.environ["B2B_REPO_ROOT"] = args.repo_root

    root = _repo_root()

    parser_dir = _abs("parser_service")
    backend_dir = _abs("backend")
    frontend_dir = _abs("frontend", "moderator-dashboard-ui")

    procs: list[ManagedProcess] = []
    chrome_proc: Optional[subprocess.Popen] = None

    dashboard: dict[str, dict[str, object]] = {
        "PARSER": {"port": PARSER_PORT, "pid": "", "status": "STARTING", "url": f"http://127.0.0.1:{PARSER_PORT}", "last_error": ""},
        "BACKEND": {"port": BACKEND_PORT, "pid": "", "status": "STARTING", "url": f"http://127.0.0.1:{BACKEND_PORT}", "last_error": ""},
        "FRONTEND": {"port": FRONTEND_PORT, "pid": "", "status": "STARTING", "url": FRONTEND_URL, "last_error": ""},
        "CDP": {"port": CDP_PORT, "pid": "", "status": "STARTING", "url": f"http://127.0.0.1:{CDP_PORT}", "last_error": ""},
    }

    def on_line(service: str, line: str, is_err: bool) -> None:
        lvl = _classify_level(line, is_err)
        if lvl not in ("error", "warn"):
            return
        if service not in dashboard:
            return
        short = _short_error(line)
        with _DASH_LOCK:
            dashboard[service]["last_error"] = short

    try:
        _free_ports([FRONTEND_PORT, BACKEND_PORT, PARSER_PORT, CDP_PORT])
        _print_dashboard(dashboard)

        parser_py = _venv_python(parser_dir)
        backend_py = _venv_python(backend_dir)

        parser_env = {**os.environ}
        parser_env["CHROME_CDP_URL"] = f"http://127.0.0.1:{CDP_PORT}"
        parser_env["USE_CHROME_CDP"] = "true"
        procs.append(
            _start_process(
                name="PARSER",
                args=[parser_py, "-u", _abs("parser_service", "run_api.py")],
                cwd=parser_dir,
                env=parser_env,
                on_line=on_line,
            )
        )
        dashboard["PARSER"]["pid"] = procs[-1].pid()
        _print_dashboard(dashboard)

        time.sleep(1)
        procs.append(
            _start_process(
                name="BACKEND",
                args=[backend_py, "-u", _abs("backend", "run_api.py")],
                cwd=backend_dir,
                env={**os.environ},
                on_line=on_line,
            )
        )
        dashboard["BACKEND"]["pid"] = procs[-1].pid()
        _print_dashboard(dashboard)

        fe_env = {**os.environ}
        fe_env["NODE_OPTIONS"] = "--max-old-space-size=2048"
        fe_env["NEXT_TELEMETRY_DISABLED"] = "1"
        fe_env["NEXT_PUBLIC_API_URL"] = f"http://127.0.0.1:{BACKEND_PORT}"
        fe_env["NEXT_PUBLIC_PARSER_URL"] = f"http://127.0.0.1:{PARSER_PORT}"
        fe_env["PORT"] = str(FRONTEND_PORT)

        procs.append(
            _start_process(
                name="FRONTEND",
                args=["cmd", "/c", f"npm run dev -- -p {FRONTEND_PORT}"],
                cwd=frontend_dir,
                env=fe_env,
                on_line=on_line,
            )
        )
        dashboard["FRONTEND"]["pid"] = procs[-1].pid()
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

        if _wait_http_ready(f"{FRONTEND_URL}/login", 120):
            dashboard["FRONTEND"]["status"] = "READY"
        else:
            dashboard["FRONTEND"]["status"] = "FAILED"
            dashboard["FRONTEND"]["last_error"] = "login page timeout"
        _print_dashboard(dashboard)

        core_ready = (
            str(dashboard["PARSER"].get("status")) == "READY"
            and str(dashboard["BACKEND"].get("status")) == "READY"
            and str(dashboard["FRONTEND"].get("status")) == "READY"
        )

        if core_ready:
            chrome_proc = _start_chrome_cdp()
            if chrome_proc is not None and chrome_proc.pid:
                dashboard["CDP"]["pid"] = int(chrome_proc.pid)
            if _wait_http_ready(f"http://127.0.0.1:{CDP_PORT}/json/version", 30):
                dashboard["CDP"]["status"] = "READY"
            else:
                dashboard["CDP"]["status"] = "FAILED"
                dashboard["CDP"]["last_error"] = "cdp /json/version timeout"
        else:
            dashboard["CDP"]["status"] = "SKIPPED"
            dashboard["CDP"]["last_error"] = "waiting for core services READY"

        _print_dashboard(dashboard)

        while True:
            for mp in procs:
                code = mp.popen.poll()
                if code is not None:
                    _log_system(f"{mp.name} exited with code {code}", level="error")
                    if mp.name in dashboard:
                        dashboard[mp.name]["status"] = "FAILED"
                        if not str(dashboard[mp.name].get("last_error") or "").strip():
                            dashboard[mp.name]["last_error"] = f"exit code {code}"
                        _print_dashboard(dashboard)
                    _pause_if_frozen(int(code or 1))
                    return int(code or 1)
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


if __name__ == "__main__":
    raise SystemExit(main())
