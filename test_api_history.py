import asyncio
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import settings

async def test_api_response():
    """Test the API response format for domain history."""
    engine = create_async_engine(settings.DATABASE_URL)
    
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT id, domain, run_id, action, message, details, created_at 
            FROM domain_logs 
            WHERE domain = 'rzhevka-market.ru' 
            ORDER BY created_at DESC 
            LIMIT 100
        """))
        
        rows = result.fetchall()
        
        # Format response like the API does
        logs = []
        for r in rows:
            logs.append({
                "id": r[0],
                "domain": r[1],
                "run_id": r[2],
                "action": r[3],
                "message": r[4],
                "details": r[5],
                "created_at": str(r[6]) if r[6] else None,
            })
        
        response = {
            "domain": "rzhevka-market.ru",
            "total": len(logs),
            "logs": logs
        }
        
        print(f"API Response for rzhevka-market.ru:")
        print(f"Total: {response['total']}")
        print("\nLogs:")
        for log in response['logs']:
            print(f"  - {log['action']}: {log['message']} (Run: {log['run_id']})")

if __name__ == "__main__":
    asyncio.run(test_api_response())
