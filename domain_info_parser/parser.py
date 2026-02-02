"""Domain Info Parser - извлекает ИНН и email с веб-страниц."""
import re
import asyncio
from typing import Optional, Dict, List
from urllib.parse import urljoin, urlparse
import logging

from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeout
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
        base_netloc = urlparse(base_url).netloc
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
            if urlparse(url).netloc == base_netloc:
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
            
            # С разделителями
            r'ИНН[:\s\n]+(\d{4}[\s\-\n]?\d{6})',  # ИНН: 1234 567890
            r'ИНН[:\s\n]+(\d{4}[\s\-\n]?\d{4}[\s\-\n]?\d{4})',  # ИНН: 1234 5678 9012
            
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

    async def goto_with_fallback(self, page: Page, url: str) -> None:
        """Открыть страницу, при ошибке HTTPS попробовать HTTP."""
        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=self.timeout)
            return
        except Exception as e:
            if url.startswith("https://"):
                fallback_url = "http://" + url[len("https://") :]
                logger.warning(f"  ⚠️ HTTPS не удалось, пробуем HTTP: {fallback_url}")
                await page.goto(fallback_url, wait_until='domcontentloaded', timeout=self.timeout)
                return
            raise e
    
    async def get_page_text(self, page: Page) -> str:
        """Получить весь текст со страницы."""
        try:
            # Получаем текст из body
            text = await page.evaluate('''() => {
                return document.body.innerText;
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
            'politics', 'company', 'юридическ', 'legal', 'details', 'информация'
        ]
        # Ключевые слова в URL
        url_keywords = [
            'contact', 'about', 'requisites', 'requisite', 'politics', 
            'company', 'legal', 'details', 'o-kompanii', 'kompanii'
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
    
    async def parse_domain(self, domain: str) -> Dict:
        """
        Парсить домен и извлечь ИНН и email.
        
        Args:
            domain: Доменное имя (например, example.com)
            
        Returns:
            Словарь с результатами: {domain, inn, emails, source_urls, error}
        """
        if not self.browser:
            raise Exception("Браузер не запущен. Вызовите start() сначала.")
        
        result = {
            'domain': domain,
            'inn': None,
            'emails': [],
            'source_urls': [],
            'error': None
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
            await page.wait_for_timeout(2000)
            
            # Получаем текст и HTML главной страницы
            main_text = await self.get_page_text(page)
            main_html = await page.content()
            
            # Ищем ИНН и email на главной странице
            inn = self.extract_inn(main_text, main_html)
            emails = self.extract_emails(main_text)
            emails.extend(self.extract_emails_from_html(main_html))
            
            if inn:
                result['inn'] = inn
                logger.info(f"  ✅ ИНН найден на главной: {inn}")
            
            if emails:
                result['emails'].extend(emails)
                logger.info(f"  ✅ Email найден на главной: {emails}")
            
            # ВСЕГДА ищем на контактных страницах для более точных данных
            logger.info(f"  → Поиск контактных страниц...")
            contact_urls = await self.find_contact_pages(page, base_url)
            priority_urls = self._build_priority_urls(domain, base_url)
            if priority_urls:
                logger.info(f"  🎓 Найдено приоритетных URL из обучения: {len(priority_urls)}")
                contact_urls = priority_urls + [url for url in contact_urls if url not in priority_urls]
            
            # ВСЕГДА пробуем популярные URL для надежности
            if not contact_urls or True:  # Всегда true для надежности
                logger.info(f"  → Пробуем популярные URL...")
                common_paths = [
                    '/pages/requisites/', '/requisites/', '/requisites', 
                    '/company/', '/company', '/about/', '/about',
                    '/contacts/', '/contacts', '/politics/', '/politics',
                    '/legal/', '/legal', '/details/', '/details',
                    '/o-kompanii.html', '/o-kompanii/', '/about/contacts/',
                    '/service/legal/', '/kontakty.html', '/kontakty/',
                    '/contacts/kontakty', '/contacts/contacts', '/info/',
                    '/company/info/', '/about/company/', '/requisites/info/',
                    '/docs/requisites/', '/download/requisites/', '/files/requisites/',
                    '/upload/requisites/', '/media/requisites/', '/assets/docs/',
                    '/contacts/details/', '/about/', '/contacts/details/'  # Добавленные пути - дублирую для надежности
                ]
                for path in common_paths:
                    test_url = urljoin(base_url, path)
                    if test_url in contact_urls:
                        continue
                    try:
                        response = await page.goto(test_url, wait_until='domcontentloaded', timeout=10000)
                        # Проверяем статус ответа
                        if response and response.ok:
                            contact_urls.append(page.url)
                            logger.info(f"  ✅ Найдена страница: {path}")
                            # НЕ break - проверяем все страницы для надежности
                    except Exception as e:
                        logger.debug(f"  ⏭️ Пропуск {path}: {str(e)[:50]}")
                        pass  # Страница не существует, пробуем следующую
                
                contact_urls = list(dict.fromkeys(contact_urls))

                for contact_url in contact_urls:
                    # Всегда ищем на контактных страницах, даже если ИНН уже найден
                    # Может быть более релевантная информация
                    try:
                        logger.info(f"  → Загрузка: {contact_url}")
                        await page.goto(contact_url, wait_until='domcontentloaded', timeout=self.timeout)
                        result['source_urls'].append(page.url)
                        
                        contact_text = await self.get_page_text(page)
                        contact_html = await page.content()
                        
                        # Ищем ИНН с приоритетом на контактных страницах
                        contact_inn = self.extract_inn(contact_text, contact_html)
                        if contact_inn and not inn:
                            # Если ИНН еще не был найден, используем его
                            inn = contact_inn
                            result['inn'] = inn
                            logger.info(f"  ✅ ИНН найден на контактной странице: {inn}")
                        elif contact_inn and inn:
                            # Если ИНН уже был найден, но на контактной странице есть другой,
                            # приоритет отдаем контактной странице (там более точная информация)
                            inn = contact_inn
                            result['inn'] = inn
                            logger.info(f"  ✅ Обновлен ИНН с контактной страницы: {inn}")
                        
                        if not emails:
                            new_emails = self.extract_emails(contact_text)
                            new_emails.extend(self.extract_emails_from_html(contact_html))
                            if new_emails:
                                result['emails'].extend(new_emails)
                                logger.info(f"  ✅ Email найден на контактной странице: {new_emails}")
                        
                    except PlaywrightTimeout:
                        logger.warning(f"  ⏱️ Таймаут загрузки: {contact_url}")
                    except Exception as e:
                        logger.warning(f"  ⚠️ Ошибка загрузки {contact_url}: {e}")
            
            # Убираем дубликаты email
            result['emails'] = list(set(result['emails']))
            
            if result['inn'] or result['emails']:
                logger.info(f"✅ {domain}: ИНН={result['inn']}, Email={result['emails']}")
            else:
                logger.warning(f"⚠️ {domain}: Ничего не найдено")
            
        except PlaywrightTimeout:
            error_msg = f"Таймаут загрузки страницы"
            result['error'] = error_msg
            logger.error(f"❌ {domain}: {error_msg}")
            
        except Exception as e:
            error_msg = f"Ошибка парсинга: {str(e)}"
            result['error'] = error_msg
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
            
            # Небольшая пауза между запросами
            await asyncio.sleep(1)
        
        return results
