"""Fix request 913: add moderator_task + delete stale run_domains so they get re-populated"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(__file__))

async def main():
    from app.adapters.db.session import AsyncSessionLocal
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        # 1. Check if moderator_task exists for request 913
        r = await db.execute(text("SELECT id FROM moderator_tasks WHERE request_id = 913"))
        if not r.fetchone():
            await db.execute(text(
                "INSERT INTO moderator_tasks (request_id, created_by, title, status, source, depth) "
                "VALUES (913, 1, 'поставщики пенопласта оптом', 'running', 'both', 2)"
            ))
            print("Created moderator_task for request 913")
        else:
            print("moderator_task already exists for request 913")

        # 2. Delete stale run_domains for the latest run so they get re-populated
        r2 = await db.execute(text(
            "SELECT run_id FROM parsing_runs WHERE request_id = 913 ORDER BY created_at DESC LIMIT 1"
        ))
        row = r2.fetchone()
        if row:
            run_id = str(row[0])
            await db.execute(text("DELETE FROM run_domains WHERE run_id = :rid"), {"rid": run_id})
            print(f"Deleted run_domains for run {run_id}")

            # 3. Reset domain_parser_auto status to 'queued' so enrichment re-runs
            r3 = await db.execute(text(
                "SELECT process_log FROM parsing_runs WHERE run_id = :rid"
            ), {"rid": run_id})
            pl_row = r3.fetchone()
            if pl_row:
                import json
                pl = pl_row[0]
                if isinstance(pl, str):
                    pl = json.loads(pl)
                if not isinstance(pl, dict):
                    pl = {}
                import uuid
                from datetime import datetime
                pl["domain_parser_auto"] = {
                    "status": "queued",
                    "parserRunId": f"auto_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}",
                    "mode": "recovery_manual",
                    "queuedAt": datetime.utcnow().isoformat(),
                }
                await db.execute(
                    text("UPDATE parsing_runs SET process_log = CAST(:pl AS jsonb) WHERE run_id = :rid"),
                    {"pl": json.dumps(pl, ensure_ascii=False), "rid": run_id},
                )
                print(f"Reset domain_parser_auto to 'queued' for run {run_id}")

        await db.commit()
        print("Done!")

asyncio.run(main())
