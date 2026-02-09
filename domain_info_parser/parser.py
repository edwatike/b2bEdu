"""Domain Info Parser - извлекает ИНН и email с веб-страниц.

Multi-strategy approach:
  Tier 1: HTTP probe (httpx) — fast, no browser
  Tier 2: API sniff (__NEXT_DATA__, JSON-LD, embedded JSON)
  Tier 3: Playwright browser — only when Tier 1+2 fail
"""
import re
import asyncio
import json
import time
import tempfile
import os
from typing import Optional, Dict, List
from urllib.parse import urljoin, urlparse
import logging

import httpx
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeout

# Ensure we can import local modules even when running from backend
import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from learning_engine import LearningEngine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DomainInfoParser:
    """Парсер для извлечения ИНН и email с доменов."""
    
    def __init__(self, headless: bool = True, timeout: int = 15000):
        """
        Args:
            headless: Запускать браузер в headless режиме
            timeout: Таймаут загрузки страницы в миллисекундах
        """
        self.headless = headless
        self.timeout = timeout
        self.browser: Optional[Browser] = None
        self.playwright = None
        self.learning_engine = LearningEngine()

    def _build_priority_urls(self, domain: str, base_url: str) -> List[str]:
        """Build priority URLs based on learned patterns."""
        if not self.learning_engine:
            return []

        try:
            priority_items = self.learning_engine.get_priority_urls(domain, data_type="both")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка чтения паттернов обучения: {e}")
            return []

        priority_urls: List[str] = []
        base_netloc = urlparse(base_url).netloc.lower()
        if base_netloc.startswith("www."):
            base_netloc = base_netloc[4:]
        for item in priority_items:
            if not item:
                continue
            item_str = str(item).strip()
            if not item_str:
                continue
            if item_str.startswith("http://") or item_str.startswith("https://"):
                url = item_str
            elif item_str.startswith("/"):
                url = urljoin(base_url, item_str)
            else:
                url = urljoin(base_url, f"/{item_str}")
            cand_netloc = urlparse(url).netloc.lower()
            if cand_netloc.startswith("www."):
                cand_netloc = cand_netloc[4:]
            if cand_netloc == base_netloc or cand_netloc.endswith(f".{base_netloc}"):
                priority_urls.append(url)

        return list(dict.fromkeys(priority_urls))
        
    async def start(self):
        """Запустить браузер."""
        logger.info("Запуск Playwright...")
        self.playwright = await async_playwright().start()
        # Используем обычный запуск браузера вместо COMET CDP
        self.browser = await self.playwright.chromium.launch(headless=True)
        logger.info("✅ Браузер запущен (Playwright)")
        
    async def close(self):
        """Закрыть браузер."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("✅ Браузер закрыт")
    
    def extract_inn(self, text: str, html: str = "") -> Optional[str]:
        """Извлечь ИНН из текста и HTML с улучшенными паттернами."""
        # Расширенные паттерны для поиска ИНН с контекстом
        inn_patterns = [
            # КРИТИЧНО: Формат ИНН/КПП с косой чертой (самый частый случай!)
            r'ИНН[/\s]*КПП[:\s]*(\d{10})[/\s]+\d{9}',  # ИНН/КПП: 7703412988/772001001
            r'ИНН[/\s]*КПП[:\s\n]+(\d{10})[\s/]+\d{9}',  # ИНН/КПП 7703412988/772001001
            r'(?:ИНН|INN)[/\s]*(?:КПП|KPP)[:\s]*(\d{10})[/\s]+\d{9}',  # INN/KPP: 7703412988/772001001
            
            # Прямое упоминание ИНН (с учетом пробелов и переносов)
            r'ИНН[:\s\n]+(\d{10}|\d{12})',
            r'INN[:\s\n]+(\d{10}|\d{12})',
            r'инн[:\s\n]+(\d{10}|\d{12})',
            
            # С разделителями (любые комбинации цифр с пробелами/дефисами)
            r'ИНН[:\s\n]+(\d{4}[\s\-\n]?\d{6})',  # ИНН: 1234 567890
            r'ИНН[:\s\n]+(\d{4}[\s\-\n]?\d{4}[\s\-\n]?\d{4})',  # ИНН: 1234 5678 9012
            r'ИНН[:\s\n]+(\d{2}[\s\-]\d{3}[\s\-]\d{3}[\s\-]\d{2})',  # ИНН: 78 393 394 21
            r'ИНН[:\s\n]+(\d[\s\-]?\d[\s\-]?\d[\s\-]?\d[\s\-]?\d[\s\-]?\d[\s\-]?\d[\s\-]?\d[\s\-]?\d[\s\-]?\d)',  # ИНН с любыми пробелами между цифрами
            r'INN[:\s\n]+(\d[\s\-]?\d[\s\-]?\d[\s\-]?\d[\s\-]?\d[\s\-]?\d[\s\-]?\d[\s\-]?\d[\s\-]?\d[\s\-]?\d)',  # INN с пробелами
            
            # В таблицах/реквизитах
            r'(?:реквизит|requisite|details|юридическ).*?ИНН[:\s\n]*(\d{10}|\d{12})',
            r'(?:реквизит|requisite|details|legal).*?INN[:\s\n]*(\d{10}|\d{12})',
            
            # Рядом с ОГРН/КПП
            r'(?:ОГРН|OGRN)[:\s\n]+\d+.*?ИНН[:\s\n]*(\d{10}|\d{12})',
            r'(?:КПП|KPP)[:\s\n]+\d+.*?ИНН[:\s\n]*(\d{10}|\d{12})',
            
            # В контактах/о компании
            r'(?:о компании|about|контакт|contact|company).*?ИНН[:\s\n]*(\d{10}|\d{12})',
            
            # В футере
            r'(?:footer|подвал).*?ИНН[:\s\n]*(\d{10}|\d{12})',
        ]
        
        # Ищем с явным упоминанием ИНН в тексте
        for pattern in inn_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                # Убираем пробелы, дефисы и переносы
                clean_match = re.sub(r'[\s\-\n]', '', match)
                if len(clean_match) in [10, 12]:
                    logger.info(f"Found INN with pattern in text: {clean_match}")
                    return clean_match
        
        # Ищем в HTML (если предоставлен)
        if html:
            # Поиск в meta-тегах
            meta_patterns = [
                r'<meta[^>]*name=["\']inn["\'][^>]*content=["\'](\d{10}|\d{12})["\']',
                r'<meta[^>]*property=["\']inn["\'][^>]*content=["\'](\d{10}|\d{12})["\']',
                r'<meta[^>]*content=["\'](\d{10}|\d{12})["\'][^>]*name=["\']inn["\']',
            ]
            
            for pattern in meta_patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                if matches:
                    logger.info(f"Found INN in meta tag: {matches[0]}")
                    return matches[0]
            
            # Поиск в data-атрибутах
            data_patterns = [
                r'data-inn=["\'](\d{10}|\d{12})["\']',
                r'data-company-inn=["\'](\d{10}|\d{12})["\']',
            ]
            
            for pattern in data_patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                if matches:
                    logger.info(f"Found INN in data attribute: {matches[0]}")
                    return matches[0]
            
            # Поиск в HTML с явным упоминанием ИНН
            for pattern in inn_patterns:
                matches = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    clean_match = re.sub(r'[\s\-\n]', '', match)
                    if len(clean_match) in [10, 12]:
                        logger.info(f"Found INN with pattern in HTML: {clean_match}")
                        return clean_match
            
            # Поиск в JavaScript-контенте (переменные, объекты, JSON)
            js_patterns = [
                r'["\']inn["\']\s*:\s*["\']?(\d{10}|\d{12})["\']?',  # "inn": "7820067929"
                r'inn\s*=\s*["\']?(\d{10}|\d{12})["\']?',  # inn = "7820067929"
                r'companyInn["\']?\s*:\s*["\']?(\d{10}|\d{12})["\']?',  # companyInn: "7820067929"
                r'data\.inn\s*=\s*["\']?(\d{10}|\d{12})["\']?',  # data.inn = "7820067929"
                r'"tax_id"\s*:\s*"(\d{10}|\d{12})"',  # "tax_id": "7820067929"
                r'"company_id"\s*:\s*"(\d{10}|\d{12})"',  # "company_id": "7820067929"
                r'"ogrn"\s*:\s*"(\d{13})"[^}]*"inn"\s*:\s*"(\d{10}|\d{12})"',  # ОГРН + ИНН в JSON
                r'"kpp"\s*:\s*"\d{9}"[^}]*"inn"\s*:\s*"(\d{10}|\d{12})"',  # КПП + ИНН в JSON
                r'ИНН\s*[:\=]\s*["\']?(\d{10}|\d{12})["\']?',  # ИНН: "7820067929"
                r'ИНН\s*[:\=]\s*(\d{10}|\d{12})',  # ИНН: 7820067929
            ]
            
            for pattern in js_patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                if matches:
                    logger.info(f"Found INN in JavaScript content: {matches[0]}")
                    return matches[0]
            
            # УБРАЛ: АГРЕССИВНЫЙ ПОИСК - искал любые 10/12-значные числа в HTML рядом со словами ИНН/INN
# УБРАЛ: context_patterns - искал числа в контексте реквизитов без явного "ИНН"
        
        # Если не нашли с явным упоминанием, ищем 10 или 12 цифр подряд
        # но только если они окружены пробелами или знаками препинания ИЛИ рядом с ИНН
        # БОЛЕЕ СТРОГИЙ ПОДХОД: не берем просто числа из HTML без контекста
        general_pattern = r'(?<!\d)(\d{10}|\d{12})(?!\d)'
        matches = re.findall(general_pattern, text)
        
        # Фильтруем: исключаем телефоны и другие числа
        for match in matches:
            # Проверяем, что это не телефон (не начинается с 7, 8, 9)
            if len(match) == 10 and not match.startswith(('7', '8', '9')):
                # ДОП. ПРОВЕРКА: ищем "ИНН" рядом с этим числом в тексте
                inn_context = re.search(r'.{0,30}' + re.escape(match) + '.{0,30}', text, re.IGNORECASE)
                if inn_context and ('ИНН' in inn_context.group() or 'INN' in inn_context.group()):
                    logger.info(f"Found INN with context in text: {match}")
                    return match
            elif len(match) == 12:
                # Для 12-значных ИНН (ИП) проверяем, что не начинается с 79 (телефон)
                if not match.startswith('79'):
                    # ДОП. ПРОВЕРКА: ищем "ИНН" рядом с этим числом в тексте
                    inn_context = re.search(r'.{0,30}' + re.escape(match) + '.{0,30}', text, re.IGNORECASE)
                    if inn_context and ('ИНН' in inn_context.group() or 'INN' in inn_context.group()):
                        logger.info(f"Found INN with context in text: {match}")
                        return match
        
        # Дополнительный поиск: ищем 10-значные числа рядом с 13-значными (ОГРН) - ТОЛЬКО с контекстом ИНН
        # УБРАЛ: ogrn_inn_pattern - искал любые числа рядом с ОГРН
        
        # Поиск в HTML с возможной проблемой кодировки
        if html:
            # Ищем ИНН рядом со словом ИНН (даже если кириллица неправильно декодирована)
            # Ищем паттерны: ИНН + 10 цифр ИЛИ 10 цифр + ИНН
            inn_context_patterns = [
                r'(?:\xd0\x98\xd0\x9d\xd0\x9d|\xd0\x98\xd0\xbd\xd0\xbd|\xd0\xb8\xd0\xbd\xd0\xbd|\xd0\x98\xd0\xbd\xd0\xbd|\xd0\x98\xd0\x9d\xd0\x9d)[^\d]{0,20}(\d{10})',  # Неправильно декодированное "ИНН"
                r'(\d{10})[^\d]{0,20}(?:\xd0\x98\xd0\x9d\xd0\x9d|\xd0\x98\xd0\xbd\xd0\xbd|\xd0\xb8\xd0\xbd\xd0\xbd|\xd0\x98\xd0\xbd\xd0\xbd|\xd0\x98\xd0\x9d\xd0\x9d)',  # Число перед "ИНН"
                r'(?:\xd0\x9a\xd0\x9a\xd0\x9f|\xd0\xba\xd0\xba\xd0\xbf)[^\d]{0,20}\d{9}[^\d]{0,20}(\d{10})',  # КПП + ИНН
                r'(\d{10})[^\d]{0,20}\d{9}[^\d]{0,20}(?:\xd0\x9a\xd0\x9a\xd0\x9f|\xd0\xba\xd0\xba\xd0\xbf)',  # ИНН + КПП
            ]
            
            for pattern in inn_context_patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0] if match[0] else match[1]
                    if len(match) == 10 and not match.startswith(('7', '8', '9')):
                        logger.info(f"Found INN with context in HTML: {match}")
                        return match
            
            # Если не нашли с контекстом, НЕ ищем любые 10-значные числа в HTML
            # Это исключает ID элементов и другие технические числа
            # ИНН должен быть найден только с контекстом "ИНН" или на контактных страницах
            
            # Поиск ИНН в HTML-таблицах: <th>ИНН</th><td>1234567890</td> или <td>ИНН</td><td>1234567890</td>
            table_inn_patterns = [
                # th/td с текстом ИНН, затем td с числом (с возможными пробелами)
                r'<t[hd][^>]*>\s*ИНН\s*</t[hd]>\s*<td[^>]*>\s*([\d\s\-]{10,16})\s*</td>',
                r'<t[hd][^>]*>[^<]*ИНН[^<]*</t[hd]>\s*<td[^>]*>\s*([\d\s\-]{10,16})\s*</td>',
                # Вариант с rowheader
                r'rowheader[^>]*>\s*ИНН\s*</[^>]+>\s*<[^>]*>\s*([\d\s\-]{10,16})\s*<',
                # ИНН в одной ячейке: "ИНН: 1234567890" или "ИНН 1234567890"
                r'<td[^>]*>[^<]*ИНН[:\s]+([\d\s\-]{10,16})[^<]*</td>',
                # dt/dd формат
                r'<dt[^>]*>[^<]*ИНН[^<]*</dt>\s*<dd[^>]*>\s*([\d\s\-]{10,16})\s*</dd>',
            ]
            for pattern in table_inn_patterns:
                matches = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    clean = re.sub(r'[\s\-]', '', match)
                    if len(clean) in [10, 12] and not clean.startswith(('7', '8', '9')):
                        logger.info(f"Found INN in HTML table: {clean}")
                        return clean
                    elif len(clean) in [10, 12]:
                        # Даже если начинается с 7/8/9 — в таблице с заголовком ИНН это точно ИНН
                        logger.info(f"Found INN in HTML table (starts with 7/8/9): {clean}")
                        return clean
        
        # Последний шанс: ищем 10 цифр (с пробелами) рядом с КПП/ОГРН (без явного "ИНН")
        if text:
            kpp_inn_patterns = [
                r'КПП[:\s]+\d{9}[\s,;/]+([\d\s\-]{10,16})',  # КПП: 123456789 / 1234567890
                r'([\d\s\-]{10,16})[\s,;/]+КПП[:\s]+\d{9}',  # 1234567890 / КПП: 123456789
                r'ОГРН[:\s]+\d{13}[\s,;/]+([\d\s\-]{10,16})',  # ОГРН + число
            ]
            for pattern in kpp_inn_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    clean = re.sub(r'[\s\-]', '', match)
                    if len(clean) in [10, 12]:
                        logger.info(f"Found INN near KPP/OGRN: {clean}")
                        return clean
        
        logger.info("No INN found in text")
        return None
    
    def extract_emails(self, text: str) -> List[str]:
        """Извлечь email адреса из текста."""
        pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(pattern, text)
        
        # Фильтруем: исключаем общие email-адреса типа example@example.com
        filtered = []
        exclude_patterns = ['example', 'test', 'domain', 'email', 'yoursite', 'yourdomain']
        
        for email in emails:
            email_lower = email.lower()
            if not any(pattern in email_lower for pattern in exclude_patterns):
                filtered.append(email)
        
        return list(set(filtered))  # Убираем дубликаты
    
    def extract_emails_from_html(self, html: str) -> List[str]:
        """Извлечь email адреса из HTML (включая mailto)."""
        if not html:
            return []

        mailto_pattern = r'mailto:([^"\'\s>]+)'
        emails = re.findall(mailto_pattern, html, re.IGNORECASE)
        cleaned = [email.split("?")[0] for email in emails]
        return list(set(self.extract_emails(" ".join(cleaned))))

    def _is_pdf_url(self, url: str) -> bool:
        """Check if URL points to a PDF file."""
        parsed = urlparse(url)
        return parsed.path.lower().endswith('.pdf')

    async def download_and_parse_pdf(self, url: str) -> Dict:
        """Download PDF and extract INN/email from it.
        
        Returns:
            Dict with keys: text, inn, emails, error
        """
        result = {"text": "", "inn": None, "emails": [], "error": None}
        tmp_path = None
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")
                if len(resp.content) > 10_000_000:  # 10MB limit
                    result["error"] = "PDF слишком большой (>10MB)"
                    return result

            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(resp.content)
                tmp_path = f.name

            # Extract text with PyMuPDF (fitz)
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(tmp_path)
                pages_text = []
                for page_num in range(min(doc.page_count, 10)):  # max 10 pages
                    page = doc[page_num]
                    pages_text.append(page.get_text())
                doc.close()
                full_text = "\n".join(pages_text)
                result["text"] = full_text
            except Exception as e:
                # Fallback to PyPDF2
                try:
                    from PyPDF2 import PdfReader
                    reader = PdfReader(tmp_path)
                    pages_text = []
                    for page_num in range(min(len(reader.pages), 10)):
                        pages_text.append(reader.pages[page_num].extract_text() or "")
                    full_text = "\n".join(pages_text)
                    result["text"] = full_text
                except Exception as e2:
                    result["error"] = f"Не удалось прочитать PDF: {e2}"
                    return result

            # Extract INN and emails from PDF text
            if result["text"]:
                result["inn"] = self.extract_inn(result["text"])
                result["emails"] = self.extract_emails(result["text"])
                if result["inn"]:
                    logger.info(f"  ✅ ИНН найден в PDF: {result['inn']}")
                if result["emails"]:
                    logger.info(f"  ✅ Email найден в PDF: {result['emails']}")

        except httpx.HTTPStatusError as e:
            result["error"] = f"HTTP {e.response.status_code}"
        except Exception as e:
            result["error"] = str(e)[:200]
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
        return result

    async def goto_with_fallback(self, page: Page, url: str) -> None:
        """Открыть страницу, при ошибке HTTPS попробовать HTTP."""
        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=self.timeout)
            return
        except Exception as e:
            err_str = str(e).lower()
            # If it's a download (PDF), don't retry with HTTP
            if 'download' in err_str:
                raise
            if url.startswith("https://"):
                fallback_url = "http://" + url[len("https://") :]
                logger.warning(f"  ⚠️ HTTPS не удалось, пробуем HTTP: {fallback_url}")
                await page.goto(fallback_url, wait_until='domcontentloaded', timeout=self.timeout)
                return
            raise e
    
    async def get_page_text(self, page: Page) -> str:
        """Получить весь текст со страницы, включая таблицы и скрытые элементы."""
        try:
            text = await page.evaluate('''() => {
                let result = document.body.innerText || '';
                
                // Дополнительно извлекаем текст из таблиц с разделителями
                const tables = document.querySelectorAll('table');
                for (const table of tables) {
                    const rows = table.querySelectorAll('tr');
                    for (const row of rows) {
                        const cells = row.querySelectorAll('th, td');
                        const cellTexts = Array.from(cells).map(c => c.innerText.trim()).filter(t => t);
                        if (cellTexts.length > 0) {
                            result += '\\n' + cellTexts.join(': ');
                        }
                    }
                }
                
                // Извлекаем текст из dt/dd списков
                const dts = document.querySelectorAll('dt');
                for (const dt of dts) {
                    const dd = dt.nextElementSibling;
                    if (dd && dd.tagName === 'DD') {
                        result += '\\n' + dt.innerText.trim() + ': ' + dd.innerText.trim();
                    }
                }
                
                return result;
            }''')
            return text
        except Exception as e:
            logger.warning(f"Ошибка получения текста страницы: {e}")
            return ""
    
    async def find_contact_pages(self, page: Page, base_url: str) -> List[str]:
        """Найти страницы с контактами."""
        # Расширенные ключевые слова для поиска страниц с реквизитами
        contact_keywords = [
            'контакт', 'contact', 'о компании', 'компани', 'about', 
            'реквизит', 'реквизиты', 'requisites',
            'politics', 'company', 'юридическ', 'legal', 'details', 'информация',
            'юр. лиц', 'юрлиц', 'оптов', 'поставщик', 'партнер',
            'сотрудничеств', 'карточка предприятия', 'сведения',
        ]
        # Ключевые слова в URL
        url_keywords = [
            'contact', 'about', 'requisites', 'requisite', 'requizit', 'requisiti',
            'politics', 'company', 'legal', 'details', 'o-kompanii', 'kompanii', 
            'rekvizit', 'rekvizity', 'kontakt', 'kontakty', 'ur-lic', 'yurlits',
            'opt', 'partner', 'sotrudnich', 'kartochka', 'svedeniya',
            'about-us', 'about_us', 'info',
        ]
        contact_urls = []
        
        try:
            # Получаем все ссылки на странице
            links = await page.evaluate('''() => {
                return Array.from(document.querySelectorAll('a[href]')).map(a => ({
                    href: a.href,
                    text: a.innerText.toLowerCase()
                }));
            }''')
            
            for link in links:
                href = link['href']
                text = link['text']
                href_lower = href.lower()
                text_lower = text.lower()
                
                # Проверяем текст ссылки ИЛИ URL (частичное совпадение)
                text_match = any(keyword in text_lower for keyword in contact_keywords)
                url_match = any(keyword in href_lower for keyword in url_keywords)
                
                if text_match or url_match:
                    # Преобразуем в абсолютный URL
                    full_url = urljoin(base_url, href)
                    # Проверяем, что это тот же домен
                    if urlparse(full_url).netloc == urlparse(base_url).netloc:
                        contact_urls.append(full_url)
            
        except Exception as e:
            logger.warning(f"Ошибка поиска контактных страниц: {e}")
        
        return list(set(contact_urls))[:5]  # Максимум 5 страниц
    
    # ─── HTTP-first Strategy (Tier 1 & 2) ───────────────────────────────

    _HTTP_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    def _detect_js_required(self, html: str, status_code: int = 200, headers: dict = None) -> bool:
        """Определить, требуется ли JS-рендеринг для данной страницы."""
        if not html or len(html.strip()) < 500:
            return True
        headers = headers or {}
        hdr_str = str(headers).lower()
        html_lower = html.lower()
        if 'cf-ray' in hdr_str or 'cloudflare' in hdr_str:
            if status_code in (403, 503) or 'challenge' in html_lower:
                return True
        body_text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        body_text = re.sub(r'<style[^>]*>.*?</style>', '', body_text, flags=re.DOTALL | re.IGNORECASE)
        body_text = re.sub(r'<[^>]+>', '', body_text).strip()
        spa_markers = ['<div id="app"></div>', '<div id="root"></div>',
                       '<div id="__next"></div>', '<div id="__nuxt">']
        if len(body_text) < 200 and any(m in html_lower for m in spa_markers):
            return True
        return False

    def _sniff_embedded_data(self, html: str) -> Dict:
        """Tier 2: Извлечь ИНН/email из встроенных данных (__NEXT_DATA__, JSON-LD, etc)."""
        result: Dict = {"inn": None, "emails": [], "source": None}
        if not html:
            return result

        # 1. __NEXT_DATA__
        next_match = re.search(
            r'<script\s+id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL
        )
        if next_match:
            try:
                data = json.loads(next_match.group(1))
                text_dump = json.dumps(data, ensure_ascii=False)
                inn = self.extract_inn(text_dump)
                emails = self.extract_emails(text_dump)
                if inn:
                    result["inn"] = inn
                    result["source"] = "__NEXT_DATA__"
                if emails:
                    result["emails"] = emails
                    result["source"] = result["source"] or "__NEXT_DATA__"
            except Exception:
                pass

        # 2. __NUXT__
        if not result["inn"]:
            nuxt_match = re.search(
                r'window\.__NUXT__\s*=\s*(\{.*?\});?\s*</script>', html, re.DOTALL
            )
            if nuxt_match:
                try:
                    text_dump = nuxt_match.group(1)
                    inn = self.extract_inn(text_dump)
                    emails = self.extract_emails(text_dump)
                    if inn:
                        result["inn"] = inn
                        result["source"] = "__NUXT__"
                    if emails and not result["emails"]:
                        result["emails"] = emails
                except Exception:
                    pass

        # 3. JSON-LD (schema.org)
        if not result["inn"]:
            ld_matches = re.findall(
                r'<script\s+type="application/ld\+json"[^>]*>(.*?)</script>',
                html, re.DOTALL,
            )
            for ld_text in ld_matches:
                if result["inn"]:
                    break
                try:
                    ld_data = json.loads(ld_text)
                    text_dump = json.dumps(ld_data, ensure_ascii=False)
                    inn = self.extract_inn(text_dump)
                    emails = self.extract_emails(text_dump)
                    if inn:
                        result["inn"] = inn
                        result["source"] = "json-ld"
                    if emails and not result["emails"]:
                        result["emails"] = emails
                except Exception:
                    pass

        return result

    def _extract_contact_links_from_html(self, html: str, base_url: str) -> List[str]:
        """Извлечь ссылки на контактные страницы из raw HTML (без Playwright)."""
        contact_urls: List[str] = []
        link_pattern = r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>'
        links = re.findall(link_pattern, html, re.IGNORECASE | re.DOTALL)

        contact_kw = [
            'контакт', 'contact', 'о компании', 'about', 'реквизит',
            'requisit', 'company', 'юридическ', 'legal', 'details',
            'rekvizit', 'kontakt', 'info',
        ]
        url_kw = [
            'contact', 'about', 'requisit', 'company', 'legal',
            'rekvizit', 'kontakt', 'o-kompanii', 'info', 'details',
        ]
        base_netloc = urlparse(base_url).netloc

        for href, text in links:
            text_clean = re.sub(r'<[^>]+>', '', text).strip().lower()
            href_lower = href.lower()
            if any(kw in text_clean for kw in contact_kw) or \
               any(kw in href_lower for kw in url_kw):
                full_url = urljoin(base_url, href)
                if urlparse(full_url).netloc == base_netloc:
                    contact_urls.append(full_url)

        return list(dict.fromkeys(contact_urls))[:5]

    def _html_to_text(self, html: str) -> str:
        """Быстрое преобразование HTML в текст (без Playwright)."""
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    async def _http_probe_page(self, client: httpx.AsyncClient, url: str) -> Dict:
        """HTTP GET одной страницы, извлечь ИНН/email без браузера."""
        page_result: Dict = {
            "url": url, "inn": None, "emails": [], "error": None, "strategy": "http",
        }
        try:
            resp = await client.get(url)
            if resp.status_code not in (200, 301, 302):
                page_result["error"] = f"HTTP {resp.status_code}"
                return page_result
            html = resp.text
            actual_url = str(resp.url)
            page_result["url"] = actual_url

            text = self._html_to_text(html)
            inn = self.extract_inn(text, html)
            emails = self.extract_emails(text)
            emails.extend(self.extract_emails_from_html(html))
            emails = list(set(emails))

            if inn:
                page_result["inn"] = inn
            if emails:
                page_result["emails"] = emails

            # Tier 2: embedded data sniff
            if not inn:
                sniffed = self._sniff_embedded_data(html)
                if sniffed["inn"]:
                    page_result["inn"] = sniffed["inn"]
                    page_result["strategy"] = f"api_sniff:{sniffed['source']}"
                if sniffed["emails"] and not page_result["emails"]:
                    page_result["emails"] = sniffed["emails"]

            return page_result
        except Exception as e:
            page_result["error"] = str(e)[:200]
            return page_result

    async def _http_probe_domain(self, domain: str) -> Dict:
        """
        Tier 1+2: Попытка извлечь ИНН/email через HTTP (без Playwright).
        Возвращает результат. Если inn найден — Playwright не нужен.
        """
        t0 = time.monotonic()

        result: Dict = {
            'domain': domain,
            'inn': None,
            'emails': [],
            'source_urls': [],
            'error': None,
            'extraction_log': [],
            'strategy': 'http',
            'strategy_time_ms': 0,
            'js_required': False,
        }

        url = f"https://{domain}" if not domain.startswith('http') else domain
        base_url = url

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(connect=5.0, read=8.0, write=5.0, pool=5.0),
                follow_redirects=True,
                headers=self._HTTP_HEADERS,
                verify=False,
            ) as client:
                # --- Main page ---
                main = await self._http_probe_page(client, url)
                result['source_urls'].append(main["url"])
                result['extraction_log'].append({
                    "url": main["url"],
                    "inn_found": main["inn"],
                    "emails_found": main["emails"],
                    "strategy": main["strategy"],
                })

                if main.get("error") and "403" in str(main["error"]):
                    result['js_required'] = True

                if main["inn"]:
                    result['inn'] = main["inn"]
                    result['strategy'] = main["strategy"]
                if main["emails"]:
                    result['emails'] = list(set(main["emails"]))

                # Early exit if INN found
                if result['inn'] and result['emails']:
                    result['strategy_time_ms'] = int((time.monotonic() - t0) * 1000)
                    logger.info(
                        f"  ⚡ HTTP Tier1+2: ИНН+Email найдены без Playwright за "
                        f"{result['strategy_time_ms']}ms"
                    )
                    return result

                # --- Contact pages via HTTP ---
                # Get main page HTML for link extraction
                try:
                    main_resp = await client.get(url)
                    main_html = main_resp.text if main_resp.status_code == 200 else ""
                except Exception:
                    main_html = ""

                contact_urls = self._extract_contact_links_from_html(main_html, base_url)

                # Add common paths (including nested paths like /about/requisites/)
                common_paths = [
                    '/contacts', '/about', '/requisites', '/company',
                    '/kontakty', '/o-kompanii', '/rekvizity', '/legal',
                    '/info', '/rekvizity/', '/contacts/', '/about/',
                    '/about/requisites', '/about/requisites/', '/about/contacts',
                    '/about/contacts/', '/pages/requisites', '/about/company',
                ]
                for path in common_paths:
                    test_url = urljoin(base_url, path)
                    if test_url not in contact_urls:
                        contact_urls.append(test_url)

                for contact_url in contact_urls[:15]:
                    if result['inn'] and result['emails']:
                        break
                    cp = await self._http_probe_page(client, contact_url)
                    if cp.get("error"):
                        continue
                    result['source_urls'].append(cp["url"])
                    result['extraction_log'].append({
                        "url": cp["url"],
                        "inn_found": cp["inn"],
                        "emails_found": cp["emails"],
                        "strategy": cp["strategy"],
                    })
                    if cp["inn"] and not result['inn']:
                        result['inn'] = cp["inn"]
                        result['strategy'] = cp["strategy"]
                    if cp["emails"] and not result['emails']:
                        result['emails'] = list(set(cp["emails"]))

        except Exception as e:
            result['error'] = str(e)[:200]
            logger.warning(f"  ⚠️ HTTP probe failed for {domain}: {e}")

        result['strategy_time_ms'] = int((time.monotonic() - t0) * 1000)

        if result['inn']:
            logger.info(
                f"  ⚡ HTTP: ИНН найден без Playwright за {result['strategy_time_ms']}ms"
            )

        return result

    # ─── Main entry point (multi-strategy) ────────────────────────────

    async def parse_domain(self, domain: str) -> Dict:
        """
        Парсить домен и извлечь ИНН и email.
        Multi-strategy: HTTP first → API sniff → Playwright fallback.

        Args:
            domain: Доменное имя (например, example.com)

        Returns:
            Словарь с результатами: {domain, inn, emails, source_urls, error,
                                     extraction_log, strategy_used, strategy_time_ms}
        """
        t0 = time.monotonic()

        # === TIER 1+2: HTTP probe (no browser) ===
        http_result = await self._http_probe_domain(domain)

        # If HTTP found INN (primary target) → skip Playwright entirely
        if http_result['inn']:
            http_result['emails'] = list(set(http_result.get('emails', [])))
            # Save strategy result for future domain override
            try:
                self.learning_engine.save_strategy_result(
                    domain, http_result.get('strategy', 'http'),
                    found_inn=True, found_email=bool(http_result['emails']),
                    time_ms=http_result.get('strategy_time_ms', 0),
                )
            except Exception:
                pass
            logger.info(
                f"✅ {domain}: HTTP-only — ИНН={http_result['inn']}, "
                f"Email={http_result['emails']} [{http_result['strategy_time_ms']}ms]"
            )
            return {
                'domain': domain,
                'inn': http_result['inn'],
                'emails': http_result.get('emails', []),
                'source_urls': http_result.get('source_urls', []),
                'error': None,
                'extraction_log': http_result.get('extraction_log', []),
                'strategy_used': http_result.get('strategy', 'http'),
                'strategy_time_ms': http_result.get('strategy_time_ms', 0),
            }

        # Keep HTTP-found data for merging with Playwright results
        http_emails = list(set(http_result.get('emails', [])))
        http_source_urls = http_result.get('source_urls', [])
        http_extraction_log = http_result.get('extraction_log', [])

        # === TIER 3: Playwright (browser-based, expensive) ===
        logger.info(f"  🌐 HTTP не нашёл ИНН для {domain}, переходим к Playwright...")
        pw_result = await self._playwright_parse_domain(domain)

        # Merge HTTP findings with Playwright results
        pw_result['emails'] = list(set(
            pw_result.get('emails', []) + http_emails
        ))
        pw_result['source_urls'] = list(dict.fromkeys(
            http_source_urls + pw_result.get('source_urls', [])
        ))
        pw_result['extraction_log'] = (
            http_extraction_log + pw_result.get('extraction_log', [])
        )
        pw_result['strategy_used'] = 'playwright'
        pw_result['strategy_time_ms'] = int((time.monotonic() - t0) * 1000)

        # Save strategy result for future domain override
        try:
            self.learning_engine.save_strategy_result(
                domain, 'playwright',
                found_inn=bool(pw_result.get('inn')),
                found_email=bool(pw_result.get('emails')),
                time_ms=pw_result.get('strategy_time_ms', 0),
            )
        except Exception:
            pass

        if pw_result.get('inn'):
            logger.info(
                f"✅ {domain}: Playwright — ИНН={pw_result['inn']}, "
                f"Email={pw_result['emails']} [{pw_result['strategy_time_ms']}ms]"
            )
        else:
            logger.info(
                f"⚠️ {domain}: Ничего не найдено (HTTP+Playwright) "
                f"[{pw_result['strategy_time_ms']}ms]"
            )

        return pw_result

    # ─── Tier 3: Playwright-based parsing ──────────────────────────────

    async def _playwright_parse_domain(self, domain: str) -> Dict:
        """
        Playwright-based domain parsing (Tier 3).
        Вызывается только если HTTP probe не нашёл ИНН.
        """
        if not self.browser:
            raise Exception("Браузер не запущен. Вызовите start() сначала.")
        
        result = {
            'domain': domain,
            'inn': None,
            'emails': [],
            'source_urls': [],
            'error': None,
            'extraction_log': [],
        }
        
        # Формируем URL
        url = f"https://{domain}" if not domain.startswith('http') else domain
        base_url = url
        
        logger.info(f"🔍 Парсинг: {domain}")
        
        page = await self.browser.new_page()
        
        try:
            # Загружаем главную страницу
            logger.info(f"  → Загрузка главной страницы...")
            await self.goto_with_fallback(page, url)
            result['source_urls'].append(page.url)
            
            # Ждем немного для динамического контента
            await page.wait_for_timeout(500)
            
            # Получаем текст и HTML главной страницы
            main_text = await self.get_page_text(page)
            main_html = await page.content()
            
            # Ищем ИНН и email на главной странице
            inn = self.extract_inn(main_text, main_html)
            emails = self.extract_emails(main_text)
            emails.extend(self.extract_emails_from_html(main_html))
            
            page_log = {"url": page.url, "inn_found": None, "emails_found": []}
            if inn:
                result['inn'] = inn
                page_log["inn_found"] = inn
                logger.info(f"  ✅ ИНН найден на главной: {inn}")
            else:
                page_log["inn_found"] = None
            
            if emails:
                result['emails'].extend(emails)
                page_log["emails_found"] = list(set(emails))
                logger.info(f"  ✅ Email найден на главной: {emails}")
            
            result['extraction_log'].append(page_log)
            
            # Если ИНН и email уже найдены на главной — ранний выход
            if inn and emails:
                logger.info(f"  ⚡ ИНН + email найдены на главной — пропускаем доп. страницы")
            else:
                # Ищем на контактных страницах
                logger.info(f"  → Поиск контактных страниц...")
                contact_urls = await self.find_contact_pages(page, base_url)
                priority_urls = self._build_priority_urls(domain, base_url)
                if priority_urls:
                    logger.info(f"  🎓 Найдено приоритетных URL из обучения: {len(priority_urls)}")
                    contact_urls = priority_urls + [url for url in contact_urls if url not in priority_urls]

                # Пробуем популярные URL (сокращённый список самых эффективных)
                common_paths = [
                    '/contacts', '/contacts/', '/about', '/about/',
                    '/requisites', '/requisites/', '/company', '/company/',
                    '/kontakty', '/kontakty/', '/o-kompanii', '/o-kompanii/',
                    '/legal', '/legal/', '/pages/requisites/', '/info', '/info/',
                    '/requisiti', '/requisiti.html', '/rekvizity', '/rekvizity/',
                    '/ur-lica', '/ur-licam', '/opt', '/opt.html',
                    '/kontakty.html', '/o-kompanii.html', '/about-us',
                    '/contacts.html', '/company.html',
                    '/about/requisites', '/about/requisites/', '/about/contacts',
                    '/about/contacts/', '/about/company', '/about/company/',
                    '/pages/contacts', '/pages/about',
                ]
                for path in common_paths:
                    if inn and emails:
                        break  # Уже нашли всё нужное
                    test_url = urljoin(base_url, path)
                    if test_url in contact_urls:
                        continue
                    try:
                        response = await page.goto(test_url, wait_until='domcontentloaded', timeout=7000)
                        if response and response.ok:
                            contact_urls.append(page.url)
                    except Exception:
                        pass

                contact_urls = list(dict.fromkeys(contact_urls))

                # Also collect PDF links from the main page for INN extraction
                pdf_urls = []
                try:
                    pdf_links = await page.evaluate('''() => {
                        return Array.from(document.querySelectorAll('a[href]'))
                            .filter(a => a.href.toLowerCase().endsWith('.pdf'))
                            .map(a => ({ href: a.href, text: a.innerText.toLowerCase() }));
                    }''')
                    pdf_keywords = ['реквизит', 'requisit', 'карточк', 'card', 'инн', 'inn', 'компани', 'company', 'юридическ', 'legal']
                    for link in pdf_links:
                        href = link['href']
                        text = link.get('text', '')
                        if any(kw in text for kw in pdf_keywords) or any(kw in href.lower() for kw in pdf_keywords):
                            full_url = urljoin(base_url, href)
                            if full_url not in pdf_urls and full_url not in contact_urls:
                                pdf_urls.append(full_url)
                except Exception:
                    pass

                for contact_url in contact_urls:
                    if inn and emails:
                        break  # Ранний выход — всё найдено
                    try:
                        # Handle PDF URLs separately
                        if self._is_pdf_url(contact_url):
                            logger.info(f"  → PDF: {contact_url}")
                            result['source_urls'].append(contact_url)
                            pdf_result = await self.download_and_parse_pdf(contact_url)
                            cp_log = {"url": contact_url, "inn_found": None, "emails_found": [], "pdf": True}
                            if pdf_result.get("error"):
                                cp_log["error"] = pdf_result["error"]
                            if pdf_result.get("inn") and not inn:
                                inn = pdf_result["inn"]
                                result['inn'] = inn
                                cp_log["inn_found"] = inn
                            if pdf_result.get("emails"):
                                new_emails = pdf_result["emails"]
                                if not emails:
                                    emails = new_emails
                                result['emails'].extend(new_emails)
                                cp_log["emails_found"] = list(set(new_emails))
                            result['extraction_log'].append(cp_log)
                            continue

                        logger.info(f"  → Загрузка: {contact_url}")
                        await page.goto(contact_url, wait_until='domcontentloaded', timeout=self.timeout)
                        result['source_urls'].append(page.url)

                        contact_text = await self.get_page_text(page)
                        contact_html = await page.content()

                        cp_log = {"url": page.url, "inn_found": None, "emails_found": []}

                        contact_inn = self.extract_inn(contact_text, contact_html)
                        if contact_inn:
                            inn = contact_inn
                            result['inn'] = inn
                            cp_log["inn_found"] = inn
                            logger.info(f"  ✅ ИНН найден на контактной странице: {inn}")

                        if not emails:
                            new_emails = self.extract_emails(contact_text)
                            new_emails.extend(self.extract_emails_from_html(contact_html))
                            if new_emails:
                                emails = new_emails
                                result['emails'].extend(new_emails)
                                cp_log["emails_found"] = list(set(new_emails))
                                logger.info(f"  ✅ Email найден на контактной странице: {new_emails}")

                        # Collect PDF links from this page too
                        if not inn:
                            try:
                                page_pdf_links = await page.evaluate('''() => {
                                    return Array.from(document.querySelectorAll('a[href]'))
                                        .filter(a => a.href.toLowerCase().endsWith('.pdf'))
                                        .map(a => a.href);
                                }''')
                                for pdf_href in page_pdf_links:
                                    full_pdf = urljoin(base_url, pdf_href)
                                    if full_pdf not in pdf_urls and urlparse(full_pdf).netloc == urlparse(base_url).netloc:
                                        pdf_urls.append(full_pdf)
                            except Exception:
                                pass

                        result['extraction_log'].append(cp_log)

                    except PlaywrightTimeout:
                        result['extraction_log'].append({"url": contact_url, "error": "timeout"})
                        logger.warning(f"  ⏱️ Таймаут загрузки: {contact_url}")
                    except Exception as e:
                        err_str = str(e)
                        # If download started (PDF link), try PDF parsing
                        if 'download' in err_str.lower():
                            logger.info(f"  📄 Обнаружен PDF (download): {contact_url}")
                            pdf_result = await self.download_and_parse_pdf(contact_url)
                            cp_log = {"url": contact_url, "inn_found": None, "emails_found": [], "pdf": True}
                            if pdf_result.get("error"):
                                cp_log["error"] = pdf_result["error"]
                            if pdf_result.get("inn") and not inn:
                                inn = pdf_result["inn"]
                                result['inn'] = inn
                                cp_log["inn_found"] = inn
                            if pdf_result.get("emails"):
                                new_emails = pdf_result["emails"]
                                if not emails:
                                    emails = new_emails
                                result['emails'].extend(new_emails)
                                cp_log["emails_found"] = list(set(new_emails))
                            result['extraction_log'].append(cp_log)
                        else:
                            result['extraction_log'].append({"url": contact_url, "error": err_str[:200]})
                            logger.warning(f"  ⚠️ Ошибка загрузки {contact_url}: {e}")

                # Parse collected PDF links (if INN still not found)
                for pdf_url in pdf_urls:
                    if inn:
                        break
                    try:
                        logger.info(f"  → PDF: {pdf_url}")
                        result['source_urls'].append(pdf_url)
                        pdf_result = await self.download_and_parse_pdf(pdf_url)
                        cp_log = {"url": pdf_url, "inn_found": None, "emails_found": [], "pdf": True}
                        if pdf_result.get("error"):
                            cp_log["error"] = pdf_result["error"]
                        if pdf_result.get("inn"):
                            inn = pdf_result["inn"]
                            result['inn'] = inn
                            cp_log["inn_found"] = inn
                        if pdf_result.get("emails"):
                            new_emails = pdf_result["emails"]
                            if not emails:
                                emails = new_emails
                            result['emails'].extend(new_emails)
                            cp_log["emails_found"] = list(set(new_emails))
                        result['extraction_log'].append(cp_log)
                    except Exception as e:
                        result['extraction_log'].append({"url": pdf_url, "error": str(e)[:200]})
                        logger.warning(f"  ⚠️ Ошибка PDF {pdf_url}: {e}")
            
            # Убираем дубликаты email
            result['emails'] = list(set(result['emails']))
            
            if result['inn'] or result['emails']:
                logger.info(f"✅ {domain}: ИНН={result['inn']}, Email={result['emails']}")
            else:
                logger.warning(f"⚠️ {domain}: Ничего не найдено")
            
        except PlaywrightTimeout:
            error_msg = f"Таймаут загрузки страницы"
            result['error'] = error_msg
            result['extraction_log'].append({"url": url, "error": "timeout"})
            logger.error(f"❌ {domain}: {error_msg}")
            
        except Exception as e:
            error_msg = f"Ошибка парсинга: {str(e)}"
            result['error'] = error_msg
            result['extraction_log'].append({"url": url, "error": str(e)[:200]})
            logger.error(f"❌ {domain}: {error_msg}")
            
        finally:
            await page.close()
        
        return result
    
    async def parse_domains(self, domains: List[str]) -> List[Dict]:
        """
        Парсить список доменов.
        
        Args:
            domains: Список доменов
            
        Returns:
            Список результатов для каждого домена
        """
        results = []
        
        for i, domain in enumerate(domains, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"Домен {i}/{len(domains)}")
            logger.info(f"{'='*60}")
            
            result = await self.parse_domain(domain)
            results.append(result)
            
            # Минимальная пауза между запросами
            await asyncio.sleep(0.2)
        
        return results
