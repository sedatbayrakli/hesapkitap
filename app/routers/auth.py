"""
Kimlik doğrulama, giriş ve çıkış yönlendiricisi (Auth Router).
"""

from fastapi import APIRouter, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.security import (
    verify_password,
    generate_csrf_token,
    verify_csrf_token,
    check_rate_limit,
    record_failed_login,
    reset_failed_login
)

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    """Giriş sayfasını gösterir."""
    # Zaten giriş yapılmışsa dashboard'a yönlendir
    if request.session.get("user_id"):
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

    csrf_token = generate_csrf_token(request)
    is_locked, remaining = check_rate_limit(request)
    error_msg = None
    if is_locked:
        error_msg = "Çok fazla hatalı giriş denemesi yapıldı. Lütfen 5 dakika sonra tekrar deneyin."

    return templates.TemplateResponse("login.html", {
        "request": request,
        "csrf_token": csrf_token,
        "error": error_msg,
        "remaining_attempts": remaining,
        "user": None
    })


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db)
):
    """Kullanıcı adı ve şifre ile giriş kontrolü yapar."""
    # 1. CSRF Doğrulaması
    if not verify_csrf_token(request, csrf_token):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "csrf_token": generate_csrf_token(request),
            "error": "Oturum güvenliği (CSRF) doğrulanamadı. Sayfayı yenileyip tekrar deneyin.",
            "user": None
        }, status_code=status.HTTP_400_BAD_REQUEST)

    # 2. Rate Limiting Kontrolü
    is_locked, remaining = check_rate_limit(request)
    if is_locked:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "csrf_token": generate_csrf_token(request),
            "error": "Çok fazla hatalı giriş yapıldı. Hesabınız geçici olarak kilitlendi (5 dakika).",
            "remaining_attempts": 0,
            "user": None
        }, status_code=status.HTTP_429_TOO_MANY_REQUESTS)

    # 3. Kullanıcı Bilgisi ve Şifre Doğrulama
    user = db.query(User).filter(User.Username == username.strip(), User.IsActive == 1).first()
    if not user or not verify_password(password, user.PasswordHash):
        rem = record_failed_login(request)
        error_text = f"Kullanıcı adı veya şifre hatalı! Kalan deneme hakkı: {rem}" if rem > 0 else "Çok fazla hatalı giriş yapıldı. 5 dakika bekleyiniz."
        return templates.TemplateResponse("login.html", {
            "request": request,
            "csrf_token": generate_csrf_token(request),
            "error": error_text,
            "remaining_attempts": rem,
            "user": None
        }, status_code=status.HTTP_401_UNAUTHORIZED)

    # 4. Giriş Başarılı -> Oturum Bilgilerini Kaydet
    reset_failed_login(request)
    request.session.clear()
    request.session["csrf_token"] = generate_csrf_token(request)
    request.session["user_id"] = user.UserID
    request.session["is_super_admin"] = bool(user.IsSuperAdmin)
    request.session["user_name"] = user.FullName
    if user.TenantID:
        request.session["tenant_id"] = user.TenantID
    if user.DefaultBranchID:
        request.session["active_branch_id"] = user.DefaultBranchID

    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/logout")
def logout(request: Request):
    """Oturumu sonlandırır ve giriş sayfasına yönlendirir."""
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
