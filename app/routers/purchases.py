"""
Mal Alış ve Ürün Yönetimi Router'ı.
Mal alış girişi yapıldığında ürün stok miktarı transaction içinde artırılır.
"""

from typing import Optional
from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.models import Product, Purchase
from app.deps import get_current_context, require_can_manage_purchases, CurrentContext
from app.security import generate_csrf_token, verify_csrf_token

router = APIRouter(prefix="/purchases", tags=["purchases"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def purchases_page(
    request: Request,
    context: CurrentContext = Depends(require_can_manage_purchases),
    db: Session = Depends(get_db)
):
    """Mal alış ekranı."""
    if not context.effective_tenant_id:
        raise HTTPException(status_code=400, detail="Aktif işletme bulunamadı.")

    # Ürün listesi ve son maliyet bilgileri
    sql = """
        SELECT 
            p.ProductID,
            p.ProductName,
            p.Barcode,
            p.CurrentSalePrice,
            p.StockQty,
            (SELECT UnitCost FROM Purchases WHERE ProductID = p.ProductID ORDER BY PurchaseDate DESC, PurchaseID DESC LIMIT 1) AS LastUnitCost
        FROM Products p
        WHERE p.TenantID = :tenant_id AND p.IsActive = 1
        ORDER BY p.ProductName ASC
    """
    products = db.execute(text(sql), {"tenant_id": context.effective_tenant_id}).mappings().all()

    # Son 15 alış hareketi
    recent_purchases = db.query(Purchase).filter(
        Purchase.TenantID == context.effective_tenant_id
    ).order_by(Purchase.PurchaseDate.desc(), Purchase.PurchaseID.desc()).limit(15).all()

    return templates.TemplateResponse("purchases.html", {
        "request": request,
        "user": context.user,
        "active_tenant": context.active_tenant,
        "active_branch_id": context.active_branch_id,
        "branches": context.branches,
        "all_tenants": context.all_tenants,
        "products": products,
        "recent_purchases": recent_purchases,
        "csrf_token": generate_csrf_token(request),
        "active_page": "purchases"
    })


@router.post("")
def add_purchase(
    request: Request,
    product_id: int = Form(...),
    price_mode: str = Form("unit"),  # 'unit' (tek adet alış fiyatı) veya 'package' (koli/paket toplam fiyatı)
    unit_cost: float = Form(...),    # Girilen fiyata göre birim maliyet veya paket fiyatı
    package_type: str = Form("Adet"),  # 'Adet', '24 lü Koli', '12 li Paket', 'Özel'
    package_multiplier: int = Form(1),  # Koli/Paket içi adet (örn: 24)
    package_count: float = Form(1),     # Kaç koli veya kaç adet alındığı
    supplier_name: Optional[str] = Form(None),
    branch_id: Optional[str] = Form(None),
    csrf_token: str = Form(...),
    context: CurrentContext = Depends(require_can_manage_purchases),
    db: Session = Depends(get_db)
):
    """
    Mal alış kaydı ekler ve ürün stoğunu artırır (Tek transaction).
    Barem/Koli desteği:
    - Örn: 5 koli 24'lü ayran alındığında stoğa 5 * 24 = 120 adet eklenir.
    - Koli toplam fiyatı girildiyse (price_mode == 'package'), birim adet maliyeti otomatik hesaplanır.
    """
    if not verify_csrf_token(request, csrf_token):
        raise HTTPException(status_code=400, detail="Geçersiz CSRF jetonu.")

    effective_branch = int(branch_id) if branch_id and branch_id.isdigit() else context.active_branch_id
    multiplier = max(1, package_multiplier)
    count = max(0.01, package_count)

    # Toplam stoğa girecek tekil adet
    total_qty = round(count * multiplier, 2)

    # Birim tekil maliyet (1 adedin maliyeti)
    if price_mode == "package":
        # 1 koli/paket fiyatı girilmiş demektir
        calculated_unit_cost = round(unit_cost / multiplier, 4)
    else:
        # Doğrudan 1 adedin birim maliyeti girilmiş demektir
        calculated_unit_cost = round(unit_cost, 4)

    try:
        # Ürünü bul ve kilitle
        product = db.query(Product).filter(
            Product.ProductID == product_id,
            Product.TenantID == context.effective_tenant_id
        ).with_for_update().first()

        if not product:
            raise HTTPException(status_code=404, detail="Ürün bulunamadı veya yetkisiz erişim.")

        purchase = Purchase(
            TenantID=context.effective_tenant_id,
            ProductID=product.ProductID,
            BranchID=effective_branch,
            UnitCost=calculated_unit_cost,
            Quantity=total_qty,
            PackageMultiplier=multiplier,
            PackageType=package_type.strip() if package_type else "Adet",
            SupplierName=supplier_name.strip() if supplier_name else None
        )
        db.add(purchase)

        # Stok miktarını tekil adet olarak artır
        product.StockQty = round(product.StockQty + total_qty, 2)

        db.commit()
    except Exception:
        db.rollback()
        raise

    return RedirectResponse(url="/purchases", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/new-product")
def create_new_product(
    request: Request,
    product_name: str = Form(...),
    barcode: Optional[str] = Form(None),
    current_sale_price: float = Form(...),
    critical_stock_level: float = Form(0.0),
    csrf_token: str = Form(...),
    context: CurrentContext = Depends(require_can_manage_purchases),
    db: Session = Depends(get_db)
):
    """Yeni ürün kartı oluşturur."""
    if not verify_csrf_token(request, csrf_token):
        raise HTTPException(status_code=400, detail="Geçersiz CSRF jetonu.")

    prod = Product(
        TenantID=context.effective_tenant_id,
        ProductName=product_name.strip(),
        Barcode=barcode.strip() if barcode and barcode.strip() else None,
        CurrentSalePrice=current_sale_price,
        CriticalStockLevel=critical_stock_level,
        StockQty=0.0,
        IsActive=1
    )
    db.add(prod)
    db.commit()

    return RedirectResponse(url="/purchases", status_code=status.HTTP_303_SEE_OTHER)
