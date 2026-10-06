"""
FastAPI Dependency injection ve oturum/yetkilendirme muhafızları (guards).
"""

from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Tenant, Branch


class CurrentContext:
    """Oturum açmış kullanıcının güncel kimlik ve tenant bağlamı."""
    def __init__(
        self,
        user: User,
        effective_tenant_id: Optional[int],
        active_tenant: Optional[Tenant],
        active_branch_id: Optional[int],
        branches: list[Branch],
        all_tenants: list[Tenant]
    ):
        self.user = user
        self.effective_tenant_id = effective_tenant_id
        self.active_tenant = active_tenant
        self.active_branch_id = active_branch_id
        self.branches = branches
        self.all_tenants = all_tenants


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Oturumdaki kullanıcıyı getirir, giriş yapılmamışsa None döner."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = db.query(User).filter(User.UserID == user_id, User.IsActive == 1).first()
    return user


def get_current_user(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional)
) -> User:
    """Giriş yapılmasını zorunlu kılar. Yapılmamışsa login sayfasına yönlendirir veya 401 verir."""
    if not user:
        if request.url.path.startswith("/api/"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Oturum açmanız gerekiyor.")
        # HTML istekleri için yönlendirme istisnası
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/auth/login"}
        )
    return user


def get_current_context(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> CurrentContext:
    """
    Kullanıcının tenant ve şube bağlamını hesaplar.
    Süper admin için session'daki aktif tenant kullanılır, normal kullanıcı için kendi TenantID'si sabittir.
    """
    effective_tenant_id: Optional[int] = None
    all_tenants: list[Tenant] = []

    if user.IsSuperAdmin:
        all_tenants = db.query(Tenant).filter(Tenant.IsActive == 1).order_by(Tenant.TenantName).all()
        # Süper admin session'ında seçili tenant var mı?
        selected_tenant_id = request.session.get("selected_tenant_id")
        if selected_tenant_id:
            effective_tenant_id = int(selected_tenant_id)
        elif all_tenants:
            # Varsayılan olarak ilk aktif tenant'ı seç
            effective_tenant_id = all_tenants[0].TenantID
            request.session["selected_tenant_id"] = effective_tenant_id
    else:
        # Normal kullanıcı kendi tenant'ı dışına asla çıkamaz
        effective_tenant_id = user.TenantID

    active_tenant = None
    branches: list[Branch] = []
    if effective_tenant_id:
        active_tenant = db.query(Tenant).filter(Tenant.TenantID == effective_tenant_id).first()
        branches = db.query(Branch).filter(
            Branch.TenantID == effective_tenant_id,
            Branch.IsActive == 1
        ).order_by(Branch.BranchName).all()

    # Aktif şube seçimi
    active_branch_id = request.session.get("active_branch_id")
    branch_ids = [b.BranchID for b in branches]
    
    if active_branch_id and int(active_branch_id) in branch_ids:
        active_branch_id = int(active_branch_id)
    elif user.DefaultBranchID and user.DefaultBranchID in branch_ids:
        active_branch_id = user.DefaultBranchID
        request.session["active_branch_id"] = active_branch_id
    elif branches:
        active_branch_id = branches[0].BranchID
        request.session["active_branch_id"] = active_branch_id
    else:
        active_branch_id = None

    return CurrentContext(
        user=user,
        effective_tenant_id=effective_tenant_id,
        active_tenant=active_tenant,
        active_branch_id=active_branch_id,
        branches=branches,
        all_tenants=all_tenants
    )


def require_super_admin(context: CurrentContext = Depends(get_current_context)) -> CurrentContext:
    """Yalnızca Süper Admin rolüne izin verir."""
    if not context.user.IsSuperAdmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu işlem için Süper Admin yetkisi gereklidir.")
    return context


def require_can_manage_sales(context: CurrentContext = Depends(get_current_context)) -> CurrentContext:
    """Satış yapma iznini (CanManageSales) kontrol eder."""
    if not (context.user.IsSuperAdmin or context.user.CanManageSales):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Satış ekranına erişim yetkiniz bulunmamaktadır.")
    return context


def require_can_manage_purchases(context: CurrentContext = Depends(get_current_context)) -> CurrentContext:
    """Mal alış iznini (CanManagePurchases) kontrol eder."""
    if not (context.user.IsSuperAdmin or context.user.CanManagePurchases):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Mal alış ekranına erişim yetkiniz bulunmamaktadır.")
    return context


def require_can_manage_cash_register(context: CurrentContext = Depends(get_current_context)) -> CurrentContext:
    """Kasa sayımı iznini (CanManageCashRegister) kontrol eder."""
    if not (context.user.IsSuperAdmin or context.user.CanManageCashRegister):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Kasa yönetimi ekranına erişim yetkiniz bulunmamaktadır.")
    return context


def require_can_view_reports(context: CurrentContext = Depends(get_current_context)) -> CurrentContext:
    """Raporları görüntüleme iznini (CanViewReports) kontrol eder."""
    if not (context.user.IsSuperAdmin or context.user.CanViewReports):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Raporlar ekranına erişim yetkiniz bulunmamaktadır.")
    return context


def require_can_manage_users(context: CurrentContext = Depends(get_current_context)) -> CurrentContext:
    """Personel yönetimi iznini (CanManageUsers) kontrol eder."""
    if not (context.user.IsSuperAdmin or context.user.CanManageUsers):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Personel yönetimi yetkiniz bulunmamaktadır.")
    return context
