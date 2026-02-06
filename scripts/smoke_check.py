import os
import sys
import urllib.request
import urllib.error
from typing import Iterable


def _env(name: str, default: str) -> str:
    return (os.getenv(name) or default).strip()


def _check(url: str, ok_status: Iterable[int]) -> tuple[bool, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "b2b-smoke-check"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.getcode()
            body = resp.read(200).decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        status = e.code
        body = e.read(200).decode("utf-8", errors="ignore") if e.fp else ""
    except Exception as exc:
        return False, f"error: {type(exc).__name__}: {exc}"

    if status in ok_status:
        return True, f"status={status}"
    return False, f"status={status} body={body[:120]!r}"


def main() -> int:
    backend = _env("BACKEND_URL", "http://127.0.0.1:8000")
    parser = _env("PARSER_SERVICE_URL", "http://127.0.0.1:9000")
    frontend = _env("FRONTEND_URL", "http://127.0.0.1:3000")

    checks = [
        ("backend.health", f"{backend}/health", {200}),
        ("parser.health", f"{parser}/health", {200}),
        ("frontend.login", f"{frontend}/login", {200, 302, 307}),
        ("frontend.auth_status", f"{frontend}/api/auth/status", {200}),
    ]

    ok_all = True
    results = []
    for name, url, ok_status in checks:
        ok, detail = _check(url, ok_status)
        ok_all = ok_all and ok
        results.append({"name": name, "url": url, "ok": ok, "detail": detail})

    print("B2B smoke check")
    for r in results:
        flag = "PASS" if r["ok"] else "FAIL"
        print(f"[{flag}] {r['name']} -> {r['url']} ({r['detail']})")

    if not ok_all:
        print("One or more checks failed.")
        return 1

    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
