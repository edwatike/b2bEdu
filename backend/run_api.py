"""Script to run the Backend API."""
import sys
import os

# CRITICAL: Add backend directory to Python path BEFORE importing app
# Use the EXACT same approach as temp/test_uvicorn_direct.py which works
# temp/test_uvicorn_direct.py (from temp/): os.path.join(os.path.dirname(__file__), '..', 'backend')
# run_api.py (from backend/): os.path.dirname(os.path.abspath(__file__))
script_file = os.path.abspath(__file__)
script_dir = os.path.dirname(script_file)
# When run from project root: python backend/run_api.py
# script_file = D:\tryagain\backend\run_api.py
# script_dir = D:\tryagain\backend
backend_dir = script_dir
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# CRITICAL: Set PYTHONPATH environment variable for uvicorn reload mode
# When uvicorn runs with reload=True and import string, it spawns a new process
# that needs to have the correct Python path to import modules
os.environ["PYTHONPATH"] = backend_dir + os.pathsep + os.environ.get("PYTHONPATH", "")

import logging

# Configure logging before importing app
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)

import uvicorn
from app.main import app

# Verify app is loaded correctly (same as test_uvicorn_direct.py)
from fastapi.routing import APIRoute
routes = [r for r in app.routes if isinstance(r, APIRoute)]
inn_routes = [r for r in routes if 'inn' in r.path.lower()]
logger = logging.getLogger(__name__)
logger.info(f"=== Starting uvicorn with {len(routes)} routes ===")
logger.info(f"=== INN routes: {[r.path for r in inn_routes]} ===")
logger.info(f"=== App instance ID: {id(app)} ===")
logger.info(f"=== PYTHONPATH set to: {os.environ.get('PYTHONPATH', 'NOT SET')} ===")

if __name__ == "__main__":
    # CRITICAL: For reload=True, uvicorn requires import string, not direct app object
    # Use import string to enable reload functionality
    # IMPORTANT: reload_dirs ensures uvicorn watches the correct directory
    # and excludes temp/ to avoid unnecessary reloads
    # 
    # NOTE: Using direct app object works better for reliability
    # If reload is needed, use import string, but ensure PYTHONPATH is set
    use_reload = os.environ.get("UVICORN_RELOAD", "false").lower() == "true"
    
    if use_reload:
        # Use import string for reload mode
        uvicorn.run(
            "app.main:app",  # Import string required for reload
            host="127.0.0.1",
            port=8000,
            reload=True,
            reload_dirs=[backend_dir],  # Only watch backend directory
            reload_excludes=["temp/*", "*.pyc", "__pycache__"],  # Exclude temp files
            log_level="info"
        )
    else:
        # Use direct app object for better reliability (no reload)
        # This ensures all routes are registered correctly
        uvicorn.run(
            app,  # Direct app object - more reliable
            host="127.0.0.1",
            port=8000,
            reload=False,
            log_level="info"
        )
