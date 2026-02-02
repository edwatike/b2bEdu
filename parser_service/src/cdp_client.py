"""Simple Chrome DevTools Protocol client for connecting to existing Chrome."""
import asyncio
import json
import logging
from typing import Optional, Dict, Any, List
import websockets
from playwright.async_api import Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class CDPClient:
    """Simple CDP client for connecting to existing Chrome without Playwright subprocess."""
    
    def __init__(self, cdp_url: str):
        self.cdp_url = cdp_url
        self.ws_url: Optional[str] = None
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.message_id = 0
        self.pending_requests: Dict[int, asyncio.Future] = {}
    
    async def connect(self):
        """Connect to Chrome CDP and get WebSocket URL."""
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
                response = await client.get(f"{self.cdp_url}/json/version")
                if response.status_code != 200:
                    raise Exception(f"Chrome CDP returned status {response.status_code}")
                cdp_info = response.json()
                if "webSocketDebuggerUrl" in cdp_info:
                    self.ws_url = cdp_info["webSocketDebuggerUrl"]
                    logger.info(f"Found WebSocket URL: {self.ws_url}")
                else:
                    raise Exception("No webSocketDebuggerUrl in CDP response")
        except Exception as e:
            logger.error(f"Failed to get CDP WebSocket URL: {e}")
            raise
    
    async def get_browser_contexts(self) -> List[Dict[str, Any]]:
        """Get list of browser contexts via CDP."""
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
                response = await client.get(f"{self.cdp_url}/json")
                if response.status_code != 200:
                    raise Exception(f"Chrome CDP returned status {response.status_code}")
                return response.json()
        except Exception as e:
            logger.error(f"Failed to get browser contexts: {e}")
            raise



















