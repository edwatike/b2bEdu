"""Check domains with requires_moderation status for run 435e6e2f."""
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://postgres:12059001@localhost:5432/b2bplatform')
    
    run_id = '435e6e2f-00d8-4651-b359-e0d3936f487f'
    
    rows = await conn.fetch("""
        SELECT domain, status, reason, attempted_urls, inn_source_url, email_source_url
        FROM run_domains 
        WHERE run_id = $1 AND status = 'requires_moderation'
        ORDER BY domain
    """, run_id)
    
    print(f'\n=== Total requires_moderation: {len(rows)} ===\n')
    
    for r in rows:
        reason_text = r['reason'][:100] if r['reason'] else 'no reason'
        attempted = len(r['attempted_urls']) if r['attempted_urls'] else 0
        print(f"  {r['domain']}")
        print(f"    Reason: {reason_text}")
        print(f"    Attempted URLs: {attempted}")
        print()
    
    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
