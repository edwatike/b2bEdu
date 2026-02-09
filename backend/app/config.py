"""
Application configuration using Pydantic Settings.
Reads settings from environment variables.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database - PostgreSQL с данными поставщиков
    DATABASE_URL: str = "postgresql+asyncpg://postgres:12059001@localhost:5432/b2bplatform"

    # Parser Service
    PARSER_SERVICE_URL: str = "http://127.0.0.1:9000"
    LLM_KEYS_ENABLED: bool = False
    LLM_KEYS_FORCE: bool = False
    OLLAMA_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = ""
    OLLAMA_TIMEOUT_SEC: int = 15

    # Checko API
    CHECKO_API_KEY: str = ""

    # Groq (platform key)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = ""
    GROQ_BASE_URL: str = ""

    # Application
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    LOG_SQL: bool = False

    # Domain parser auto-enrichment
    DOMAIN_PARSER_AUTO_ENABLED: str = "1"
    DOMAIN_PARSER_AUTO_MODE: str = "complete"  # complete|progressive
    DOMAIN_PARSER_AUTO_MAX_CONCURRENCY: str = "2"
    DOMAIN_PARSER_AUTO_EARLY: str = "1"
    DOMAIN_PARSER_AUTO_LIMIT: str = "3"

    # Parsing concurrency guard (CDP is single-instance)
    PARSING_MAX_CONCURRENCY: str = "1"

    # CORS - парсим из строки, разделенной запятыми
    # Включаем localhost:3000, 127.0.0.1:3000 и browser preview порты
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001,http://127.0.0.1:60124,http://localhost:60124"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    # Storage
    ATTACHMENTS_DIR: str = "storage/attachments"

    # User secrets encryption
    USER_SECRETS_FERNET_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=[
            str(Path(__file__).resolve().parents[2] / ".env"),
            str(Path(__file__).resolve().parents[1] / ".env"),
        ],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


# Create a singleton instance
settings = Settings()

# Backward compatibility: add properties for lowercase access
Settings.database_url = property(lambda self: self.DATABASE_URL)
Settings.parser_service_url = property(lambda self: self.PARSER_SERVICE_URL)
Settings.env = property(lambda self: self.ENV)
Settings.log_level = property(lambda self: self.LOG_LEVEL)
Settings.log_sql = property(lambda self: self.LOG_SQL)
Settings.attachments_dir = property(lambda self: self.ATTACHMENTS_DIR)
Settings.cors_origins = property(lambda self: self.CORS_ORIGINS)
Settings.checko_api_key = property(lambda self: self.CHECKO_API_KEY)

Settings.user_secrets_fernet_key = property(lambda self: self.USER_SECRETS_FERNET_KEY)

# Backward compatibility for Groq settings
Settings.groq_api_key = property(lambda self: self.GROQ_API_KEY)
Settings.groq_model = property(lambda self: self.GROQ_MODEL)
Settings.groq_base_url = property(lambda self: self.GROQ_BASE_URL)

# Backward compatibility for new optional LLM settings
Settings.llm_keys_enabled = property(lambda self: self.LLM_KEYS_ENABLED)
Settings.llm_keys_force = property(lambda self: self.LLM_KEYS_FORCE)
Settings.ollama_url = property(lambda self: self.OLLAMA_URL)
Settings.ollama_model = property(lambda self: self.OLLAMA_MODEL)
Settings.ollama_timeout_sec = property(lambda self: self.OLLAMA_TIMEOUT_SEC)
