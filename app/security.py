"""
Güvenlik, şifreleme, oturum ve CSRF yardımcı fonksiyonları.
"""

import hmac
import hashlib
import secrets
import time
from typing import Dict, Tuple
from fastapi import Request, HTTPException, status
from passlib.context import CryptContext
from app.config import settings

# Şifre hashleme context'i (bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# IP bazlı kaba kuvvet (brute-force) koruması: ip -> (deneme_sayisi, bloke_bitis_zamani)
LOGIN_ATTEMPTS: Dict[str, Tuple[int, float]] = {}
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = 300  # 5 dakika (saniye)


def hash_password(password: str) -> str:
    """Metin halindeki şifreyi bcrypt ile hashler."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verilen şifrenin hash ile eşleştiğini doğrular."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def get_client_ip(request: Request) -> str:
    """İstemcinin IP adresini header veya client bilgisinden alır."""
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def check_rate_limit(request: Request) -> Tuple[bool, int]:
    """
    Login deneme sınırını kontrol eder.
    Dönüş: (kilitli_mi, kalan_deneme_sayisi)
    """
    ip = get_client_ip(request)
    now = time.time()
    
    if ip in LOGIN_ATTEMPTS:
        attempts, lock_until = LOGIN_ATTEMPTS[ip]
        if now < lock_until:
            return True, 0
        if now >= lock_until and lock_until > 0:
            # Kilit süresi dolmuş, sıfırla
            LOGIN_ATTEMPTS[ip] = (0, 0.0)
            return False, MAX_LOGIN_ATTEMPTS
        
        remaining = max(0, MAX_LOGIN_ATTEMPTS - attempts)
        return False, remaining
    
    return False, MAX_LOGIN_ATTEMPTS


def record_failed_login(request: Request) -> int:
    """
    Başarısız login denemesini kaydeder.
    Kalan deneme hakkını döndürür.
    """
    ip = get_client_ip(request)
    now = time.time()
    attempts, lock_until = LOGIN_ATTEMPTS.get(ip, (0, 0.0))
    
    if now >= lock_until and lock_until > 0:
        attempts = 0
    
    attempts += 1
    if attempts >= MAX_LOGIN_ATTEMPTS:
        LOGIN_ATTEMPTS[ip] = (attempts, now + LOCKOUT_DURATION)
        return 0
    else:
        LOGIN_ATTEMPTS[ip] = (attempts, 0.0)
        return MAX_LOGIN_ATTEMPTS - attempts


def reset_failed_login(request: Request) -> None:
    """Başarılı giriş sonrasında IP sayaçlarını sıfırlar."""
    ip = get_client_ip(request)
    if ip in LOGIN_ATTEMPTS:
        del LOGIN_ATTEMPTS[ip]


def generate_csrf_token(request: Request) -> str:
    """Session tabanlı güvenli CSRF token üretir."""
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_hex(32)
        request.session["csrf_token"] = token
    return token


def verify_csrf_token(request: Request, submitted_token: str) -> bool:
    """Formdan gönderilen CSRF token ile oturumdaki token'ı karşılaştırır."""
    session_token = request.session.get("csrf_token")
    if not session_token or not submitted_token:
        return False
    return hmac.compare_digest(session_token, submitted_token)
