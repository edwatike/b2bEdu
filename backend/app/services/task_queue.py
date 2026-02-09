import os
import tempfile
import logging
from typing import Optional

logger = logging.getLogger(__name__)

QUEUE_NAME = os.getenv("RQ_QUEUE_NAME", "b2b")

_redis = None
_queue = None


def _redis_data_dir() -> str:
    override = os.getenv("RQ_REDIS_DIR")
    if override:
        return override
    return os.path.join(tempfile.gettempdir(), "b2b-redis")


def get_redis_connection():
    """Return embedded Redis connection (redislite) when enabled."""
    global _redis
    if _redis is not None:
        return _redis

    if os.getenv("RQ_ENABLED", "0") != "1":
        return None

    try:
        from redislite import Redis  # type: ignore

        data_dir = _redis_data_dir()
        os.makedirs(data_dir, exist_ok=True)
        _redis = Redis(data_dir)
        return _redis
    except Exception as exc:
        logger.warning("Failed to initialize redislite: %s", exc)
        return None


def get_queue():
    """Return RQ queue when enabled; otherwise None."""
    global _queue
    if _queue is not None:
        return _queue

    if os.getenv("RQ_ENABLED", "0") != "1":
        return None

    redis_conn = get_redis_connection()
    if not redis_conn:
        return None

    try:
        from rq import Queue  # type: ignore

        _queue = Queue(QUEUE_NAME, connection=redis_conn)
        return _queue
    except Exception as exc:
        logger.warning("Failed to initialize RQ queue: %s", exc)
        return None


def enqueue(func_path: str, *args, **kwargs):
    """Enqueue a job by import path. Falls back to None if queue disabled."""
    q = get_queue()
    if not q:
        return None
    return q.enqueue(func_path, *args, **kwargs)
