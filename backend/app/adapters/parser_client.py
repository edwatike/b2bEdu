"""HTTP client for Parser Service."""
import httpx
from typing import List, Dict, Any, Optional
from app.config import settings


class ParserClient:
    """Client for communicating with Parser Service."""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.parser_service_url
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=300.0,  # 5 minutes for parsing operations
            trust_env=False  # Disable proxy for local connections
        )
    
    async def parse(
        self,
        keyword: str,
        depth: int = 10,
        source: str = "google",
        run_id: Optional[str] = None,
        resume_from: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """
        Start parsing for a keyword.
        
        Args:
            keyword: Search keyword
            depth: Number of search result pages to parse (depth)
            source: Source for parsing - "google", "yandex", or "both" (default: "google")
            
        Returns:
            Dictionary with parsing results
            
        Raises:
            httpx.HTTPStatusError: If the request fails, with detailed error message from Parser Service
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Use explicit Content-Type with charset=utf-8 to prevent Cyrillic mojibake
        # This fixes the issue where Cyrillic queries become '?????' (from HANDOFF.md)
        try:
            response = await self.client.post(
                "/parse",
                json={
                    "keyword": keyword,
                    "depth": depth,
                    "source": source,
                    "run_id": run_id,
                    "resume_from": resume_from,
                },
                headers={
                    "Content-Type": "application/json; charset=utf-8"
                }
            )
            
            # Extract detailed error message before raising exception
            if not response.is_success:
                error_detail = "Unknown error"
                try:
                    error_data = response.json()
                    error_detail = error_data.get("detail", error_data.get("message", str(response.status_code)))
                except Exception:
                    try:
                        error_detail = f"HTTP {response.status_code}: {response.text[:500]}"  # Limit text length
                    except:
                        error_detail = f"HTTP {response.status_code}: {response.status_text}"
                
                logger.error(f"Parser Service error ({response.status_code}): {error_detail}")
                
                # Raise HTTPStatusError with detailed message
                # The error_detail will be accessible via e.response.json()["detail"]
                response.raise_for_status()  # This will raise HTTPStatusError
            
            return response.json()
        except httpx.HTTPStatusError as e:
            # Re-raise with original details
            raise
        except httpx.RequestError as e:
            # Network/connection errors (503, connection refused, etc.)
            error_msg = f"Failed to connect to Parser Service at {self.base_url}: {str(e)}"
            logger.error(f"Parser Service connection error: {error_msg}")
            # Raise as HTTPStatusError-like exception so it can be caught and handled properly
            raise Exception(error_msg)
        except Exception as e:
            logger.error(f"Unexpected error in parser_client.parse: {e}", exc_info=True)
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Parser Service health."""
        try:
            response = await self.client.get("/health")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def get_html_via_cdp(self, url: str) -> Dict[str, Any]:
        """Get HTML content from URL using Chrome CDP via Parser Service.
        
        This method connects to Chrome via CDP, navigates to the URL,
        and returns the HTML content. This is used for INN extraction
        where we need to get the actual rendered HTML from the browser.
        
        Args:
            url: URL to fetch HTML from
            
        Returns:
            Dict with structure:
            {
                "url": str,
                "html": str,
                "title": str | None,
                "success": bool,
                "error": str | None
            }
            
        Raises:
            httpx.HTTPError: If request fails
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info(f"Fetching HTML via Chrome CDP for URL: {url}")
            response = await self.client.post(
                "/get-html",
                json={"url": url},
                headers={
                    "Content-Type": "application/json; charset=utf-8"
                }
            )
            response.raise_for_status()
            result = response.json()
            
            if result.get("success"):
                logger.info(f"Successfully fetched HTML via CDP for {url}, length: {len(result.get('html', ''))} chars")
            else:
                logger.warning(f"Failed to fetch HTML via CDP for {url}: {result.get('error')}")
            
            return result
        except httpx.HTTPStatusError as e:
            error_detail = "Unknown error"
            try:
                error_data = e.response.json()
                error_detail = error_data.get("detail", error_data.get("error", str(e.response.status_code)))
            except Exception:
                try:
                    error_detail = f"HTTP {e.response.status_code}: {e.response.text[:500]}"
                except:
                    error_detail = f"HTTP {e.response.status_code}: {e.response.status_text}"
            
            logger.error(f"Parser Service error while fetching HTML ({e.response.status_code}): {error_detail}")
            raise
        except httpx.RequestError as e:
            error_msg = f"Failed to connect to Parser Service at {self.base_url}: {str(e)}"
            logger.error(f"Parser Service connection error: {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            logger.error(f"Unexpected error in parser_client.get_html_via_cdp: {e}", exc_info=True)
            raise
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
