"""HTTP client for Checko API."""
import httpx
import logging
from typing import Dict, Any, Optional, List
from app.config import settings

logger = logging.getLogger(__name__)


class CheckoClient:
    """Client for Checko API v2 with automatic API key rotation."""
    
    BASE_URL = "https://api.checko.ru/v2"
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Checko client.
        
        Args:
            api_key: Checko API key. If not provided, uses settings.CHECKO_API_KEYS.
        """
        # Список API ключей для ротации
        self._api_keys: List[str] = []
        self._current_key_index: int = 0
        
        if api_key:
            self._api_keys = [api_key]
        else:
            # Загружаем список ключей из настроек
            self._load_api_keys()
            if not self._api_keys:
                raise ValueError("Checko API key is required")
        self.api_key = self._api_keys[self._current_key_index]
    
    def _load_api_keys(self):
        """Load API keys from settings."""
        # Поддерживаем как одиночный ключ, так и список через запятую
        keys_str = settings.CHECKO_API_KEY
        if not keys_str:
            return
        
        # Разделяем по запятой и очищаем пробелы
        keys = [k.strip() for k in keys_str.split(',') if k.strip()]
        self._api_keys = keys
        logger.info(f"Loaded {len(self._api_keys)} Checko API key(s) for rotation")
    
    def _rotate_api_key(self):
        """Rotate to the next API key."""
        if len(self._api_keys) <= 1:
            logger.warning("Cannot rotate API key: only one key available")
            return False
        
        self._current_key_index = (self._current_key_index + 1) % len(self._api_keys)
        self.api_key = self._api_keys[self._current_key_index]
        logger.info(f"Rotated to API key #{self._current_key_index + 1}/{len(self._api_keys)}")
        return True
    
    async def _make_request(self, url: str, params: Dict[str, Any], max_retries: int = None) -> Dict[str, Any]:
        """Make HTTP request with automatic API key rotation on rate limit.
        
        Args:
            url: API endpoint URL
            params: Request parameters
            max_retries: Maximum number of retries with different keys (default: number of keys)
            
        Returns:
            API response data
            
        Raises:
            httpx.HTTPStatusError: If all API keys are exhausted or other error occurs
        """
        if max_retries is None:
            max_retries = len(self._api_keys)
        
        last_error = None
        
        for attempt in range(max_retries):
            params["key"] = self.api_key
            
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url, params=params)
                    
                    # Проверяем на ошибку лимита (429) или блокировку (403)
                    if response.status_code == 429 or response.status_code == 403:
                        if response.status_code == 429:
                            logger.warning(f"Rate limit exceeded for API key #{self._current_key_index + 1}")
                        else:  # 403
                            logger.warning(f"API key blocked (403) for key #{self._current_key_index + 1}")
                        if self._rotate_api_key():
                            continue  # Пробуем следующий ключ
                        else:
                            response.raise_for_status()
                    
                    # Проверяем ответ на наличие ошибки лимита в JSON
                    try:
                        data = response.json()
                        if isinstance(data, dict):
                            error_msg = data.get('error', '').lower()
                            if 'limit' in error_msg or 'quota' in error_msg or 'превышен' in error_msg:
                                logger.warning(f"API limit error in response for key #{self._current_key_index + 1}: {error_msg}")
                                if self._rotate_api_key():
                                    continue  # Пробуем следующий ключ
                    except:
                        pass
                    
                    response.raise_for_status()
                    return response.json()
                    
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429:
                    logger.warning(f"Rate limit (429) for API key #{self._current_key_index + 1}")
                    if attempt < max_retries - 1 and self._rotate_api_key():
                        continue
                raise
            except Exception as e:
                last_error = e
                logger.error(f"Request failed with API key #{self._current_key_index + 1}: {e}")
                raise
        
        # Все ключи исчерпаны
        if last_error:
            raise last_error
        raise RuntimeError("All Checko API keys exhausted")
    
    async def get_company(self, inn: str) -> Dict[str, Any]:
        """Get company information by INN.
        
        Args:
            inn: Company INN (10 or 12 digits)
            
        Returns:
            Company data from Checko API
            
        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        url = f"{self.BASE_URL}/company"
        params = {"inn": inn}
        return await self._make_request(url, params)
    
    async def get_finances(self, inn: str) -> Dict[str, Any]:
        """Get company financial data by INN.
        
        Args:
            inn: Company INN (10 or 12 digits)
            
        Returns:
            Financial data from Checko API
            
        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        url = f"{self.BASE_URL}/finances"
        params = {"inn": inn}
        return await self._make_request(url, params)
    
    async def get_legal_cases(self, inn: str) -> Dict[str, Any]:
        """Get company legal cases by INN.
        
        Args:
            inn: Company INN (10 or 12 digits)
            
        Returns:
            Legal cases data from Checko API
            
        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        url = f"{self.BASE_URL}/legal-cases"
        params = {"inn": inn}
        return await self._make_request(url, params)
    
    async def get_inspections(self, inn: str) -> Dict[str, Any]:
        """Get company inspections by INN.
        
        Args:
            inn: Company INN (10 or 12 digits)
            
        Returns:
            Inspections data from Checko API
            
        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        url = f"{self.BASE_URL}/inspections"
        params = {"inn": inn}
        return await self._make_request(url, params)
    
    async def get_enforcements(self, inn: str) -> Dict[str, Any]:
        """Get company enforcements by INN.
        
        Args:
            inn: Company INN (10 or 12 digits)
            
        Returns:
            Enforcements data from Checko API
            
        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        url = f"{self.BASE_URL}/enforcements"
        params = {"inn": inn}
        return await self._make_request(url, params)
    
    async def get_all_data(self, inn: str) -> Dict[str, Any]:
        """Get all company data from Checko API (5 endpoints in parallel).
        
        Args:
            inn: Company INN (10 or 12 digits)
            
        Returns:
            Combined data from all Checko endpoints:
            {
                "company": {...},
                "_finances": {...},
                "_legal": {...},
                "_inspections": {...},
                "_enforcements": {...}
            }
        """
        import asyncio
        
        # Запускаем все запросы параллельно
        tasks = [
            self.get_company(inn),
            self.get_finances(inn),
            self.get_legal_cases(inn),
            self.get_inspections(inn),
            self.get_enforcements(inn),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Формируем результат
        company_data = results[0]
        if isinstance(company_data, Exception):
            raise company_data
        
        finances_data = results[1] if not isinstance(results[1], Exception) else {"data": None}
        legal_data = results[2] if not isinstance(results[2], Exception) else {"data": None}
        inspections_data = results[3] if not isinstance(results[3], Exception) else {"data": None}
        enforcements_data = results[4] if not isinstance(results[4], Exception) else {"data": None}
        
        # Логируем ошибки в дополнительных запросах (не критичны)
        for i, result in enumerate(results[1:], 1):
            if isinstance(result, Exception):
                endpoint_names = ["finances", "legal-cases", "inspections", "enforcements"]
                logger.warning(f"Failed to fetch {endpoint_names[i-1]} for INN {inn}: {result}")
        
        return {
            **company_data.get("data", {}),
            "_finances": finances_data.get("data") or {},
            "_legal": legal_data.get("data") or {},
            "_inspections": inspections_data.get("data") or {},
            "_enforcements": enforcements_data.get("data") or {},
        }
