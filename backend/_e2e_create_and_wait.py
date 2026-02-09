"""Create a new cabinet-like request with 2 keys, wait for parsing+auto enrichment, then print report.

This avoids UI (Playwright is unavailable).

Usage: python _e2e_create_and_wait.py
"""

import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))


async def main() -> None:
    from sqlalchemy import text
    from app.adapters.db.session import AsyncSessionLocal
    from app.usecases import start_parsing

    keys = [
        "минеральная вата оптом купить",
        "экструдированный пенополистирол купить",
    ]

    title = f"E2E AUTO 2keys {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"

    async with AsyncSessionLocal() as db:
        # 1) Create parsing_request
        req_res = await db.execute(
            text(
                "INSERT INTO parsing_requests (title, raw_keys_json, depth, source, created_by) "
                "VALUES (:title, :raw, :depth, :source, :uid) RETURNING id"
            ),
            {
                "title": title,
                "raw": __import__("json").dumps(keys, ensure_ascii=False),
                "depth": 2,
                "source": "both",
                "uid": 6,
            },
        )
        request_id = int(req_res.scalar())

        # 2) Create moderator_task (cabinet submit behavior)
        await db.execute(
            text(
                "INSERT INTO moderator_tasks (request_id, created_by, title, status, source, depth) "
                "VALUES (:request_id, :created_by, :title, :status, :source, :depth)"
            ),
            {
                "request_id": request_id,
                "created_by": 6,
                "title": title,
                "status": "new",
                "source": "both",
                "depth": 2,
            },
        )
        await db.commit()

    # 3) Start parsing for each key (two runs attached to request)
    run_ids: list[str] = []
    async with AsyncSessionLocal() as db:
        for k in keys:
            res = await start_parsing.execute(
                db=db,
                keyword=str(k),
                depth=2,
                source="both",
                background_tasks=None,
                request_id=int(request_id),
            )
            run_ids.append(str(res.get("run_id")))
        await db.commit()

    print(f"Created request_id={request_id} title={title}")
    print(f"Run IDs: {run_ids}")

    # 4) Wait for parsing_runs completed
    async def _all_runs_completed() -> tuple[bool, list[tuple[str, str, str]]]:
        async with AsyncSessionLocal() as db:
            r = await db.execute(
                text(
                    "SELECT run_id, status, COALESCE(process_log->'domain_parser_auto'->>'status','') "
                    "FROM parsing_runs WHERE request_id = :rid ORDER BY created_at ASC"
                ),
                {"rid": request_id},
            )
            rows = [(str(x[0]), str(x[1]), str(x[2] or "")) for x in (r.fetchall() or [])]
            ok = bool(rows) and all(st == "completed" for (_rid, st, _dp) in rows)
            return ok, rows

    async def _all_runs_enriched() -> tuple[bool, list[tuple[str, str, str]]]:
        async with AsyncSessionLocal() as db:
            r = await db.execute(
                text(
                    "SELECT run_id, status, COALESCE(process_log->'domain_parser_auto'->>'status','') "
                    "FROM parsing_runs WHERE request_id = :rid ORDER BY created_at ASC"
                ),
                {"rid": request_id},
            )
            rows = [(str(x[0]), str(x[1]), str(x[2] or "")) for x in (r.fetchall() or [])]
            ok = bool(rows) and all(dp in ("completed", "") for (_rid, _st, dp) in rows)
            return ok, rows

    # wait up to ~8 minutes
    for i in range(1, 97):
        ok, rows = await _all_runs_completed()
        if ok:
            print(f"Parsing completed after {i*5}s")
            break
        if i % 6 == 0:
            print("Parsing status:")
            for rid, st, dp in rows:
                print(f"  {rid}: status={st} dp={dp}")
        await asyncio.sleep(5)
    else:
        print("Timeout waiting for parsing completion")

    # 5) Wait for run_domains to be populated (worker + current_task populate)
    # We consider it ready when run_domains exist for all runs.
    async def _run_domains_ready() -> tuple[bool, list[tuple[str, int]]]:
        async with AsyncSessionLocal() as db:
            out = []
            for rid in run_ids:
                r = await db.execute(text("SELECT COUNT(*) FROM run_domains WHERE run_id = :rid"), {"rid": rid})
                out.append((rid, int(r.scalar() or 0)))
            ok = all(cnt > 0 for (_rid, cnt) in out)
            return ok, out

    for i in range(1, 97):
        ok, counts = await _run_domains_ready()
        if ok:
            print(f"run_domains populated after {i*5}s")
            break
        if i % 6 == 0:
            print("run_domains counts:")
            for rid, cnt in counts:
                print(f"  {rid}: {cnt}")
        await asyncio.sleep(5)
    else:
        print("Timeout waiting for run_domains population")

    # 6) Print report using existing helper
    import subprocess
    subprocess.run([
        sys.executable,
        os.path.join(os.path.dirname(__file__), "_report_request.py"),
        str(request_id),
    ], check=False)


if __name__ == "__main__":
    asyncio.run(main())
