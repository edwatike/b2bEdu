"""Check parser logs for domains with empty reason."""
import asyncio
import asyncpg
import json

async def main():
    conn = await asyncpg.connect('postgresql://postgres:12059001@localhost:5432/b2bplatform')
    
    run_id = '435e6e2f-00d8-4651-b359-e0d3936f487f'
    
    # Get parsing_runs.process_log (id is UUID, need to cast)
    row = await conn.fetchrow("""
        SELECT process_log FROM parsing_runs WHERE id::text = $1
    """, run_id)
    
    if not row or not row['process_log']:
        print('No process_log found')
        await conn.close()
        return
    
    process_log = row['process_log']
    
    # Find domains with empty reason
    problem_domains = [
        'alterteplo.ru', 'ozon.ru', 'petrovich.ru', 'rzhevka-market.ru',
        'stroyportal.ru', 'tdvasya.ru', 'tophouse.ru', 'tstn.ru', 'utepliteli-optom.ru'
    ]
    
    print(f'\n=== Checking parser logs for {len(problem_domains)} domains ===\n')
    
    for domain in problem_domains:
        domain_log = process_log.get(domain, {})
        
        print(f"\n{domain}:")
        print(f"  Status: {domain_log.get('status', 'not found')}")
        print(f"  Error: {domain_log.get('error', 'none')[:200]}")
        print(f"  Result: {str(domain_log.get('result', {}))[:200]}")
        
        if 'attempted_urls' in domain_log:
            print(f"  Attempted URLs: {len(domain_log['attempted_urls'])}")
            for url in domain_log.get('attempted_urls', [])[:3]:
                print(f"    - {url}")
    
    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
