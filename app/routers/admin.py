"""
Yönetim, Personel, Şube ve Tenant Yönetimi Router'ı.
"""

from typing import Optional
from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Tenant, Branch
from app.deps import (
    get_current_context,
    require_can_manage_users,
    require_super_admin,
    CurrentContext
)
from app.security import hash_password, generate_csrf_token, verify_csrf_token

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/users", response_class=HTMLResponse)
def users_page(
    request: Request,
    context: CurrentContext = Depends(require_can_manage_users),
    db: Session = Depends(get_db)
):
    """Personel ve yönetim listesi sayfası."""
    # Sadece aktif tenant'ın kullanıcıları
    users = db.query(User).filter(
        User.TenantID == context.effective_tenant_id
    ).order_by(User.IsActive.desc(), User.FullName.asc()).all()

    return templates.TemplateResponse("admin_users.html", {
        "request": request,
        "user": context.user,
        "active_tenant": context.active_tenant,
        "active_branch_id": context.active_branch_id,
        "branches": context.branches,
        "all_tenants": context.all_tenants,
        "users": users,
        "csrf_token": generate_csrf_token(request),
        "active_page": "admin"
    })


@router.post("/users")
def create_user(
    request: Request,
    full_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    default_branch_id: Optional[str] = Form(None),
    can_sales: Optional[str] = Form(None),
    can_purchases: Optional[str] = Form(None),
    can_register: Optional[str] = Form(None),
    can_reports: Optional[str] = Form(None),
    can_users: Optional[str] = Form(None),
    csrf_token: str = Form(...),
    context: CurrentContext = Depends(require_can_manage_users),
    db: Session = Depends(get_db)
):
    """Yeni personel oluşturur."""
    if not verify_csrf_token(request, csrf_token):
        raise HTTPException(status_code=400, detail="Geçersiz CSRF jetonu.")

    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Şifre en az 8 karakter olmalıdır.")

    existing = db.query(User).filter(User.Username == username.strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Bu kullanıcı adı zaten kullanılıyor.")

    def_branch = int(default_branch_id) if default_branch_id and default_branch_id.isdigit() else None

    new_user = User(
        TenantID=context.effective_tenant_id,
        DefaultBranchID=def_branch,
        Username=username.strip(),
        PasswordHash=hash_password(password),
        FullName=full_name.strip(),
        IsSuperAdmin=0,
        CanManageSales=1 if can_sales == "1" else 0,
        CanManagePurchases=1 if can_purchases == "1" else 0,
        CanManageCashRegister=1 if can_register == "1" else 0,
        CanViewReports=1 if can_reports == "1" else 0,
        CanManageUsers=1 if can_users == "1" else 0,
        IsActive=1
    )
    db.add(new_user)
    db.commit()

    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/users/{target_user_id}/toggle-status")
def toggle_user_status(
    target_user_id: int,
    request: Request,
    csrf_token: str = Form(...),
    context: CurrentContext = Depends(require_can_manage_users),
    db: Session = Depends(get_db)
):
    """Personeli aktif/pasif yapar."""
    if not verify_csrf_token(request, csrf_token):
        raise HTTPException(status_code=400, detail="Geçersiz CSRF jetonu.")

    target = db.query(User).filter(
        User.UserID == target_user_id,
        User.TenantID == context.effective_tenant_id
    ).first()

    if not target or target.IsSuperAdmin:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı veya değiştirilemez.")

    target.IsActive = 0 if target.IsActive == 1 else 1
    db.commit()

    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/switch-tenant")
def switch_tenant(
    request: Request,
    tenant_id: int = Form(...),
    csrf_token: str = Form(...),
    context: CurrentContext = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """Süper Admin'in çalıştığı aktif tenant'ı session'da değiştirir."""
    if not verify_csrf_token(request, csrf_token):
        raise HTTPException(status_code=400, detail="Geçersiz CSRF jetonu.")

    tenant = db.query(Tenant).filter(Tenant.TenantID == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="İşletme bulunamadı.")

    request.session["selected_tenant_id"] = tenant.TenantID
    request.session.pop("active_branch_id", None)

    referer = request.headers.get("referer") or "/dashboard"
    return RedirectResponse(url=referer, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/switch-branch")
def switch_branch(
    request: Request,
    branch_id: int = Form(...),
    csrf_token: str = Form(...),
    context: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db)
):
    """Aktif şubeyi session'da değiştirir."""
    if not verify_csrf_token(request, csrf_token):
        raise HTTPException(status_code=400, detail="Geçersiz CSRF jetonu.")

    branch = db.query(Branch).filter(
        Branch.BranchID == branch_id,
        Branch.TenantID == context.effective_tenant_id
    ).first()

    if not branch:
        raise HTTPException(status_code=404, detail="Şube bulunamadı.")

    request.session["active_branch_id"] = branch.BranchID
    referer = request.headers.get("referer") or "/dashboard"
    return RedirectResponse(url=referer, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/tenants")
def create_tenant(
    request: Request,
    tenant_name: str = Form(...),
    initial_branch_name: str = Form("Ana Şube"),
    csrf_token: str = Form(...),
    context: CurrentContext = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """Süper Admin için yeni tenant (işletme) açar."""
    if not verify_csrf_token(request, csrf_token):
        raise HTTPException(status_code=400, detail="Geçersiz CSRF jetonu.")

    new_t = Tenant(TenantName=tenant_name.strip(), IsActive=1)
    db.add(new_t)
    db.flush()

    branch = Branch(TenantID=new_t.TenantID, BranchName=initial_branch_name.strip(), IsActive=1)
    db.add(branch)
    db.commit()

    request.session["selected_tenant_id"] = new_t.TenantID
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)
