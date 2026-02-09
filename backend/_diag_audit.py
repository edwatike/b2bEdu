"""QA Audit diagnostic: check run_domains, tasks, mc.ru for current-task block"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(__file__))

async def main():
    from app.adapters.db.session import AsyncSessionLocal
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        # 1. All active moderator_tasks
        r1 = await db.execute(text(
            "SELECT mt.id, mt.request_id, mt.status, mt.title, mt.created_at "
            "FROM moderator_tasks mt "
            "WHERE mt.status NOT IN ('done','cancelled') "
            "ORDER BY mt.created_at ASC LIMIT 15"
        ))
        tasks = r1.fetchall()
        print(f"=== Active moderator_tasks: {len(tasks)} ===")
        for t in tasks:
            ttl = (t[3] or "")[:50]
            print(f"  task_id={t[0]} req={t[1]} status={t[2]} title={ttl}")

        # 2. For first 5 tasks, check parsing_runs and run_domains
        for t in tasks[:5]:
            req_id = t[1]
            r2 = await db.execute(text(
                "SELECT pr.run_id, pr.status FROM parsing_runs pr "
                "WHERE pr.request_id = :rid ORDER BY pr.created_at ASC"
            ), {"rid": req_id})
            runs = r2.fetchall()
            for run in runs:
                rid = str(run[0])
                r3 = await db.execute(text(
                    "SELECT status, COUNT(*) FROM run_domains "
                    "WHERE run_id = :rid GROUP BY status"
                ), {"rid": rid})
                rd_stats = {str(row[0]): int(row[1]) for row in r3.fetchall()}
                r4 = await db.execute(text(
                    "SELECT COUNT(DISTINCT domain) FROM domains_queue "
                    "WHERE parsing_run_id = :rid"
                ), {"rid": rid})
                dq_cnt = int(r4.scalar() or 0)
                print(f"  run={rid[:12]}.. pr_status={run[1]} dq={dq_cnt} rd={rd_stats}")

        # 3. Runs needing population (no run_domains yet)
        r5 = await db.execute(text(
            "SELECT pr.run_id FROM parsing_runs pr "
            "JOIN moderator_tasks mt ON mt.request_id = pr.request_id "
            "WHERE mt.status NOT IN ('done','cancelled') "
            "AND pr.status = 'completed' "
            "AND EXISTS (SELECT 1 FROM domains_queue dq WHERE dq.parsing_run_id = pr.run_id) "
            "AND NOT EXISTS (SELECT 1 FROM run_domains rd WHERE rd.run_id = pr.run_id) "
            "ORDER BY pr.created_at DESC LIMIT 10"
        ))
        need_pop = [str(r[0]) for r in r5.fetchall()]
        print(f"=== Runs needing population: {len(need_pop)} runs ===")
        for rp in need_pop[:5]:
            print(f"  {rp}")

        # 4. Query (c) from current_task - tasks with pending/processing run_domains
        r6 = await db.execute(text(
            "SELECT mt.id, mt.request_id, mt.title FROM moderator_tasks mt "
            "WHERE mt.status NOT IN ('done','cancelled') "
            "AND EXISTS (SELECT 1 FROM parsing_runs pr WHERE pr.request_id = mt.request_id "
            "  AND EXISTS (SELECT 1 FROM run_domains rd WHERE rd.run_id = pr.run_id "
            "    AND (rd.status IN ('pending','processing') OR rd.status IS NULL OR rd.status = ''))) "
            "ORDER BY mt.created_at ASC LIMIT 5"
        ))
        pending_tasks = r6.fetchall()
        print(f"=== Tasks with pending/processing run_domains: {len(pending_tasks)} ===")
        for pt in pending_tasks:
            print(f"  task_id={pt[0]} req={pt[1]} title={(pt[2] or '')[:50]}")

        # 5. mc.ru check
        r7 = await db.execute(text(
            "SELECT rd.run_id, rd.domain, rd.status, rd.global_requires_moderation, "
            "rd.checko_ok, rd.supplier_id "
            "FROM run_domains rd WHERE rd.domain = 'mc.ru' LIMIT 5"
        ))
        mc_rows = r7.fetchall()
        print(f"=== mc.ru in run_domains: {len(mc_rows)} ===")
        for row in mc_rows:
            print(f"  run={str(row[0])[:12]}.. status={row[2]} grm={row[3]} checko={row[4]} sid={row[5]}")

        # 6. Global mc.ru status
        r8 = await db.execute(text(
            "SELECT ms.id, ms.domain, ms.type, ms.data_status, ms.inn "
            "FROM moderator_suppliers ms "
            "LEFT JOIN supplier_domains sd ON sd.supplier_id = ms.id "
            "WHERE lower(COALESCE(sd.domain, ms.domain, '')) LIKE '%mc.ru%' LIMIT 5"
        ))
        mc_sup = r8.fetchall()
        print(f"=== mc.ru in moderator_suppliers: {len(mc_sup)} ===")
        for row in mc_sup:
            print(f"  sid={row[0]} domain={row[1]} type={row[2]} data_status={row[3]} inn={row[4]}")

        r9 = await db.execute(text(
            "SELECT domain, reason FROM domain_moderation "
            "WHERE lower(domain) LIKE '%mc.ru%' LIMIT 5"
        ))
        mc_mod = r9.fetchall()
        print(f"=== mc.ru in domain_moderation: {len(mc_mod)} ===")
        for row in mc_mod:
            print(f"  domain={row[0]} reason={row[1]}")

        # 7. Total run_domains stats
        r10 = await db.execute(text(
            "SELECT status, COUNT(*) FROM run_domains GROUP BY status ORDER BY COUNT(*) DESC"
        ))
        print(f"=== Total run_domains by status ===")
        for row in r10.fetchall():
            print(f"  {row[0]}: {row[1]}")

asyncio.run(main())
