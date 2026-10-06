"""
Uygulama genel yapılandırma ayarları (Environment değişkenleri).
"""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "KantinPos"
    APP_ENV: str = "production"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "kantinpos-cok-gizli-anahtar-degistirin-lutfen-32char-min")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")
    DB_PATH: str = os.getenv("DB_PATH", "data/kantinpos.db")
    SESSION_COOKIE_NAME: str = "kantinpos_session"
    SESSION_MAX_AGE: int = 86400 * 7  # 7 gün
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() in ("true", "1", "yes")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
