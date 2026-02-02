"""Main parser logic."""
from typing import List, Optional, Set, Dict, Any
from playwright.async_api import async_playwright, Browser, Page
from bs4 import BeautifulSoup
import httpx
import asyncio
import logging

from src.config import settings
from src.models import ParsedSupplier
from src.utils import (
    extract_domain,
    extract_emails,
    extract_phones,
    extract_inn,
    clean_text,
)
from src.human_behavior import random_delay, human_like_scroll

logger = logging.getLogger(__name__)


class Parser:
    """Main parser class."""
    
    def __init__(self, chrome_cdp_url: str):
        self.chrome_cdp_url = chrome_cdp_url
        self.browser: Optional[Browser] = None
        self.playwright = None
        self._playwright_started = False
        self.context = None
        self._playwright_loop = None  # Store event loop for Windows thread
        self._last_logs_send_time: Dict[str, float] = {}  # run_id -> timestamp для rate limiting
    
    async def _send_parsing_logs(self, run_id: Optional[str], parsing_logs: Dict[str, Any]) -> None:
        """Отправляет parsing_logs в backend для инкрементального обновления.
        
        Args:
            run_id: ID запуска парсинга
            parsing_logs: Словарь с логами парсинга (только для текущего запуска)
        """
        if not run_id or not parsing_logs:
            return
        
        # Rate limiting: отправляем не чаще раза в 2.5 секунды (синхронизировано с интервалом отправки)
        import time
        import json
        current_time = time.time()
        last_send_time = self._last_logs_send_time.get(run_id, 0)
        if current_time - last_send_time < 2.5:
            return
        
        # Логирование размера логов перед отправкой
        logs_size = len(json.dumps(parsing_logs, ensure_ascii=False))
        logger.info(f"Sending parsing logs to backend for run_id: {run_id}, size: {logs_size} bytes")
        
        try:
            backend_url = settings.BACKEND_URL
            url = f"{backend_url}/parsing/runs/{run_id}/logs"
            
            async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
                response = await client.put(
                    url,
                    json={"parsing_logs": parsing_logs},
                    headers={"Content-Type": "application/json"}
                )
                if response.status_code == 200:
                    self._last_logs_send_time[run_id] = current_time
                    logger.info(f"Successfully sent parsing logs to backend for run_id: {run_id}, size: {logs_size} bytes")
                else:
                    response_text = response.text[:200] if hasattr(response, 'text') else str(response.status_code)
                    logger.warning(f"Failed to send parsing logs to backend for run_id: {run_id}, status: {response.status_code}, response: {response_text}, logs_size: {logs_size} bytes")
        except Exception as e:
            logger.warning(f"Error sending parsing logs to backend for run_id: {run_id}, error: {e}, logs_size: {logs_size} bytes", exc_info=True)
    
    async def connect_browser(self):
        """Connect to a browser.

        By default, launches isolated Chromium (headless) to avoid interfering with user's browser.
        Only attaches to an existing Chrome via CDP when USE_CHROME_CDP=True.
        """
        import logging
        import httpx
        import json
        import asyncio
        import sys
        from playwright.async_api import async_playwright
        
        logger = logging.getLogger(__name__)
        
        try:
            # Safe default: do not attach to user's real Chrome unless explicitly enabled.
            if not getattr(settings, "USE_CHROME_CDP", False):
                logger.info("Launching isolated Chromium (USE_CHROME_CDP is disabled)")

                if not self._playwright_started:
                    logger.info("Starting Playwright...")
                    self.playwright = await async_playwright().start()
                    self._playwright_started = True
                    logger.info("Playwright started successfully")

                self.browser = await self.playwright.chromium.launch(headless=getattr(settings, "HEADLESS", True))
                self.context = await self.browser.new_context(
                    viewport={"width": 1280, "height": 720},
                )
                await self.context.set_extra_http_headers({
                    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                })
                logger.info("Isolated Chromium context created successfully")
                return

            # First, check if Chrome CDP is available and get WebSocket URL
            logger.info(f"Checking Chrome CDP availability at {self.chrome_cdp_url}...")
            ws_url = None
            
            try:
                # Get WebSocket URL from Chrome CDP
                async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
                    response = await client.get(f"{self.chrome_cdp_url}/json/version")
                    if response.status_code != 200:
                        raise Exception(
                            f"Chrome CDP returned status {response.status_code}. "
                            f"Make sure Chrome is running with --remote-debugging-port=9222"
                        )
                    cdp_info = response.json()
                    if "webSocketDebuggerUrl" in cdp_info:
                        ws_url = cdp_info["webSocketDebuggerUrl"]
                        logger.info(f"Found WebSocket URL: {ws_url}")
                        logger.info(f"Chrome version: {cdp_info.get('Browser', 'Unknown')}")
                    else:
                        # Fallback: convert HTTP URL to WebSocket URL
                        ws_url = self.chrome_cdp_url.replace("http://", "ws://") + "/devtools/browser"
                        logger.warning(f"webSocketDebuggerUrl not found in CDP response, using fallback: {ws_url}")
            except httpx.ConnectError as cdp_check_err:
                error_msg = (
                    f"Cannot connect to Chrome CDP at {self.chrome_cdp_url}. "
                    f"Please start Chrome with --remote-debugging-port=9222. "
                    f"Connection error: {cdp_check_err}"
                )
                logger.error(error_msg)
                raise Exception(error_msg) from cdp_check_err
            except httpx.TimeoutException as cdp_check_err:
                error_msg = (
                    f"Timeout connecting to Chrome CDP at {self.chrome_cdp_url}. "
                    f"Chrome may be slow to respond or not running. Error: {cdp_check_err}"
                )
                logger.error(error_msg)
                raise Exception(error_msg) from cdp_check_err
            except Exception as cdp_check_err:
                error_msg = (
                    f"Chrome CDP check failed at {self.chrome_cdp_url}. "
                    f"Please start Chrome with --remote-debugging-port=9222. Error: {cdp_check_err}"
                )
                logger.error(error_msg)
                raise Exception(error_msg) from cdp_check_err
            
            if not ws_url:
                raise Exception("Failed to get WebSocket URL from Chrome CDP")
            
            # Connect to Chrome CDP using the working approach from test_browser_connection.py
            # On Windows, we need to run Playwright in a separate thread with its own event loop
            # using asyncio.run() to avoid NotImplementedError
            logger.info(f"Connecting to Chrome CDP via WebSocket: {ws_url}...")
            
            # Start Playwright if not already started
            if not self._playwright_started:
                logger.info("Starting Playwright...")
                self.playwright = await async_playwright().start()
                self._playwright_started = True
                logger.info("Playwright started successfully")
            
            # Connect to Chrome CDP
            connect_url = ws_url if "ws://" in ws_url or "ws://" in ws_url else self.chrome_cdp_url
            logger.info(f"Connecting to Chrome CDP at {connect_url}...")
            try:
                self.browser = await self.playwright.chromium.connect_over_cdp(connect_url)
                logger.info(f"Connected to Chrome CDP successfully")
            except Exception as connect_err:
                error_msg = (
                    f"Failed to connect to Chrome CDP via WebSocket {connect_url}. "
                    f"Make sure Chrome is running in debug mode. Error: {connect_err}"
                )
                logger.error(error_msg)
                raise Exception(error_msg) from connect_err
                
        except Exception as e:
            logger.error(f"Error connecting to Chrome CDP: {e}", exc_info=True)
            raise Exception(f"Failed to connect to Chrome CDP at {self.chrome_cdp_url}: {str(e)}") from e
    
    async def close(self):
        """Close browser connection."""
        try:
            if self.browser:
                # Don't close browser, just disconnect
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Error during close: {e}")
    
    async def parse_page(self, url: str) -> dict:
        """Parse a single page and extract supplier data."""
        # Don't call connect_browser() here - browser should already be set
        if not self.browser:
            raise Exception("Browser not connected. Call connect_browser() first or set browser directly.")
        
        # Use context if available, otherwise create page from browser
        if self.context:
            page = await self.context.new_page()
        else:
            page = await self.browser.new_page()
        
        try:
            # Navigate to page
            await page.goto(url, wait_until="networkidle", timeout=settings.page_load_timeout)
            
            # Simulate human behavior
            await random_delay(1000, 2000)
            await human_like_scroll(page)
            
            # Get page content
            html = await page.content()
            title = await page.title()
            
            # Parse HTML
            soup = BeautifulSoup(html, "lxml")
            text = soup.get_text()
            
            # Extract data
            emails = extract_emails(text)
            phones = extract_phones(text)
            inn = extract_inn(text)
            
            # Extract company name (from title or h1)
            company_name = title
            h1 = soup.find("h1")
            if h1:
                company_name = clean_text(h1.get_text())
            
            # If no company name found, use domain
            if not company_name or len(company_name) < 3:
                company_name = extract_domain(url)
            
            return {
                "name": company_name,
                "domain": extract_domain(url),
                "email": emails[0] if emails else None,
                "phone": phones[0] if phones else None,
                "inn": inn,
                "source_url": url,
            }
        except Exception as e:
            print(f"Error parsing {url}: {e}")
            return {
                "name": extract_domain(url),
                "domain": extract_domain(url),
                "email": None,
                "phone": None,
                "inn": None,
                "source_url": url,
            }
        finally:
            await page.close()
    
    async def parse_keyword(self, keyword: str, depth: int = 10, source: str = "google", run_id: Optional[str] = None) -> List[dict]:
        """Parse suppliers for a keyword.
        
        Args:
            keyword: Search keyword
            max_urls: Maximum number of URLs to parse (used as depth for search pages)
            source: Source for parsing - "google", "yandex", or "both" (default: "google")
        """
        import asyncio
        import logging
        from src.engines import YandexEngine, GoogleEngine
        
        logger = logging.getLogger(__name__)
        
        try:
            # Connect to browser first (if not already connected)
            if not self.browser or not self.playwright:
                logger.info(f"Connecting to browser for keyword: {keyword}")
                await self.connect_browser()
                logger.info(f"Browser connected successfully")
            else:
                logger.info(f"Using existing browser connection for keyword: {keyword}")
            
            # Use depth directly from parameter
            logger.info(f"Parsing with depth={depth} (type: {type(depth)}), source={source}")
            if depth != int(depth) or depth < 1:
                logger.warning(f"Invalid depth value: {depth}, using 1")
                depth = 1
            depth = int(depth)  # Ensure it's an integer
            
            # Prepare query (add "купить" as in old parser)
            query = f"{keyword} купить"
            
            # Collect links from search engines with source tracking
            # Use dict to track which source(s) found each URL
            collected_links: Dict[str, Set[str]] = {}  # URL -> set of sources (google, yandex)
            
            # Get browser contexts - CRITICAL: use existing browser's contexts
            # This ensures we use the SAME browser window that user sees
            contexts = self.browser.contexts
            logger.info(f"Found {len(contexts)} existing browser contexts")
            print(f"[INFO] Found {len(contexts)} existing browser contexts")
            
            if len(contexts) == 0:
                # If no contexts exist, create one - but this should rarely happen
                logger.warning("No existing browser contexts found, creating new one")
                print("[WARNING] No existing browser contexts found, creating new one")
                self.context = await self.browser.new_context(
                    viewport={"width": 800, "height": 600},
                    no_viewport=False
                )
            else:
                # Select context based on profile index
                # Profile index: 0 = first profile, 1 = second profile, etc.
                profile_index = settings.CHROME_PROFILE_INDEX
                
                # Use specific profile context if index is valid
                if 0 <= profile_index < len(contexts):
                    self.context = contexts[profile_index]
                    logger.info(f"Using profile context at index {profile_index} (profile #{profile_index + 1})")
                    print(f"[INFO] Using profile #{profile_index + 1} context with {len(self.context.pages)} pages")
                    print(f"[INFO] Parser will use profile #{profile_index + 1} browser window for parsing!")
                else:
                    # Fallback to first context if index is out of range
                    logger.warning(
                        f"Profile index {profile_index} is out of range (0-{len(contexts)-1}), "
                        f"using first context (profile #1)"
                    )
                    self.context = contexts[0]
                    print(f"[INFO] Using YOUR existing browser context (profile #1) with {len(self.context.pages)} pages")
                    print(f"[INFO] Parser will use YOUR browser window for parsing!")
                
                # Don't change viewport of existing pages - user might have them sized as needed
                # Just ensure we can work with them
            
            # Set HTTP headers
            await self.context.set_extra_http_headers({
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            })
            
            # Normalize source parameter (lowercase, strip whitespace)
            source_normalized = str(source).lower().strip() if source else "google"
            logger.info(f"Source (original): '{source}', source (normalized): '{source_normalized}'")
            
            # Run search engines in parallel
            tasks = []
            
            # Initialize parsing logs structure
            parsing_logs = {}
            
            # Create pages only for requested sources (use elif to ensure only one branch executes)
            # Note: Playwright automatically activates new pages, but we don't call bring_to_front()
            # Pages will only be brought to front if CAPTCHA is detected (in wait_for_captcha())
            if source_normalized == "yandex":
                logger.info("Creating Yandex page only (source=yandex)")
                yandex_page = await self.context.new_page()
                # Don't bring to front - page will be activated only if CAPTCHA is detected
                yandex_engine = YandexEngine()
                tasks.append(yandex_engine.parse(yandex_page, query, depth, collected_links, run_id, keyword, parsing_logs))
            elif source_normalized == "google":
                logger.info("Creating Google page only (source=google)")
                google_page = await self.context.new_page()
                # Don't bring to front - page will be activated only if CAPTCHA is detected
                google_engine = GoogleEngine()
                tasks.append(google_engine.parse(google_page, query, depth, collected_links, run_id, keyword, parsing_logs))
            elif source_normalized == "both":
                logger.info("Creating both Yandex and Google pages (source=both)")
                yandex_page = await self.context.new_page()
                # Don't bring to front - page will be activated only if CAPTCHA is detected
                yandex_engine = YandexEngine()
                tasks.append(yandex_engine.parse(yandex_page, query, depth, collected_links, run_id, keyword, parsing_logs))
                
                google_page = await self.context.new_page()
                # Don't bring to front - page will be activated only if CAPTCHA is detected
                google_engine = GoogleEngine()
                tasks.append(google_engine.parse(google_page, query, depth, collected_links, run_id, keyword, parsing_logs))
            else:
                # Default to Google if source is invalid
                logger.warning(f"Invalid source '{source_normalized}', defaulting to Google")
                google_page = await self.context.new_page()
                # Don't bring to front - page will be activated only if CAPTCHA is detected
                google_engine = GoogleEngine()
                tasks.append(google_engine.parse(google_page, query, depth, collected_links, run_id, keyword, parsing_logs))
            
            logger.info(f"Created {len(tasks)} task(s) for parsing")
            
            # Wait for all search engines to complete
            if tasks:
                # Запускаем задачи и периодически отправляем логи в backend
                # Создаем задачу для периодической отправки логов
                async def send_logs_periodically():
                    """Периодически отправляет логи в backend во время парсинга."""
                    send_count = 0
                    logger.info(f"Starting periodic logs sending for run_id: {run_id}")
                    try:
                        while True:
                            await asyncio.sleep(2.5)  # Синхронизировано с rate limiting (2.5 сек)
                            if parsing_logs:
                                send_count += 1
                                logger.info(f"Attempting to send logs (attempt #{send_count}) for run_id: {run_id}")
                                await self._send_parsing_logs(run_id, parsing_logs)
                            else:
                                logger.debug(f"No logs to send yet for run_id: {run_id}")
                    except asyncio.CancelledError:
                        logger.info(f"Periodic logs sending cancelled for run_id: {run_id}, total attempts: {send_count}")
                        raise
                    except Exception as e:
                        logger.error(f"Error in periodic logs sending for run_id: {run_id}: {e}", exc_info=True)
                
                # Запускаем задачу отправки логов в фоне
                logs_task = asyncio.create_task(send_logs_periodically())
                
                try:
                    # Ждем завершения парсинга
                    await asyncio.gather(*tasks)
                finally:
                    # Отменяем задачу отправки логов и отправляем финальные логи
                    logs_task.cancel()
                    try:
                        await logs_task
                    except asyncio.CancelledError:
                        pass
                    # Отправляем финальные логи
                    if parsing_logs:
                        await self._send_parsing_logs(run_id, parsing_logs)
            
            # Convert dict to list (no limit - return all collected URLs)
            urls_with_sources = list(collected_links.items())
            
            if not urls_with_sources:
                logger.warning(f"No URLs found for keyword '{keyword}'")
                await self.close()
                return []
            
            logger.info(f"Found {len(urls_with_sources)} URLs from search engines")
            
            # Return only URLs without parsing pages
            # Extract domain from each URL and create supplier-like structure
            suppliers = []
            for url, sources in urls_with_sources:
                from urllib.parse import urlparse
                parsed_url = urlparse(url)
                domain = parsed_url.netloc.replace("www.", "")
                
                # Determine source: "google", "yandex", or "both"
                url_source = "both" if len(sources) > 1 else list(sources)[0] if sources else "google"
                
                suppliers.append(ParsedSupplier(
                    name=domain,  # Use domain as name since we don't parse pages
                    domain=domain,
                    email=None,
                    phone=None,
                    inn=None,
                    source_url=url,
                    source=url_source  # Add source information
                ))
            
            await self.close()
            # Return suppliers with parsing logs
            return suppliers, parsing_logs
        except Exception as e:
            logger.error(f"Error in parse_keyword: {e}", exc_info=True)
            # Ensure cleanup on error
            try:
                await self.close()
            except:
                pass
            raise

