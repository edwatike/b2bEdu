import asyncio, json, sys, os
sys.path.insert(0, os.path.dirname(__file__))

async def main():
    from app.adapters.db.session import AsyncSessionLocal
    from sqlalchemy import text
    
    async with AsyncSessionLocal() as db:
        # Check the specific run
        r = await db.execute(text("""
            SELECT pr.run_id, pr.status, 
                   pr.process_log->'domain_parser_auto'->>'status' as dp_status,
                   pr.process_log->'domain_parser_auto'->>'parserRunId' as dp_run_id
            FROM parsing_runs pr 
            WHERE pr.run_id = '23574641-8e53-47ee-8193-db6f8ceff71a'
        """))
        row = r.fetchone()
        if row:
            print(f"RUN: status={row[1]}, dp_status={row[2]}, dp_run_id={row[3]}")
        
        # Count domains in queue for this run
        r2 = await db.execute(text("""
            SELECT COUNT(*) FROM domains_queue WHERE parsing_run_id = '23574641-8e53-47ee-8193-db6f8ceff71a'
        """))
        print(f"Domains in queue: {r2.scalar()}")
        
        # Check which domains are NOT in suppliers and NOT in moderation
        r3 = await db.execute(text("""
            SELECT dq.domain 
            FROM domains_queue dq
            WHERE dq.parsing_run_id = '23574641-8e53-47ee-8193-db6f8ceff71a'
            AND NOT EXISTS (SELECT 1 FROM moderator_suppliers ms WHERE ms.domain = dq.domain)
            AND NOT EXISTS (SELECT 1 FROM supplier_domains sd WHERE sd.domain = dq.domain)
            AND NOT EXISTS (SELECT 1 FROM domain_moderation dm WHERE dm.domain = dq.domain)
        """))
        unprocessed = [str(x[0]) for x in r3.fetchall()]
        print(f"Unprocessed domains: {len(unprocessed)} -> {unprocessed}")
        
        # Check how many runs are queued
        r4 = await db.execute(text("""
            SELECT pr.run_id, 
                   pr.process_log->'domain_parser_auto'->>'status' as dp_status,
                   pr.created_at
            FROM parsing_runs pr 
            WHERE COALESCE(pr.process_log->'domain_parser_auto'->>'status','') = 'queued'
            ORDER BY pr.created_at ASC
        """))
        queued = r4.fetchall()
        print(f"Queued runs: {len(queued)}")
        for q in queued[:5]:
            print(f"  run_id={q[0]}, dp_status={q[1]}, created={q[2]}")
        
        # Check total unprocessed domains across ALL runs
        r5 = await db.execute(text("""
            SELECT COUNT(DISTINCT dq.domain) 
            FROM domains_queue dq
            WHERE NOT EXISTS (SELECT 1 FROM moderator_suppliers ms WHERE ms.domain = dq.domain)
            AND NOT EXISTS (SELECT 1 FROM supplier_domains sd WHERE sd.domain = dq.domain)
            AND NOT EXISTS (SELECT 1 FROM domain_moderation dm WHERE dm.domain = dq.domain)
        """))
        print(f"Total unprocessed domains across all runs: {r5.scalar()}")
        
        # Check _worker_paused state via API
        print("\n--- Worker state ---")
        r6 = await db.execute(text("""
            SELECT pr.run_id, 
                   pr.process_log->'domain_parser_auto'->>'status' as dp_status
            FROM parsing_runs pr 
            WHERE COALESCE(pr.process_log->'domain_parser_auto'->>'status','') IN ('running')
        """))
        running = r6.fetchall()
        print(f"Running runs: {len(running)}")
        for rr in running:
            print(f"  run_id={rr[0]}, dp_status={rr[1]}")

asyncio.run(main())
