"""Diagnose why cabinet shows 0 suppliers for request 912"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(__file__))

async def main():
    from app.adapters.db.session import AsyncSessionLocal
    from sqlalchemy import text

    run_id = "a430b883-3124-4a61-bb88-7537837cea66"

    async with AsyncSessionLocal() as db:
        # 1. Show run_domains with supplier/reseller status
        r = await db.execute(text(
            "SELECT domain, status, supplier_id FROM run_domains "
            "WHERE run_id = :rid AND status IN ('supplier','reseller') ORDER BY id"
        ), {"rid": run_id})
        print("=== run_domains (supplier/reseller) ===")
        sup_ids = []
        for row in r.fetchall():
            print(f"  {row[0]} -> {row[1]} (supplier_id={row[2]})")
            if row[2]: sup_ids.append(int(row[2]))

        # 2. Show domains_queue domains for this run
        r2 = await db.execute(text(
            "SELECT DISTINCT domain FROM domains_queue WHERE parsing_run_id = :rid ORDER BY domain"
        ), {"rid": run_id})
        dq_domains = [str(row[0]) for row in r2.fetchall()]
        print(f"\n=== domains_queue ({len(dq_domains)} domains) ===")
        for d in dq_domains:
            print(f"  {d}")

        # 3. Check which domains_queue domains match moderator_suppliers
        print("\n=== Matching domains_queue -> moderator_suppliers ===")
        for d in dq_domains:
            nd = d.lower().replace("www.", "")
            r3 = await db.execute(text(
                "SELECT ms.id, COALESCE(sd.domain, ms.domain) AS matched "
                "FROM moderator_suppliers ms "
                "LEFT JOIN supplier_domains sd ON sd.supplier_id = ms.id "
                "WHERE replace(lower(COALESCE(sd.domain, ms.domain, '')), 'www.', '') = :d "
                "LIMIT 1"
            ), {"d": nd})
            row = r3.fetchone()
            if row:
                print(f"  {d} -> MATCH (supplier_id={row[0]}, matched={row[1]})")
            else:
                print(f"  {d} -> NO MATCH")

        # 4. Check supplier_domains for the supplier_ids from run_domains
        if sup_ids:
            print(f"\n=== supplier_domains for supplier_ids {sup_ids} ===")
            r4 = await db.execute(text(
                "SELECT supplier_id, domain FROM supplier_domains WHERE supplier_id = ANY(:ids) ORDER BY supplier_id"
            ), {"ids": sup_ids})
            for row in r4.fetchall():
                print(f"  supplier_id={row[0]} domain={row[1]}")

asyncio.run(main())
