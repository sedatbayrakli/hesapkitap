"""
KantinPos Ana FastAPI Uygulaması.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import text
from app.config import settings
from app.database import engine
from app.seed import setup_database
from app.routers import auth, dashboard, sales, purchases, register, reports, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama açılışında veritabanı şemasını ve seed verilerini kontrol eder."""
    setup_database()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
    docs_url=None,   # Üretimde Swagger arayüzü kapalı
    redoc_url=None
)

# Starlette SessionMiddleware (HttpOnly, SameSite=Lax, Opsiyonel Secure)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie=settings.SESSION_COOKIE_NAME,
    max_age=settings.SESSION_MAX_AGE,
    same_site="lax",
    https_only=settings.COOKIE_SECURE
)

# Statik Dosyalar ve Şablonlar
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Router Kayıtları
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(sales.router)
app.include_router(purchases.router)
app.include_router(register.router)
app.include_router(reports.router)
app.include_router(admin.router)


@app.get("/")
def root():
    """Kök dizin isteklerini uygun ekrana veya girişe yönlendirir."""
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/health")
def health_check():
    """Coolify ve konteyner sağlık kontrolü (Healthcheck)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
        return {"status": "ok", "db": "up"}
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "db": "down", "detail": str(exc)}
        )
