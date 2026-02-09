"""Centralized rate limiting configuration.

Uses slowapi (backed by limits library) with in-memory storage.
All rate-limit constants are defined here so they can be tuned in one place.

For endpoints where adding a `request: Request` parameter would conflict with
existing body parameter names (e.g. mail.py), use `PathRateLimitMiddleware`
instead of per-endpoint `@limiter.limit()` decorators.
"""
import time
import logging
from collections import defaultdict

from fastapi import status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

_logger = logging.getLogger(__name__)

# Single Limiter instance shared across the application.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],          # no blanket limit; applied per-route
    storage_uri="memory://",    # in-process; swap to redis:// in production
)

# ── Rate-limit strings (slowapi / limits format) ────────────────────────
AUTH_LIMIT = "10/minute"          # login / OTP / status
PARSING_START_LIMIT = "5/minute"  # heavy: spawns parser service calls
DOMAIN_PARSER_LIMIT = "3/minute"  # heavy: batch domain extraction
MAIL_LIMIT = "10/minute"          # IMAP/SMTP operations
DEFAULT_WRITE_LIMIT = "30/minute" # POST/PUT/DELETE on normal CRUD


# ── Path-based rate limiter middleware ───────────────────────────────────
# Used for routers where adding `request: Request` would conflict with body
# parameter names (mail.py).

class PathRateLimitMiddleware(BaseHTTPMiddleware):
    """Simple token-bucket rate limiter keyed by (client_ip, path_prefix).

    Parameters
    ----------
    rules : list[tuple[str, int, int]]
        Each rule is (path_prefix, max_requests, window_seconds).
        Example: [("/api/mail/", 10, 60)]  # 10 req/min for mail endpoints
    """

    def __init__(self, app, rules: list[tuple[str, int, int]] | None = None):
        super().__init__(app)
        self.rules: list[tuple[str, int, int]] = rules or []
        # buckets: {(ip, prefix): [timestamps]}
        self._buckets: dict[tuple[str, str], list[float]] = defaultdict(list)

    async def dispatch(self, request, call_next):
        path = request.url.path
        client_ip = get_remote_address(request)

        for prefix, max_req, window in self.rules:
            if not path.startswith(prefix):
                continue

            key = (client_ip, prefix)
            now = time.monotonic()
            # Prune expired timestamps
            bucket = [t for t in self._buckets[key] if now - t < window]
            if len(bucket) >= max_req:
                _logger.warning(
                    "Rate limit exceeded: %s %s from %s (%d/%d in %ds)",
                    request.method, path, client_ip, len(bucket), max_req, window,
                )
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "rate_limit_exceeded",
                        "detail": f"Rate limit exceeded: {max_req} requests per {window}s",
                        "retry_after": window,
                    },
                    headers={"Retry-After": str(window)},
                )
            bucket.append(now)
            self._buckets[key] = bucket
            break  # first matching rule wins

        return await call_next(request)
