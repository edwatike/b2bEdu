"""Report pipeline stats for a request_id.
Outputs:
- runs
- total unique domains (root normalized)
- run_domains status counts (aggregated)
- suppliers visible in cabinet (uses cabinet router state builder)

Usage: python _report_request.py <request_id>
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


async def _get_cabinet_suppliers_count(request_id: int) -> int:
    from app.adapters.db.session import AsyncSessionLocal
    from app.transport.routers.cabinet import _ensure_request_suppliers_loaded, _request_suppliers_state

    async with AsyncSessionLocal() as db:
        await _ensure_request_suppliers_loaded(db=db, request_id=int(request_id))
        supplier_map = _request_suppliers_state.get(int(request_id), {})
        return len(list(supplier_map.values()))


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python _report_request.py <request_id>")
        raise SystemExit(2)

    request_id = int(sys.argv[1])

    from sqlalchemy import text
    from app.adapters.db.session import AsyncSessionLocal
    from app.utils.domain import normalize_domain_root

    async with AsyncSessionLocal() as db:
        req_res = await db.execute(
            text("SELECT id, title, created_by, created_at FROM parsing_requests WHERE id = :id"),
            {"id": request_id},
        )
        req = req_res.fetchone()
        if not req:
            print(f"Request {request_id} not found")
            return

        print(f"Request: id={req[0]} title={req[1]} created_by={req[2]} created_at={req[3]}")

        mt_res = await db.execute(
            text("SELECT id, status, title, created_at FROM moderator_tasks WHERE request_id = :rid ORDER BY id DESC"),
            {"rid": request_id},
        )
        mts = mt_res.fetchall() or []
        if mts:
            for mt in mts:
                print(f"ModeratorTask: id={mt[0]} status={mt[1]} title={mt[2]} created_at={mt[3]}")
        else:
            print("ModeratorTask: NONE")

        runs_res = await db.execute(
            text(
                "SELECT run_id, status, created_at, COALESCE(process_log->'domain_parser_auto'->>'status','') AS dp_status "
                "FROM parsing_runs WHERE request_id = :rid ORDER BY created_at ASC"
            ),
            {"rid": request_id},
        )
        runs = runs_res.fetchall() or []
        print(f"Runs: {len(runs)}")
        run_ids = []
        for r in runs:
            run_id = str(r[0])
            run_ids.append(run_id)
            print(f"  run_id={run_id} status={r[1]} created_at={r[2]} domain_parser_auto={r[3]}")

        if not run_ids:
            print("No runs -> nothing to report")
            return

        dq_res = await db.execute(
            text(
                "SELECT DISTINCT domain FROM domains_queue WHERE parsing_run_id = ANY(:run_ids) ORDER BY domain ASC"
            ),
            {"run_ids": list(run_ids)},
        )
        dq_domains = [str(x[0]) for x in (dq_res.fetchall() or []) if x and x[0]]
        uniq_root = sorted({normalize_domain_root(d) for d in dq_domains if d})
        uniq_root = [d for d in uniq_root if d]
        print(f"DomainsQueue: distinct_raw={len(dq_domains)} distinct_root={len(uniq_root)}")

        # run_domains aggregated status counts
        rd_res = await db.execute(
            text(
                "SELECT status, COUNT(*) FROM run_domains "
                "WHERE run_id = ANY(:run_ids) GROUP BY status ORDER BY status"
            ),
            {"run_ids": list(run_ids)},
        )
        rd_rows = rd_res.fetchall() or []
        if rd_rows:
            print("RunDomains statuses (aggregated across runs):")
            for rr in rd_rows:
                print(f"  {rr[0]} = {rr[1]}")
        else:
            print("RunDomains: NONE")

    suppliers_count = await _get_cabinet_suppliers_count(request_id)
    print(f"Cabinet suppliers visible: {suppliers_count}")


if __name__ == "__main__":
    asyncio.run(main())
