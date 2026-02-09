"""Check E2E state for latest parsing run"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(__file__))

async def main():
    from app.adapters.db.session import AsyncSessionLocal
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        r = await db.execute(text(
            "SELECT run_id, request_id, status, "
            "process_log->'domain_parser_auto'->>'status' as dp_status "
            "FROM parsing_runs ORDER BY created_at DESC LIMIT 1"
        ))
        row = r.fetchone()
        print(f"Latest run: {row[0]} req={row[1]} status={row[2]} dp={row[3]}")

        run_id = str(row[0])
        req_id = int(row[1])

        r2 = await db.execute(text(
            "SELECT status, COUNT(*) FROM run_domains WHERE run_id = :rid GROUP BY status"
        ), {"rid": run_id})
        rows = r2.fetchall()
        if rows:
            for rr in rows:
                print(f"  run_domains: {rr[0]}={rr[1]}")
        else:
            print("  No run_domains yet")

        r3 = await db.execute(text(
            "SELECT id, status, title FROM moderator_tasks WHERE request_id = :rid"
        ), {"rid": req_id})
        mt = r3.fetchone()
        if mt:
            print(f"  moderator_task: id={mt[0]} status={mt[1]} title={mt[2]}")
        else:
            print("  No moderator_task")

        r4 = await db.execute(text(
            "SELECT COUNT(DISTINCT domain) FROM domains_queue WHERE parsing_run_id = :rid"
        ), {"rid": run_id})
        print(f"  domains_queue count: {r4.scalar()}")

asyncio.run(main())
