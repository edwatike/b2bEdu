"""Search engines integration."""
import asyncio
import logging
import time
from typing import Set, List, Optional, Dict, Any
from datetime import datetime
from playwright.async_api import Page
from .human_behavior import (
    human_pause,
    very_human_behavior,
    light_human_behavior,
    wait_for_captcha,
    apply_stealth,
)

logger = logging.getLogger(__name__)


class SearchEngine:
    """Base class for search engines."""
    
    def __init__(self, name: str):
        self.name = name
    
    async def parse(self, page: Page, query: str, depth: int, collected_links: Dict[str, Set[str]], run_id: Optional[str] = None, keyword: Optional[str] = None, parsing_logs: Optional[Dict[str, Any]] = None):
        """Parse search results and collect links.
        
        Args:
            page: Playwright page object
            query: Search query
            depth: Number of pages to parse
            collected_links: Dictionary to store collected links (URL -> set of sources)
            run_id: Optional run ID for status updates
            keyword: Optional keyword for logging
            parsing_logs: Optional dictionary to store structured parsing logs
        """
        raise NotImplementedError


class YandexEngine(SearchEngine):
    """Yandex search engine parser."""
    
    def __init__(self):
        super().__init__("YANDEX")
    
    async def parse(self, page: Page, query: str, depth: int, collected_links: Dict[str, Set[str]], run_id: Optional[str] = None, keyword: Optional[str] = None, parsing_logs: Optional[Dict[str, Any]] = None):
        """Parse Yandex search results."""
        start_time = time.time()
        logger.info(f"{self.name}: Начало парсинга '{query}'")
        print(f"\n[*] {self.name}: Старт парсинга...")
        
        initial_count = len(collected_links)
        
        # Initialize parsing logs for this engine
        if parsing_logs is not None:
            if "yandex" not in parsing_logs:
                parsing_logs["yandex"] = {
                    "links_by_page": {},
                    "total_links": 0,
                    "last_links": [],  # Last 20 links found
                    "pages_processed": 0
                }
            yandex_logs = parsing_logs["yandex"]
        
        # Set additional headers for Yandex
        await page.set_extra_http_headers({
            'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not-A.Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
        })

        await apply_stealth(page)
        
        await human_pause(1, 2)
        
        # Сохраняем текущую активную страницу перед переходом
        current_active_page = None
        try:
            pages = page.context.pages
            for p in pages:
                if p != page and p.url and p.url != "about:blank":
                    current_active_page = p
                    break
        except:
            pass
        
        search_query = query.replace(" ", "+")
        base_url = f"https://yandex.ru/search/?text={search_query}&numdoc=50"
        await page.goto(
            base_url,
            wait_until="domcontentloaded",
            timeout=60000
        )
        
        # Возвращаем фокус на предыдущую активную страницу (если она есть)
        # Это предотвращает автоматическое переключение вкладки
        if current_active_page:
            try:
                await current_active_page.bring_to_front()
            except:
                pass
        
        # Wait a bit for page to fully load before checking CAPTCHA
        await asyncio.sleep(1)
        
        await wait_for_captcha(page, self.name, run_id)
        
        logger.info(f"{self.name}: Starting to parse {depth} page(s)")
        for n in range(1, depth + 1):
            print(f"[PAGE] {self.name}: страница {n}/{depth}")
            logger.info(f"{self.name}: Processing page {n} of {depth}, current URL: {page.url}")

            if n > 1:
                page_url = f"{base_url}&p={n - 1}"
                logger.info(f"{self.name}: Navigating to page {n} via {page_url}")
                await human_pause(1, 2)
                await page.goto(page_url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(0.5)
                await wait_for_captcha(page, self.name, run_id)

            await light_human_behavior(page)
            await human_pause(1, 2)
            await wait_for_captcha(page, self.name, run_id)
            
            # Try multiple selectors for Yandex links
            elems = page.locator("a.Link")
            count = await elems.count()
            
            # If no links found with "a.Link", try alternative selectors
            if count == 0:
                elems = page.locator("a[href^='http']")
                count = await elems.count()
            
            logger.info(f"{self.name}: Found {count} link elements on page {n}")
            
            for i in range(count):
                try:
                    href = await elems.nth(i).get_attribute("href")
                    if href and href.startswith("http") and ".ru" in href:
                        # Exclude Yandex internal links
                        if "yandex.ru/search" in href or "yandex.ru/_crpd" in href:
                            continue
                        # Exclude other search engines
                        if any(domain in href.lower() for domain in ["google", "youtube", "yandex"]):
                            continue
                        clean_url = href.split("?")[0].split("#")[0]
                        # Track source for each URL
                        is_new_url = clean_url not in collected_links
                        if is_new_url:
                            collected_links[clean_url] = set()
                        collected_links[clean_url].add("yandex")
                        logger.debug(f"{self.name}: Added link: {clean_url} (source: yandex)")
                        
                        # Add to parsing logs
                        if parsing_logs is not None and "yandex" in parsing_logs:
                            yandex_logs = parsing_logs["yandex"]
                            is_first_link = yandex_logs["total_links"] == 0
                            if n not in yandex_logs["links_by_page"]:
                                yandex_logs["links_by_page"][n] = 0
                            yandex_logs["links_by_page"][n] += 1
                            yandex_logs["total_links"] = len([url for url, sources in collected_links.items() if "yandex" in sources])
                            # Keep last 20 links
                            if clean_url not in yandex_logs["last_links"]:
                                yandex_logs["last_links"].append(clean_url)
                                if len(yandex_logs["last_links"]) > 20:
                                    yandex_logs["last_links"].pop(0)
                            # Логирование первой ссылки для проверки обновления логов
                            if is_first_link:
                                logger.info(f"{self.name}: First link found and added to logs: {clean_url}, page: {n}")
                except Exception as e:
                    logger.debug(f"{self.name}: Error extracting link {i}: {e}")
                    pass
            
            logger.info(f"{self.name}: Total collected so far: {len(collected_links)}")
            
            # Update pages processed in logs
            if parsing_logs is not None and "yandex" in parsing_logs:
                parsing_logs["yandex"]["pages_processed"] = n
            
            if n < depth:
                await human_pause(2, 4)
        
        elapsed = time.time() - start_time
        new_links = len(collected_links) - initial_count
        print(f"[OK] {self.name}: Собрано {new_links} ссылок за {elapsed:.1f} сек ({elapsed/60:.1f} мин)\n")
        logger.info(f"{self.name}: Завершено за {elapsed:.1f}с, собрано {new_links} ссылок")


class GoogleEngine(SearchEngine):
    """Google search engine parser."""
    
    def __init__(self):
        super().__init__("GOOGLE")
    
    async def parse(self, page: Page, query: str, depth: int, collected_links: Dict[str, Set[str]], run_id: Optional[str] = None, keyword: Optional[str] = None, parsing_logs: Optional[Dict[str, Any]] = None):
        """Parse Google search results."""
        start_time = time.time()
        logger.info(f"{self.name}: Начало парсинга '{query}'")
        print(f"\n[*] {self.name}: Старт парсинга...")
        
        initial_count = len(collected_links)
        
        # Initialize parsing logs for this engine
        if parsing_logs is not None:
            if "google" not in parsing_logs:
                parsing_logs["google"] = {
                    "links_by_page": {},
                    "total_links": 0,
                    "last_links": [],  # Last 20 links found
                    "pages_processed": 0
                }
            google_logs = parsing_logs["google"]
        
        print(f"[GOOGLE] Opening search page for: {query}")
        logger.info(f"{self.name}: Opening Google search for '{query}'")

        await apply_stealth(page)
        
        # Сохраняем текущую активную страницу перед переходом
        current_active_page = None
        try:
            pages = page.context.pages
            for p in pages:
                if p != page and p.url and p.url != "about:blank":
                    current_active_page = p
                    break
        except:
            pass
        
        await page.goto(
            f"https://www.google.com/search?q={query.replace(' ', '+')}&hl=ru",
            timeout=60000,
            wait_until="domcontentloaded"
        )
        
        # Возвращаем фокус на предыдущую активную страницу (если она есть)
        # Это предотвращает автоматическое переключение вкладки
        if current_active_page:
            try:
                await current_active_page.bring_to_front()
            except:
                pass
        
        print(f"[GOOGLE] Page loaded: {page.url}")
        logger.info(f"{self.name}: Page loaded: {page.url}")
        
        # Wait a bit for page to fully load before checking CAPTCHA
        await asyncio.sleep(1)
        
        # Wait for CAPTCHA to be solved if present
        await wait_for_captcha(page, self.name, run_id)
        
        # If we're on CAPTCHA page, wait for user to solve it
        max_captcha_wait = 300  # 5 minutes
        captcha_wait_start = time.time()
        while "/sorry" in page.url.lower() or "captcha" in page.url.lower():
            elapsed = time.time() - captcha_wait_start
            if elapsed > max_captcha_wait:
                print(f"[ERROR] {self.name}: CAPTCHA wait timeout after {max_captcha_wait}s")
                logger.error(f"{self.name}: CAPTCHA wait timeout")
                break
            
            print(f"[WAIT] {self.name}: Waiting for CAPTCHA to be solved... ({int(elapsed)}s / {max_captcha_wait}s)")
            await asyncio.sleep(3)
            try:
                await page.reload(wait_until="domcontentloaded", timeout=30000)
            except:
                pass
        
        if "/sorry" not in page.url.lower():
            print(f"[OK] {self.name}: CAPTCHA solved or not present, continuing...")
            logger.info(f"{self.name}: Ready to parse search results")
        
        logger.info(f"{self.name}: Starting to parse {depth} page(s)")
        for n in range(1, depth + 1):
            print(f"[PAGE] {self.name}: страница {n}/{depth}")
            logger.info(f"{self.name}: Processing page {n} of {depth}, current URL: {page.url}")
            
            await light_human_behavior(page)
            await wait_for_captcha(page, self.name, run_id)
            
            # Use simple approach like old parser - get all links
            elems = page.locator("a")
            count = await elems.count()
            print(f"[DEBUG] {self.name}: Found {count} total links on page")
            logger.info(f"{self.name}: Found {count} total links on page")
            
            for i in range(count):
                try:
                    href = await elems.nth(i).get_attribute("href")
                    if href:
                        # Clean href - remove Google redirect parameters
                        if href.startswith("/url?q="):
                            import urllib.parse
                            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                            if "q" in parsed:
                                href = parsed["q"][0]
                        
                        # Filter: must be http/https, contain .ru, not be Google/Youtube
                        if (href and href.startswith("http") and 
                            ".ru" in href and 
                            "google" not in href.lower() and
                            "youtube" not in href.lower()):
                            clean_href = href.split("&")[0].split("?")[0]
                            # Track source for each URL
                            is_new_url = clean_href not in collected_links
                            if is_new_url:
                                collected_links[clean_href] = set()
                            collected_links[clean_href].add("google")
                            print(f"[FOUND] {self.name}: {clean_href}")
                            logger.info(f"{self.name}: Found link: {clean_href} (source: google)")
                            
                            # Add to parsing logs
                            if parsing_logs is not None and "google" in parsing_logs:
                                google_logs = parsing_logs["google"]
                                is_first_link = google_logs["total_links"] == 0
                                if n not in google_logs["links_by_page"]:
                                    google_logs["links_by_page"][n] = 0
                                google_logs["links_by_page"][n] += 1
                                google_logs["total_links"] = len([url for url, sources in collected_links.items() if "google" in sources])
                                # Keep last 20 links
                                if clean_href not in google_logs["last_links"]:
                                    google_logs["last_links"].append(clean_href)
                                    if len(google_logs["last_links"]) > 20:
                                        google_logs["last_links"].pop(0)
                                # Логирование первой ссылки для проверки обновления логов
                                if is_first_link:
                                    logger.info(f"{self.name}: First link found and added to logs: {clean_href}, page: {n}")
                except Exception as e:
                    logger.debug(f"Error extracting link {i}: {e}")
                    pass
            
            print(f"[INFO] {self.name}: Total links collected so far: {len(collected_links)}")
            logger.info(f"{self.name}: Total links collected so far: {len(collected_links)}")
            
            # Update pages processed in logs
            if parsing_logs is not None and "google" in parsing_logs:
                parsing_logs["google"]["pages_processed"] = n
            
            if n < depth:
                next_btn = page.locator("a#pnnext")
                if await next_btn.count() == 0:
                    break
                
                await human_pause(2, 5)
                await next_btn.click()
                await wait_for_captcha(page, self.name, run_id)
        
        elapsed = time.time() - start_time
        new_links = len(collected_links) - initial_count
        print(f"[OK] {self.name}: Собрано {new_links} ссылок за {elapsed:.1f} сек ({elapsed/60:.1f} мин)\n")
        logger.info(f"{self.name}: Завершено за {elapsed:.1f}с, собрано {new_links} ссылок")


# Legacy functions for backward compatibility
async def search_google(keyword: str, max_results: int = 10) -> List[str]:
    """Legacy function - returns empty list. Use GoogleEngine.parse() instead."""
    logger.warning("search_google() is deprecated. Use GoogleEngine.parse() instead.")
    return []


async def search_yandex(keyword: str, max_results: int = 10) -> List[str]:
    """Legacy function - returns empty list. Use YandexEngine.parse() instead."""
    logger.warning("search_yandex() is deprecated. Use YandexEngine.parse() instead.")
    return []


async def search_combined(keyword: str, max_results: int = 10) -> List[str]:
    """Legacy function - returns empty list. Use both engines separately instead."""
    logger.warning("search_combined() is deprecated. Use both engines separately instead.")
    return []

