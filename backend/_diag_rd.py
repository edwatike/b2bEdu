"""Quick diagnostic: check run_domains and task selection for run a430b883"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

async def main():
    from app.adapters.db.session import AsyncSessionLocal
    from sqlalchemy import text

    run_id = "a430b883-3124-4a61-bb88-7537837cea66"

    async with AsyncSessionLocal() as db:
        # 1. Check run_domains count
        r = await db.execute(text("SELECT COUNT(*) FROM run_domains WHERE run_id = :rid"), {"rid": run_id})
        cnt = r.scalar()
        print(f"run_domains count for {run_id}: {cnt}")

        # 2. Check domains_queue count
        r2 = await db.execute(text("SELECT COUNT(DISTINCT domain) FROM domains_queue WHERE parsing_run_id = :rid"), {"rid": run_id})
        dq_cnt = r2.scalar()
        print(f"domains_queue distinct domains: {dq_cnt}")

        # 3. Check moderator_tasks for request 912
        r3 = await db.execute(text("SELECT id, request_id, status, title FROM moderator_tasks WHERE request_id = 912"))
        row = r3.fetchone()
        if row:
            print(f"moderator_task: id={row[0]} request_id={row[1]} status={row[2]} title={row[3]}")
        else:
            print("No moderator_task for request_id=912")

        # 4. Check if eager population query would find this run
        r4 = await db.execute(text(
            "SELECT pr.run_id FROM parsing_runs pr "
            "JOIN moderator_tasks mt ON mt.request_id = pr.request_id "
            "WHERE mt.status NOT IN ('done','cancelled') "
            "AND pr.status = 'completed' "
            "AND EXISTS (SELECT 1 FROM domains_queue dq WHERE dq.parsing_run_id = pr.run_id) "
            "AND NOT EXISTS (SELECT 1 FROM run_domains rd WHERE rd.run_id = pr.run_id) "
            "ORDER BY pr.created_at DESC LIMIT 10"
        ))
        rows = r4.fetchall()
        print(f"Runs needing population: {[str(r[0]) for r in rows]}")

        # 5. If run_domains exist, show statuses
        if cnt > 0:
            r5 = await db.execute(text(
                "SELECT status, COUNT(*) FROM run_domains WHERE run_id = :rid GROUP BY status"
            ), {"rid": run_id})
            for row in r5.fetchall():
                print(f"  run_domains status={row[0]}: {row[1]}")

asyncio.run(main())
