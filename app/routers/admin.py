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


# -------------------------------------------------------------
# STOK KARTLARI YÖNETİMİ (Tüm Tenant'lar İçin Ortak Kart Yönetimi)
# -------------------------------------------------------------

@router.get("/products", response_class=HTMLResponse)
def products_page(
    request: Request,
    context: CurrentContext = Depends(require_can_manage_users),
    db: Session = Depends(get_db)
):
    """
    Stok Kartları yönetim sayfası.
    Burada ürünün özellikleri (ad, barkod, paket/barem tipi, koli çarpanı, satış fiyatı, kritik stok)
    tam teşekküllü bir stok kartı olarak yönetilir.
    """
    from app.models import Product

    # Aktif işletmenin stok kartları
    products = db.query(Product).filter(
        Product.TenantID == context.effective_tenant_id
    ).order_by(Product.ProductName.asc()).all()

    return templates.TemplateResponse("admin_products.html", {
        "request": request,
        "user": context.user,
        "active_tenant": context.active_tenant,
        "active_branch_id": context.active_branch_id,
        "branches": context.branches,
        "all_tenants": context.all_tenants,
        "products": products,
        "csrf_token": generate_csrf_token(request),
        "active_page": "admin_products"
    })


@router.post("/products")
def create_stock_card(
    request: Request,
    product_name: str = Form(...),
    barcode: Optional[str] = Form(None),
    package_type: str = Form("Adet"),
    package_multiplier: int = Form(1),
    current_sale_price: float = Form(...),
    critical_stock_level: float = Form(0.0),
    apply_all_tenants: Optional[str] = Form(None),  # Kartı sistemdeki tüm işletmelerde geçerli kıl
    csrf_token: str = Form(...),
    context: CurrentContext = Depends(require_can_manage_users),
    db: Session = Depends(get_db)
):
    """
    Yeni stok kartı tanımlar.
    Kullanıcı isterse kartı tüm işletmelerde (all tenants) tek seferde geçerli kılar.
    """
    from app.models import Product

    if not verify_csrf_token(request, csrf_token):
        raise HTTPException(status_code=400, detail="Geçersiz CSRF jetonu.")

    mult = max(1, package_multiplier)
    pkg_type = package_type.strip() if package_type and package_type.strip() else ("Adet" if mult == 1 else f"{mult}'li Paket")
    bcode = barcode.strip() if barcode and barcode.strip() else None
    pname = product_name.strip()

    target_tenant_ids = [context.effective_tenant_id]
    if apply_all_tenants == "1":
        all_t = db.query(Tenant.TenantID).filter(Tenant.IsActive == 1).all()
        target_tenant_ids = [t[0] for t in all_t]

    for t_id in target_tenant_ids:
        # Aynı barkod veya ad varsa o tenantta güncelle veya ekle
        existing = db.query(Product).filter(
            Product.TenantID == t_id,
            (Product.ProductName == pname) | ((Product.Barcode == bcode) if bcode else False)
        ).first()

        if existing:
            existing.ProductName = pname
            existing.Barcode = bcode
            existing.PackageType = pkg_type
            existing.PackageMultiplier = mult
            existing.CurrentSalePrice = current_sale_price
            existing.CriticalStockLevel = critical_stock_level
            existing.IsActive = 1
        else:
            new_p = Product(
                TenantID=t_id,
                ProductName=pname,
                Barcode=bcode,
                PackageType=pkg_type,
                PackageMultiplier=mult,
                CurrentSalePrice=current_sale_price,
                CriticalStockLevel=critical_stock_level,
                StockQty=0.0,
                IsActive=1
            )
            db.add(new_p)

    db.commit()
    return RedirectResponse(url="/admin/products", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/products/{product_id}")
def update_stock_card(
    product_id: int,
    request: Request,
    product_name: str = Form(...),
    barcode: Optional[str] = Form(None),
    package_type: str = Form("Adet"),
    package_multiplier: int = Form(1),
    current_sale_price: float = Form(...),
    critical_stock_level: float = Form(0.0),
    apply_all_tenants: Optional[str] = Form(None),
    csrf_token: str = Form(...),
    context: CurrentContext = Depends(require_can_manage_users),
    db: Session = Depends(get_db)
):
    """Mevcut stok kartının özelliklerini günceller."""
    from app.models import Product

    if not verify_csrf_token(request, csrf_token):
        raise HTTPException(status_code=400, detail="Geçersiz CSRF jetonu.")

    prod = db.query(Product).filter(
        Product.ProductID == product_id,
        Product.TenantID == context.effective_tenant_id
    ).first()

    if not prod:
        raise HTTPException(status_code=404, detail="Stok kartı bulunamadı.")

    mult = max(1, package_multiplier)
    pkg_type = package_type.strip() if package_type and package_type.strip() else ("Adet" if mult == 1 else f"{mult}'li Paket")
    bcode = barcode.strip() if barcode and barcode.strip() else None
    pname = product_name.strip()

    prod.ProductName = pname
    prod.Barcode = bcode
    prod.PackageType = pkg_type
    prod.PackageMultiplier = mult
    prod.CurrentSalePrice = current_sale_price
    prod.CriticalStockLevel = critical_stock_level

    # Diğer işletmelerde de güncelle
    if apply_all_tenants == "1":
        other_prods = db.query(Product).filter(
            Product.TenantID != context.effective_tenant_id,
            (Product.ProductName == pname) | ((Product.Barcode == bcode) if bcode else False)
        ).all()
        for op in other_prods:
            op.ProductName = pname
            op.Barcode = bcode
            op.PackageType = pkg_type
            op.PackageMultiplier = mult
            op.CurrentSalePrice = current_sale_price
            op.CriticalStockLevel = critical_stock_level

    db.commit()
    return RedirectResponse(url="/admin/products", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/products/sync-all")
def sync_stock_cards_to_all_tenants(
    request: Request,
    csrf_token: str = Form(...),
    context: CurrentContext = Depends(require_can_manage_users),
    db: Session = Depends(get_db)
):
    """
    Aktif işletmedeki tüm stok kartlarını diğer tüm işletmelerde eksiksiz oluşturur / senkronize eder.
    'Her tenantta kartlar geçerli olsun' kuralını tam otomatikleştirir.
    """
    from app.models import Product

    if not verify_csrf_token(request, csrf_token):
        raise HTTPException(status_code=400, detail="Geçersiz CSRF jetonu.")

    current_products = db.query(Product).filter(
        Product.TenantID == context.effective_tenant_id,
        Product.IsActive == 1
    ).all()

    other_tenants = db.query(Tenant).filter(
        Tenant.TenantID != context.effective_tenant_id,
        Tenant.IsActive == 1
    ).all()

    for target_t in other_tenants:
        for p in current_products:
            exists = db.query(Product).filter(
                Product.TenantID == target_t.TenantID,
                (Product.ProductName == p.ProductName) | ((Product.Barcode == p.Barcode) if p.Barcode else False)
            ).first()

            if not exists:
                new_copy = Product(
                    TenantID=target_t.TenantID,
                    ProductName=p.ProductName,
                    Barcode=p.Barcode,
                    PackageType=p.PackageType,
                    PackageMultiplier=p.PackageMultiplier,
                    CurrentSalePrice=p.CurrentSalePrice,
                    CriticalStockLevel=p.CriticalStockLevel,
                    StockQty=0.0,
                    IsActive=1
                )
                db.add(new_copy)
            else:
                exists.PackageType = p.PackageType
                exists.PackageMultiplier = p.PackageMultiplier
                exists.CurrentSalePrice = p.CurrentSalePrice
                exists.CriticalStockLevel = p.CriticalStockLevel

    db.commit()
    return RedirectResponse(url="/admin/products", status_code=status.HTTP_303_SEE_OTHER)
