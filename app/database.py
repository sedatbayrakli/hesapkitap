"""
Veritabanı bağlantı havuzu ve SQLite ayarları.
WAL mode, busy_timeout=5000 ve foreign_keys=ON her bağlantıda zorunlu kılınmıştır.
"""

import os
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

# Veritabanı dosyasının bulunduğu dizini otomatik oluştur
db_file_path = Path(settings.DB_PATH).resolve()
db_file_path.parent.mkdir(parents=True, exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{db_file_path}"

# SQLite bağlantı motoru
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 15},
    pool_pre_ping=True
)


@event.listens_for(engine, "connect")
def configure_sqlite_connection(dbapi_connection, connection_record):
    """SQLite bağlantı ayarlarını (WAL, busy_timeout, foreign_keys) yapılandırır."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI endpointleri ve servisler için veritabanı oturumu üreticisi."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
