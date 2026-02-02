"""FastAPI application for Parser Service."""
import asyncio
import sys
import logging
import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Set, Any

# CRITICAL: Set event loop policy BEFORE any other imports
# This must be the very first thing to avoid NotImplementedError on Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from src.models import ParsedSupplier, ParseRequest, ParseResponse
from src.config import settings
from src.simple_ocr_wrapper import smart_extract_text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Parser Service API",
    version="1.0.0",
    description="Web parsing service using Chrome CDP"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ParseRequest(BaseModel):
    """Request model for parsing."""
    keyword: str
    depth: int = 10  # Number of search result pages to parse
    source: str = "google"  # "google", "yandex", or "both"
    run_id: Optional[str] = None  # Optional run_id for status updates


class ParsedSupplier(BaseModel):
    """Parsed supplier data."""
    name: str
    domain: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    inn: Optional[str] = None
    source_url: str
    source: Optional[str] = None  # Source: "google", "yandex", or "both"


class ParseResponse(BaseModel):
    """Response model for parsing."""
    keyword: str
    suppliers: List[ParsedSupplier]
    total_found: int
    parsing_logs: Optional[Dict[str, Any]] = None  # Structured parsing logs with links found by each engine


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/ocr/extract-text")
async def ocr_extract_text(file: UploadFile = File(...)):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        text = smart_extract_text(file.filename or "file", content) or ""
        return {"text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR failed: {e}")


class GetHtmlRequest(BaseModel):
    """Request model for getting HTML from URL via Chrome CDP."""
    url: str


class GetHtmlResponse(BaseModel):
    """Response model for HTML content."""
    url: str
    html: str
    title: Optional[str] = None
    success: bool
    error: Optional[str] = None


@app.post("/get-html", response_model=GetHtmlResponse)
async def get_html_via_cdp(request: GetHtmlRequest):
    """Get HTML content from URL using Chrome CDP.
    
    This endpoint connects to Chrome via CDP, navigates to the URL,
    and returns the HTML content. This is used for INN extraction
    where we need to get the actual rendered HTML from the browser.
    
    Args:
        request: Request with URL to fetch
        
    Returns:
        Response with HTML content
    """
    import traceback
    import logging
    import asyncio
    import sys
    from concurrent.futures import ThreadPoolExecutor
    
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"=== GET HTML REQUEST === URL: {request.url}")
        logger.info(f"Platform: {sys.platform}, is Windows: {sys.platform == 'win32'}")
        
        # On Windows, run in a separate thread with asyncio.run() to avoid NotImplementedError
        if sys.platform == 'win32':
            logger.info("Using Windows-specific HTML fetching in separate thread with asyncio.run()")
            
            def get_html_in_thread(url_param, chrome_cdp_url_param):
                """Run HTML fetching in a separate thread with its own event loop."""
                import asyncio
                import sys
                
                # Set event loop policy for this thread
                if sys.platform == 'win32':
                    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                
                # Import here AFTER setting policy
                import httpx
                from playwright.async_api import async_playwright
                from src.parser import Parser
                
                async def get_html_async():
                    """Async function to get HTML via Chrome CDP."""
                    import logging
                    thread_logger = logging.getLogger(__name__)
                    thread_logger.info(f"Starting get_html_async() for URL: {url_param}")
                    
                    # Get WebSocket URL from Chrome CDP
                    thread_logger.info("Getting Chrome CDP WebSocket URL...")
                    async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
                        response = await client.get(f"{chrome_cdp_url_param}/json/version")
                        if response.status_code != 200:
                            raise Exception(f"Chrome CDP returned status {response.status_code}")
                        cdp_info = response.json()
                        ws_url = cdp_info.get("webSocketDebuggerUrl")
                        if not ws_url:
                            raise Exception("No webSocketDebuggerUrl in CDP response")
                        thread_logger.info(f"Got WebSocket URL: {ws_url}")
                    
                    # Start Playwright and connect to Chrome
                    thread_logger.info("Starting Playwright...")
                    playwright = await async_playwright().start()
                    thread_logger.info("Playwright started, connecting to Chrome CDP...")
                    connect_errors = []
                    for connect_endpoint in (ws_url, chrome_cdp_url_param):
                        try:
                            thread_logger.info(f"Connecting to Chrome CDP via {connect_endpoint}...")
                            browser = await playwright.chromium.connect_over_cdp(connect_endpoint, timeout=60000)
                            break
                        except Exception as connect_err:
                            connect_errors.append((connect_endpoint, connect_err))
                            thread_logger.warning(f"CDP connect failed for {connect_endpoint}: {connect_err}")
                            await asyncio.sleep(1)
                    else:
                        error_summary = "; ".join([f"{endpoint}: {err}" for endpoint, err in connect_errors])
                        raise Exception(f"All CDP connection attempts failed: {error_summary}")
                    thread_logger.info("Connected to Chrome CDP successfully!")
                    
                    try:
                        # Get browser contexts
                        contexts = browser.contexts
                        thread_logger.info(f"Found {len(contexts)} browser context(s)")
                        
                        # Select context based on profile index
                        from src.config import settings
                        profile_index = settings.CHROME_PROFILE_INDEX
                        
                        if len(contexts) == 0:
                            thread_logger.warning("No existing contexts found, creating new context")
                            context = await browser.new_context(
                                viewport={"width": 1920, "height": 1080}
                            )
                        else:
                            if 0 <= profile_index < len(contexts):
                                context = contexts[profile_index]
                                thread_logger.info(f"Using profile context at index {profile_index}")
                            else:
                                thread_logger.warning(f"Profile index {profile_index} out of range, using first context")
                                context = contexts[0]
                        
                        # Set HTTP headers
                        await context.set_extra_http_headers({
                            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                        })
                        
                        async def block_heavy_resources(route, request):
                            if request.resource_type in {"image", "media", "font"}:
                                await route.abort()
                            else:
                                await route.continue_()

                        await context.route("**/*", block_heavy_resources)

                        # Create page and navigate
                        page = await context.new_page()
                        try:
                            thread_logger.info(f"Navigating to URL: {url_param}")
                            await page.goto(url_param, wait_until="domcontentloaded", timeout=settings.page_load_timeout)
                            
                            # Simulate human behavior (small delay)
                            await asyncio.sleep(0.3)
                            
                            # Get page content
                            html = await page.content()
                            title = await page.title()
                            
                            thread_logger.info(f"Successfully fetched HTML from {url_param}, length: {len(html)} chars")
                            
                            return {
                                "url": url_param,
                                "html": html,
                                "title": title,
                                "success": True,
                                "error": None
                            }
                        finally:
                            await page.close()
                    finally:
                        # Don't close browser, just disconnect
                        await browser.close()
                        await playwright.stop()
                
                # Use asyncio.run() to create a new event loop
                return asyncio.run(get_html_async())
            
            # Run in a separate thread
            current_loop = asyncio.get_running_loop()
            executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="get-html")
            try:
                logger.info("Running HTML fetching in separate thread with asyncio.run() (Windows)...")
                result = await current_loop.run_in_executor(
                    executor,
                    get_html_in_thread,
                    request.url,
                    settings.CHROME_CDP_URL
                )
            finally:
                executor.shutdown(wait=False)
        else:
            # Non-Windows: run normally
            parser = Parser(settings.CHROME_CDP_URL)
            await parser.connect_browser()
            try:
                # Use parse_page but only get HTML
                page = await parser.context.new_page() if parser.context else await parser.browser.new_page()
                async def block_heavy_resources(route, request):
                    if request.resource_type in {"image", "media", "font"}:
                        await route.abort()
                    else:
                        await route.continue_()
                await page.route("**/*", block_heavy_resources)
                try:
                    await page.goto(request.url, wait_until="domcontentloaded", timeout=settings.page_load_timeout)
                    await asyncio.sleep(0.3)  # Small delay
                    html = await page.content()
                    title = await page.title()
                    result = {
                        "url": request.url,
                        "html": html,
                        "title": title,
                        "success": True,
                        "error": None
                    }
                finally:
                    await page.close()
            finally:
                await parser.close()
        
        return GetHtmlResponse(**result)
        
    except httpx.ConnectError as e:
        error_message = f"Cannot connect to Chrome CDP at {settings.CHROME_CDP_URL}. Please ensure Chrome is running with --remote-debugging-port=9222. Error: {str(e)}"
        logger.error(f"Connection error in get_html_via_cdp: {error_message}")
        return GetHtmlResponse(
            url=request.url,
            html="",
            title=None,
            success=False,
            error=error_message
        )
    except Exception as e:
        error_traceback = traceback.format_exc()
        error_message = str(e) if e else "Unknown error"
        error_type = type(e).__name__
        
        logger.error(f"Error in get_html_via_cdp ({error_type}): {error_message}\n{error_traceback}")
        
        return GetHtmlResponse(
            url=request.url,
            html="",
            title=None,
            success=False,
            error=f"{error_type}: {error_message}"
        )


# Track running parse requests to prevent duplicates
_running_parse_requests = set()
# Create lock lazily to avoid issues with event loop
_parse_lock = None

def get_parse_lock():
    """Get or create the parse lock."""
    global _parse_lock
    if _parse_lock is None:
        try:
            _parse_lock = asyncio.Lock()
        except RuntimeError:
            # If no event loop is running, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            _parse_lock = asyncio.Lock()
    return _parse_lock

@app.post("/parse", response_model=ParseResponse)
async def parse_keyword(request: ParseRequest):
    """Parse suppliers for a keyword."""
    import traceback
    import logging
    import asyncio
    import sys
    from concurrent.futures import ThreadPoolExecutor
    
    logger = logging.getLogger(__name__)
    
    # Create request key for duplicate detection (without timestamp - same key for same request)
    request_key = f"{request.keyword}_{request.depth}_{request.source}"
    
    # CRITICAL: Use lock to prevent race conditions
    parse_lock = get_parse_lock()
    async with parse_lock:
        # CRITICAL: Prevent duplicate execution using request_key
        if request_key in _running_parse_requests:
            logger.warning(f"[DUPLICATE DETECTED] Parse request for '{request_key}' is already running, skipping duplicate call")
            # Return empty response for duplicate
            return ParseResponse(
                keyword=request.keyword,
                suppliers=[],
                total_found=0
            )
        
        # Mark request as running IMMEDIATELY to prevent race conditions
        _running_parse_requests.add(request_key)
        logger.info(f"[DUPLICATE CHECK] Marked request '{request_key}' as running (total running: {len(_running_parse_requests)})")
    
    try:
        logger.info(f"=== PARSE REQUEST === keyword: {request.keyword}, depth: {request.depth}, source: '{request.source}'")
        logger.info(f"Platform: {sys.platform}, is Windows: {sys.platform == 'win32'}")
        
        # On Windows, run parsing in a separate thread with asyncio.run() to avoid NotImplementedError
        # This is EXACTLY the same approach as test_browser_connection.py
        if sys.platform == 'win32':
            logger.info("Using Windows-specific parsing in separate thread with asyncio.run()")
            def run_parsing_in_thread(keyword_param, depth_param, source_param, chrome_cdp_url_param, run_id_param=None):
                """Run parsing in a separate thread with its own event loop using asyncio.run().
                
                This function runs ALL parsing operations in ONE asyncio.run() call,
                just like test_browser_connection.py does. This ensures all Playwright
                operations happen in the same event loop with the correct policy.
                """
                import asyncio
                import sys
                
                # Set event loop policy for this thread (same as test_browser_connection.py)
                # MUST be done BEFORE importing/using Playwright
                if sys.platform == 'win32':
                    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                
                # Import here AFTER setting policy to ensure Playwright uses correct policy
                import httpx
                from playwright.async_api import async_playwright
                from src.engines import YandexEngine, GoogleEngine
                from src.parser import Parser
                from typing import Set, Dict
                
                async def parse_async():
                    """Async function to run ALL parsing operations in one event loop."""
                    import logging
                    thread_logger = logging.getLogger(__name__)
                    thread_logger.info("Starting parse_async() in thread with asyncio.run()")
                    
                    from src.config import settings

                    thread_logger.info("Starting Playwright...")
                    playwright = await async_playwright().start()

                    browser = None
                    context = None

                    # Safe default: isolate browser. Only attach to user's Chrome if explicitly enabled.
                    if not getattr(settings, "USE_CHROME_CDP", False):
                        thread_logger.info("Launching isolated Chromium (USE_CHROME_CDP is disabled)")
                        browser = await playwright.chromium.launch(headless=getattr(settings, "HEADLESS", True))
                        context = await browser.new_context(viewport={"width": 1280, "height": 720})
                    else:
                        # Get WebSocket URL from Chrome CDP (same as test_browser_connection.py)
                        thread_logger.info("Getting Chrome CDP WebSocket URL...")
                        async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
                            response = await client.get(f"{chrome_cdp_url_param}/json/version")
                            if response.status_code != 200:
                                raise Exception(f"Chrome CDP returned status {response.status_code}")
                            cdp_info = response.json()
                            ws_url = cdp_info.get("webSocketDebuggerUrl")
                            if not ws_url:
                                raise Exception("No webSocketDebuggerUrl in CDP response")
                            thread_logger.info(f"Got WebSocket URL: {ws_url}")

                        thread_logger.info("Playwright started, connecting to Chrome CDP...")
                        browser = await playwright.chromium.connect_over_cdp(ws_url, timeout=60000)
                        thread_logger.info("Connected to Chrome CDP successfully!")
                    
                    try:
                        if context is None:
                            # CDP branch: get existing contexts
                            contexts = browser.contexts
                            thread_logger.info(f"Found {len(contexts)} browser context(s)")

                            profile_index = settings.CHROME_PROFILE_INDEX
                            if len(contexts) == 0:
                                thread_logger.warning("No existing contexts found, creating new context")
                                context = await browser.new_context(viewport={"width": 800, "height": 600})
                            else:
                                if 0 <= profile_index < len(contexts):
                                    context = contexts[profile_index]
                                    thread_logger.info(f"Using profile context at index {profile_index} (profile #{profile_index + 1})")
                                else:
                                    thread_logger.warning(
                                        f"Profile index {profile_index} is out of range (0-{len(contexts)-1}), "
                                        f"using first context (profile #1)"
                                    )
                                    context = contexts[0]
                        
                        # Set HTTP headers
                        await context.set_extra_http_headers({
                            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                        })
                        
                        # Now run the actual parsing logic
                        parser = Parser(chrome_cdp_url_param)
                        # Set browser, playwright, and context directly to avoid re-connecting
                        parser.browser = browser
                        parser.playwright = playwright
                        parser.context = context
                        parser._playwright_started = True
                        
                        # Engines already imported above
                        
                        # Use depth directly from request parameter
                        depth = depth_param
                        thread_logger.info(f"Using depth={depth} for parsing (requested: {depth_param})")
                        
                        # Prepare query
                        query = f"{keyword_param} купить"
                        
                        # Normalize source parameter (lowercase, strip whitespace)
                        source_normalized = str(source_param).lower().strip() if source_param else "google"
                        thread_logger.info(f"=== CREATING PAGES === Query: {query}, source (original): '{source_param}', source (normalized): '{source_normalized}', depth: {depth}")
                        
                        # Collect links from search engines with source tracking
                        # Use dict to track which source(s) found each URL
                        collected_links: Dict[str, Set[str]] = {}  # URL -> set of sources (google, yandex)
                        
                        # Run search engines in parallel (same approach as parser.py)
                        tasks = []
                        
                        # Create pages only for requested sources - USE STRICT EQUALITY TO PREVENT DUPLICATES
                        # Get current active page to restore focus later (if exists)
                        current_active_page = None
                        try:
                            # Try to get the currently active page in the context
                            pages = context.pages
                            if pages:
                                # Find the page that is currently active (has focus)
                                for p in pages:
                                    try:
                                        # Check if page is still valid and active
                                        if p.url and p.url != "about:blank":
                                            current_active_page = p
                                            break
                                    except:
                                        pass
                        except:
                            pass
                        
                        # Initialize parsing logs structure
                        parsing_logs = {}
                        
                        if source_normalized == "yandex":
                            thread_logger.info(">>> Creating ONLY Yandex page (source=yandex)")
                            yandex_page = await context.new_page()
                            thread_logger.info(f">>> Yandex page created")
                            # Возвращаем фокус на предыдущую активную страницу (если она есть)
                            if current_active_page:
                                try:
                                    await current_active_page.bring_to_front()
                                except:
                                    pass
                            yandex_engine = YandexEngine()
                            tasks.append(yandex_engine.parse(yandex_page, query, depth, collected_links, run_id_param, keyword_param, parsing_logs))
                        elif source_normalized == "google":
                            thread_logger.info(">>> Creating ONLY Google page (source=google)")
                            google_page = await context.new_page()
                            thread_logger.info(f">>> Google page created")
                            # Возвращаем фокус на предыдущую активную страницу (если она есть)
                            if current_active_page:
                                try:
                                    await current_active_page.bring_to_front()
                                except:
                                    pass
                            google_engine = GoogleEngine()
                            tasks.append(google_engine.parse(google_page, query, depth, collected_links, run_id_param, keyword_param, parsing_logs))
                        elif source_normalized == "both":
                            thread_logger.info(">>> Creating BOTH Yandex and Google pages (source=both)")
                            yandex_page = await context.new_page()
                            thread_logger.info(f">>> Yandex page created")
                            google_page = await context.new_page()
                            thread_logger.info(f">>> Google page created")
                            # Возвращаем фокус на предыдущую активную страницу (если она есть)
                            if current_active_page:
                                try:
                                    await current_active_page.bring_to_front()
                                except:
                                    pass
                            yandex_engine = YandexEngine()
                            tasks.append(yandex_engine.parse(yandex_page, query, depth, collected_links, run_id_param, keyword_param, parsing_logs))
                            google_engine = GoogleEngine()
                            tasks.append(google_engine.parse(google_page, query, depth, collected_links, run_id_param, keyword_param, parsing_logs))
                        else:
                            # Default to Google if source is invalid
                            thread_logger.warning(f">>> Invalid source '{source_normalized}', defaulting to Google")
                            google_page = await context.new_page()
                            thread_logger.info(f">>> Google page created (default)")
                            # Возвращаем фокус на предыдущую активную страницу (если она есть)
                            if current_active_page:
                                try:
                                    await current_active_page.bring_to_front()
                                except:
                                    pass
                            google_engine = GoogleEngine()
                            tasks.append(google_engine.parse(google_page, query, depth, collected_links, run_id_param, keyword_param, parsing_logs))
                        
                        thread_logger.info(f">>> TOTAL: Created {len(tasks)} task(s) for parsing")
                        
                        # Wait for all search engines to complete
                        if tasks:
                            thread_logger.info(f">>> [LOGS] About to start periodic logs sending for run_id: {run_id_param}")
                            # Запускаем задачи и периодически отправляем логи в backend
                            # Создаем задачу для периодической отправки логов
                            async def send_logs_periodically():
                                """Периодически отправляет логи в backend во время парсинга."""
                                send_count = 0
                                thread_logger.info(f"Starting periodic logs sending for run_id: {run_id_param}")
                                try:
                                    while True:
                                        await asyncio.sleep(2.5)  # Синхронизировано с rate limiting (2.5 сек)
                                        if parsing_logs:
                                            send_count += 1
                                            thread_logger.info(f"Attempting to send logs (attempt #{send_count}) for run_id: {run_id_param}")
                                            await parser._send_parsing_logs(run_id_param, parsing_logs)
                                        else:
                                            thread_logger.debug(f"No logs to send yet for run_id: {run_id_param}")
                                except asyncio.CancelledError:
                                    thread_logger.info(f"Periodic logs sending cancelled for run_id: {run_id_param}, total attempts: {send_count}")
                                    raise
                                except Exception as e:
                                    thread_logger.error(f"Error in periodic logs sending for run_id: {run_id_param}: {e}", exc_info=True)
                            
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
                                    await parser._send_parsing_logs(run_id_param, parsing_logs)
                        
                        # Return only collected URLs without parsing pages
                        # Convert collected links to supplier-like format (only URLs, no page parsing)
                        suppliers = []
                        for url, sources in collected_links.items():  # No limit - return all collected URLs
                            # Extract domain from URL
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
                        
                        # Return suppliers with parsing logs
                        return suppliers, parsing_logs
                    finally:
                        # Clean up
                        if browser:
                            await browser.close()
                        if playwright:
                            await playwright.stop()
                
                # Use asyncio.run() to create a new event loop with the correct policy
                # This is EXACTLY the same approach as test_browser_connection.py
                return asyncio.run(parse_async())
            
            # Run parsing in a separate thread
            current_loop = asyncio.get_running_loop()
            executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="parsing")
            try:
                logger.info("Running parsing in separate thread with asyncio.run() (Windows)...")
                result_tuple = await current_loop.run_in_executor(
                    executor,
                    run_parsing_in_thread,
                    request.keyword,
                    request.depth,
                    request.source,
                    settings.CHROME_CDP_URL,
                    request.run_id
                )
                # Handle both return formats (tuple with logs or just suppliers)
                if isinstance(result_tuple, tuple) and len(result_tuple) == 2:
                    suppliers, parsing_logs = result_tuple
                else:
                    suppliers = result_tuple if result_tuple else []
                    parsing_logs = {}
            finally:
                executor.shutdown(wait=False)
        else:
            # Non-Windows: run normally
            parser = Parser(settings.CHROME_CDP_URL)
            result_tuple = await parser.parse_keyword(
                keyword=request.keyword,
                depth=request.depth,
                source=request.source,
                run_id=request.run_id
            )
            # Handle both return formats (tuple with logs or just suppliers)
            if isinstance(result_tuple, tuple) and len(result_tuple) == 2:
                suppliers, parsing_logs = result_tuple
            else:
                suppliers = result_tuple if result_tuple else []
                parsing_logs = {}
        
        logger.info(f"Parse completed: found {len(suppliers)} suppliers")
        result = ParseResponse(
            keyword=request.keyword,
            suppliers=suppliers,
            total_found=len(suppliers),
            parsing_logs=parsing_logs if parsing_logs else None
        )
        return result
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except httpx.ConnectError as e:
        # Connection error to Chrome CDP or other services
        error_message = f"Cannot connect to Chrome CDP at {settings.CHROME_CDP_URL}. Please ensure Chrome is running with --remote-debugging-port=9222. Error: {str(e)}"
        logger.error(f"Connection error in parse_keyword: {error_message}")
        raise HTTPException(
            status_code=503,
            detail=error_message
        )
    except httpx.TimeoutException as e:
        # Timeout error
        error_message = f"Timeout while parsing. The operation took too long. Error: {str(e)}"
        logger.error(f"Timeout error in parse_keyword: {error_message}")
        raise HTTPException(
            status_code=504,
            detail=error_message
        )
    except Exception as e:
        error_traceback = traceback.format_exc()
        error_message = str(e) if e else "Unknown error"
        error_type = type(e).__name__
        
        logger.error(f"Error in parse_keyword ({error_type}): {error_message}\n{error_traceback}")
        
        # Provide more helpful error messages for common issues
        if "Chrome CDP" in error_message or "connect" in error_message.lower():
            detail_message = (
                f"Chrome CDP connection error: {error_message}\n\n"
                f"Please ensure:\n"
                f"1. Chrome is running with --remote-debugging-port=9222\n"
                f"2. Chrome CDP is accessible at {settings.CHROME_CDP_URL}\n"
                f"3. No firewall is blocking the connection"
            )
        elif "NotImplementedError" in error_type:
            detail_message = (
                f"Windows event loop error: {error_message}\n\n"
                f"This is a known Windows issue. The parser should handle this automatically, "
                f"but if it persists, please check the Windows event loop policy configuration."
            )
        else:
            # Return detailed error information for other errors
            detail_message = f"{error_type}: {error_message}"
            if error_traceback:
                detail_message += f"\n\nTraceback:\n{error_traceback}"
        
        raise HTTPException(
            status_code=500,
            detail=detail_message
        )
    finally:
        # Always remove from running requests, even on error
        parse_lock = get_parse_lock()
        async with parse_lock:
            _running_parse_requests.discard(request_key)
            logger.info(f"[DUPLICATE CHECK] Removed request '{request_key}' from running requests (remaining: {len(_running_parse_requests)})")

