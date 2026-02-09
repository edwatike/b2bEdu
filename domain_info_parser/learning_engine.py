"""Learning Engine - обучает Domain Parser на основе успешных результатов Comet."""
import json
import re
import os
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


class LearningEngine:
    """Движок обучения для Domain Parser."""
    
    def __init__(self, patterns_file: str = None):
        """
        Args:
            patterns_file: Путь к файлу с выученными паттернами
        """
        if patterns_file is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            patterns_file = os.path.join(current_dir, "learning_patterns.json")
        
        self.patterns_file = patterns_file
        self.patterns = self._load_patterns()
    
    def _load_patterns(self) -> Dict:
        """Загрузить выученные паттерны из файла."""
        if not os.path.exists(self.patterns_file):
            return {
                "version": "1.0",
                "last_updated": None,
                "learned_patterns": {
                    "inn_patterns": [],
                    "email_patterns": [],
                    "successful_urls": {
                        "inn": [],
                        "email": []
                    },
                    "domain_specific": {}
                },
                "statistics": {
                    "total_learned": 0,
                    "comet_contributions": 0,
                    "success_rate_before": 0.0,
                    "success_rate_after": 0.0
                }
            }
        
        try:
            with open(self.patterns_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading patterns: {e}")
            return self._load_patterns()  # Return default
    
    def _save_patterns(self):
        """Сохранить выученные паттерны в файл."""
        try:
            self.patterns["last_updated"] = datetime.now().isoformat()
            with open(self.patterns_file, 'w', encoding='utf-8') as f:
                json.dump(self.patterns, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ Patterns saved to {self.patterns_file}")
        except Exception as e:
            logger.error(f"Error saving patterns: {e}")
    
    def learn_from_comet_success(
        self,
        domain: str,
        comet_result: Dict,
        parser_result: Dict,
        learning_session_id: str = None
    ) -> Dict:
        """
        Обучиться на успешном результате Comet, когда Domain Parser не нашел данные.
        
        Args:
            domain: Домен, на котором обучаемся
            comet_result: Результат Comet (с найденными ИНН/Email)
            parser_result: Результат Domain Parser (не нашел данные)
            learning_session_id: ID сессии обучения для группировки
        
        Returns:
            Dict с информацией о том, что было выучено
        """
        learned = {
            "domain": domain,
            "timestamp": datetime.now().isoformat(),
            "session_id": learning_session_id,
            "learned_items": []
        }
        
        # Проверяем, что Comet нашел данные, а Parser - нет
        comet_inn = comet_result.get("inn")
        comet_email = comet_result.get("email")
        parser_inn = parser_result.get("inn")
        parser_email = parser_result.get("email")
        
        source_urls = comet_result.get("sourceUrls", [])
        
        # Обучение на ИНН
        if comet_inn and not parser_inn:
            inn_learning = self._learn_inn_pattern(domain, comet_inn, source_urls)
            if inn_learning:
                learned["learned_items"].append(inn_learning)
        
        # Обучение на Email
        if comet_email and not parser_email:
            email_learning = self._learn_email_pattern(domain, comet_email, source_urls)
            if email_learning:
                learned["learned_items"].append(email_learning)
        
        # Сохраняем статистику
        if learned["learned_items"]:
            self.patterns["statistics"]["total_learned"] += len(learned["learned_items"])
            self.patterns["statistics"]["comet_contributions"] += 1
            self._save_patterns()
            
            logger.info(f"📚 Learned {len(learned['learned_items'])} patterns from {domain}")
        
        return learned

    def learn_from_manual_inn(
        self,
        domain: str,
        inn: str,
        source_url: str = None,
        source_urls: Optional[List[str]] = None,
        learning_session_id: str = None
    ) -> Dict:
        """Ручное обучение по ссылке, где найден ИНН."""
        learned = {
            "domain": domain,
            "timestamp": datetime.now().isoformat(),
            "session_id": learning_session_id,
            "learned_items": []
        }

        urls = []
        if source_urls and isinstance(source_urls, list):
            urls = [str(u).strip() for u in source_urls if str(u).strip()]
        if not urls and source_url:
            urls = [str(source_url).strip()]

        if not urls:
            return learned

        inn_learning = self._learn_inn_pattern(domain, inn, urls)
        if inn_learning:
            learned["learned_items"].append(inn_learning)
            self.patterns["statistics"]["total_learned"] += 1
            self._save_patterns()

        return learned
    
    def _learn_inn_pattern(self, domain: str, inn: str, source_urls: List[str]) -> Optional[Dict]:
        """Выучить паттерн для поиска ИНН."""
        # Анализируем URL, где был найден ИНН
        url_patterns = self._extract_url_patterns(source_urls)
        
        # Сохраняем успешные URL паттерны
        for pattern in url_patterns:
            if pattern not in self.patterns["learned_patterns"]["successful_urls"]["inn"]:
                self.patterns["learned_patterns"]["successful_urls"]["inn"].append(pattern)
        
        # Сохраняем domain-specific информацию
        if domain not in self.patterns["learned_patterns"]["domain_specific"]:
            self.patterns["learned_patterns"]["domain_specific"][domain] = {
                "inn_urls": [],
                "email_urls": [],
                "inn_found_count": 0,
                "email_found_count": 0
            }
        
        self.patterns["learned_patterns"]["domain_specific"][domain]["inn_urls"].extend(source_urls)
        self.patterns["learned_patterns"]["domain_specific"][domain]["inn_found_count"] += 1
        
        return {
            "type": "inn",
            "value": inn,
            "source_urls": source_urls,
            "url_patterns": url_patterns,
            "learning": f"Теперь буду проверять страницы типа: {', '.join(url_patterns[:3])}"
        }
    
    def _learn_email_pattern(self, domain: str, email: str, source_urls: List[str]) -> Optional[Dict]:
        """Выучить паттерн для поиска Email."""
        # Анализируем URL, где был найден Email
        url_patterns = self._extract_url_patterns(source_urls)
        
        # Сохраняем успешные URL паттерны
        for pattern in url_patterns:
            if pattern not in self.patterns["learned_patterns"]["successful_urls"]["email"]:
                self.patterns["learned_patterns"]["successful_urls"]["email"].append(pattern)
        
        # Сохраняем domain-specific информацию
        if domain not in self.patterns["learned_patterns"]["domain_specific"]:
            self.patterns["learned_patterns"]["domain_specific"][domain] = {
                "inn_urls": [],
                "email_urls": [],
                "inn_found_count": 0,
                "email_found_count": 0
            }
        
        self.patterns["learned_patterns"]["domain_specific"][domain]["email_urls"].extend(source_urls)
        self.patterns["learned_patterns"]["domain_specific"][domain]["email_found_count"] += 1
        
        # Извлекаем паттерн email домена
        email_domain = email.split('@')[-1] if '@' in email else None
        if email_domain:
            email_pattern = f"*@{email_domain}"
            if email_pattern not in self.patterns["learned_patterns"]["email_patterns"]:
                self.patterns["learned_patterns"]["email_patterns"].append(email_pattern)
        
        return {
            "type": "email",
            "value": email,
            "source_urls": source_urls,
            "url_patterns": url_patterns,
            "learning": f"Теперь буду проверять страницы типа: {', '.join(url_patterns[:3])}"
        }
    
    def _extract_url_patterns(self, urls: List[str]) -> List[str]:
        """Извлечь паттерны из URL (например, /contacts, /about, /requisites)."""
        patterns = []
        
        for url in urls:
            try:
                parsed = urlparse(url)
                path = parsed.path.lower()
                
                # Извлекаем ключевые части пути
                if '/contact' in path:
                    patterns.append('/contacts')
                elif '/about' in path:
                    patterns.append('/about')
                elif '/requisite' in path or '/rekvizit' in path:
                    patterns.append('/requisites')
                elif '/company' in path or '/kompan' in path:
                    patterns.append('/company')
                elif '/info' in path:
                    patterns.append('/info')
                elif path and path != '/':
                    # Берем первый сегмент пути
                    segments = [s for s in path.split('/') if s]
                    if segments:
                        patterns.append(f'/{segments[0]}')
            except Exception:
                continue
        
        return list(set(patterns))  # Убираем дубликаты
    
    def get_priority_urls(self, domain: str, data_type: str = "both") -> List[str]:
        """
        Получить приоритетные URL для проверки на основе выученных паттернов.
        
        Args:
            domain: Домен для проверки
            data_type: "inn", "email" или "both"
        
        Returns:
            Список приоритетных URL паттернов
        """
        priority_urls = []
        
        # Проверяем domain-specific паттерны
        domain_data = self.patterns["learned_patterns"]["domain_specific"].get(domain, {})
        
        if data_type in ["inn", "both"]:
            priority_urls.extend(domain_data.get("inn_urls", []))
            priority_urls.extend(self.patterns["learned_patterns"]["successful_urls"]["inn"])
        
        if data_type in ["email", "both"]:
            priority_urls.extend(domain_data.get("email_urls", []))
            priority_urls.extend(self.patterns["learned_patterns"]["successful_urls"]["email"])
        
        # Убираем дубликаты, сохраняя порядок
        seen = set()
        unique_urls = []
        for url in priority_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        return unique_urls
    
    def get_statistics(self) -> Dict:
        """Получить статистику обучения."""
        return self.patterns["statistics"]
    
    def save_strategy_result(self, domain: str, strategy: str, found_inn: bool, found_email: bool, time_ms: int = 0) -> None:
        """Сохранить результат стратегии для домена (для автовыбора в будущем)."""
        try:
            cache = self.patterns.get("strategy_cache", {})
            entry = cache.get(domain, {"attempts": []})
            entry["attempts"].append({
                "strategy": strategy,
                "found_inn": found_inn,
                "found_email": found_email,
                "time_ms": time_ms,
                "timestamp": datetime.now().isoformat(),
            })
            # Keep only last 5 attempts per domain
            entry["attempts"] = entry["attempts"][-5:]
            # Determine best strategy
            for attempt in reversed(entry["attempts"]):
                if attempt["found_inn"]:
                    entry["best_strategy"] = attempt["strategy"]
                    break
            cache[domain] = entry
            self.patterns["strategy_cache"] = cache
            self._save_patterns()
        except Exception as e:
            logger.warning(f"Failed to save strategy result: {e}")

    def get_best_strategy(self, domain: str) -> Optional[str]:
        """Получить лучшую стратегию для домена (None если неизвестно)."""
        try:
            cache = self.patterns.get("strategy_cache", {})
            entry = cache.get(domain, {})
            return entry.get("best_strategy")
        except Exception:
            return None

    def get_learned_summary(self, limit: int = 10) -> Dict:
        """Получить краткую сводку выученных паттернов."""
        return {
            "total_patterns": len(self.patterns["learned_patterns"]["successful_urls"]["inn"]) + 
                            len(self.patterns["learned_patterns"]["successful_urls"]["email"]),
            "inn_url_patterns": self.patterns["learned_patterns"]["successful_urls"]["inn"][:limit],
            "email_url_patterns": self.patterns["learned_patterns"]["successful_urls"]["email"][:limit],
            "domains_learned": len(self.patterns["learned_patterns"]["domain_specific"]),
            "statistics": self.patterns["statistics"]
        }
