"""Configuration for Parser Service."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Parser Service settings."""
    
    CHROME_CDP_URL: str = "http://127.0.0.1:9222"
    LOG_LEVEL: str = "INFO"

    # Safety: by default DO NOT attach to user's real Chrome via CDP.
    # When False, parser will launch isolated Chromium instance.
    USE_CHROME_CDP: bool = True
    HEADLESS: bool = False
    
    # Chrome Profile Selection
    # Profile index: 0 = first profile (default), 1 = second profile, etc.
    # If profile_index is set, parser will try to use that specific profile's context
    CHROME_PROFILE_INDEX: int = 0  # 0 = first profile, 1 = second profile, etc.
    
    # Timeouts
    page_load_timeout: int = 30000  # 30 seconds
    navigation_timeout: int = 60000  # 60 seconds
    
    # Backend URL for status updates
    BACKEND_URL: str = "http://127.0.0.1:8000"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
    
    @property
    def chrome_cdp_url(self) -> str:
        """Backward compatibility."""
        return self.CHROME_CDP_URL
    
    @property
    def log_level(self) -> str:
        """Backward compatibility."""
        return self.LOG_LEVEL
    
    @property
    def chrome_profile_index(self) -> int:
        """Get Chrome profile index (0-based)."""
        return self.CHROME_PROFILE_INDEX


settings = Settings()

