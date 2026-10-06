"""
Dashboard Yönlendiricisi: Kullanıcının yetkisine göre uygun ilk ekrana yönlendirir.
"""

from fastapi import APIRouter, Request, Depends, status
from fastapi.responses import RedirectResponse
from app.deps import get_current_context, CurrentContext

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard_redirect(
    request: Request,
    context: CurrentContext = Depends(get_current_context)
):
    """
    Kullanıcının ilk yetkili olduğu ekrana yönlendirir:
    1. Satış (CanManageSales)
    2. Kasa (CanManageCashRegister)
    3. Mal Alış (CanManagePurchases)
    4. Raporlar (CanViewReports)
    5. Yönetim (CanManageUsers)
    """
    user = context.user
    if user.IsSuperAdmin or user.CanManageSales:
        return RedirectResponse(url="/sales", status_code=status.HTTP_303_SEE_OTHER)
    elif user.CanManageCashRegister:
        return RedirectResponse(url="/register", status_code=status.HTTP_303_SEE_OTHER)
    elif user.CanManagePurchases:
        return RedirectResponse(url="/purchases", status_code=status.HTTP_303_SEE_OTHER)
    elif user.CanViewReports:
        return RedirectResponse(url="/reports", status_code=status.HTTP_303_SEE_OTHER)
    elif user.CanManageUsers:
        return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)

    # Hiçbir yetki yoksa bile oturum açık kalabilir
    return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
