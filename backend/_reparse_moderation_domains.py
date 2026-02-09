"""Reparse domains with requires_moderation status for run 435e6e2f."""
import asyncio
import asyncpg
import httpx

async def main():
    run_id = '435e6e2f-00d8-4651-b359-e0d3936f487f'
    
    # 1. Сбросить статус requires_moderation -> pending в run_domains
    conn = await asyncpg.connect('postgresql://postgres:12059001@localhost:5432/b2bplatform')
    
    result = await conn.execute("""
        UPDATE run_domains 
        SET status = 'pending', reason = NULL, attempted_urls = NULL
        WHERE run_id = $1 AND status = 'requires_moderation'
    """, run_id)
    
    print(f'Reset {result.split()[-1]} domains to pending status')
    
    # 2. Проверить количество pending доменов
    pending_count = await conn.fetchval("""
        SELECT COUNT(*) FROM run_domains 
        WHERE run_id = $1 AND status = 'pending'
    """, run_id)
    
    print(f'Total pending domains: {pending_count}')
    
    await conn.close()
    
    # 3. Запустить domain parser через backend API
    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f'\nStarting domain parser for run {run_id}...')
        
        response = await client.post(
            f'http://127.0.0.1:8000/api/moderator/current-task/{run_id}/start-domain-parser',
            headers={'Authorization': 'Bearer fake-token-for-testing'}  # В dev режиме токен не проверяется
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f'✅ Parser started successfully!')
            print(f'   Parser run ID: {data.get("parser_run_id")}')
            print(f'   Pending count: {data.get("pending_count")}')
        else:
            print(f'❌ Failed to start parser: {response.status_code}')
            print(f'   Response: {response.text[:200]}')

if __name__ == '__main__':
    asyncio.run(main())
