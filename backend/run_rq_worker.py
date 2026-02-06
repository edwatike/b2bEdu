import os
import sys

from app.services.task_queue import get_redis_connection, QUEUE_NAME


def main() -> int:
    if os.getenv("RQ_ENABLED", "0") != "1":
        print("RQ is disabled. Set RQ_ENABLED=1 to run worker.")
        return 1

    redis_conn = get_redis_connection()
    if not redis_conn:
        print("Redis connection is not available.")
        return 1

    try:
        from rq import Worker, Queue, Connection  # type: ignore
    except Exception as exc:
        print(f"RQ import failed: {exc}")
        return 1

    with Connection(redis_conn):
        worker = Worker([Queue(QUEUE_NAME)])
        worker.work(with_scheduler=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
