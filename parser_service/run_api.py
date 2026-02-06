"""
Startup script for parser service API with correct event loop policy for Windows
"""
import asyncio
import sys

# CRITICAL: Set event loop policy BEFORE any imports
# This must be the very first thing to avoid NotImplementedError on Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

if __name__ == "__main__":
    from api import app
    import os
    
    # Use uvicorn directly (Hypercorn hangs on Windows)
    import uvicorn
    
    async def run_server():
        host = (os.getenv("PARSER_HOST") or "127.0.0.1").strip()
        try:
            port = int((os.getenv("PARSER_PORT") or "9000").strip())
        except Exception:
            port = 9000
        config = uvicorn.Config(
            app=app,
            host=host,
            port=port,
            log_level="info",
            access_log=True
        )
        server = uvicorn.Server(config)
        await server.serve()
    
    asyncio.run(run_server())
