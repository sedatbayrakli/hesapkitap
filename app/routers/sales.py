"""
Hızlı Satış Router'ı: Ürün listeleme ve stok azaltımlı sepet satışı.
"""

from typing import List
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Product, Sale
from app.deps import get_current_context, require_can_manage_sales, CurrentContext
from app.security import generate_csrf_token, verify_csrf_token

router = APIRouter(prefix="/sales", tags=["sales"])
templates = Jinja2Templates(directory="app/templates")


class SaleItemSchema(BaseModel):
    product_id: int
    price: float = Field(..., ge=0)
    quantity: float = Field(..., gt=0)


class CheckoutRequest(BaseModel):
    payment_type: str = Field(..., pattern="^(CASH|CARD)$")
    items: List[SaleItemSchema]


@router.get("", response_class=HTMLResponse)
def sales_page(
    request: Request,
    context: CurrentContext = Depends(require_can_manage_sales),
    db: Session = Depends(get_db)
):
    """Hızlı satış ekranını render eder."""
    if not context.effective_tenant_id:
        raise HTTPException(status_code=400, detail="Aktif bir işletme seçilmedi.")

    # Kiracıya ait aktif ürünler
    products = db.query(Product).filter(
        Product.TenantID == context.effective_tenant_id,
        Product.IsActive == 1
    ).order_by(Product.ProductName).all()

    return templates.TemplateResponse("sales.html", {
        "request": request,
        "user": context.user,
        "active_tenant": context.active_tenant,
        "active_branch_id": context.active_branch_id,
        "branches": context.branches,
        "all_tenants": context.all_tenants,
        "products": products,
        "csrf_token": generate_csrf_token(request),
        "active_page": "sales"
    })


@router.post("/checkout")
def process_checkout(
    request: Request,
    payload: CheckoutRequest,
    context: CurrentContext = Depends(require_can_manage_sales),
    db: Session = Depends(get_db)
):
    """
    Satış işlemini ve stok düşümünü TEK transaction içinde gerçekleştirir.
    Hata durumunda otomatik rollback yapılır.
    """
    # CSRF Doğrulama (Header'dan)
    csrf_token = request.headers.get("X-CSRF-Token")
    if not verify_csrf_token(request, csrf_token):
        return JSONResponse(status_code=400, content={"success": False, "message": "Geçersiz güvenlik doğrulaması (CSRF)."})

    if not context.effective_tenant_id:
        return JSONResponse(status_code=400, content={"success": False, "message": "Aktif bir işletme bulunamadı."})

    if not context.active_branch_id:
        return JSONResponse(status_code=400, content={"success": False, "message": "Lütfen önce aktif bir şube seçiniz."})

    if not payload.items:
        return JSONResponse(status_code=400, content={"success": False, "message": "Sepette satılacak ürün bulunamadı."})

    try:
        # Transaction Başlangıcı
        for item in payload.items:
            # Ürünün kiracıya ait olduğunu kontrol et ve stok kilitle
            product = db.query(Product).filter(
                Product.ProductID == item.product_id,
                Product.TenantID == context.effective_tenant_id,
                Product.IsActive == 1
            ).with_for_update().first()

            if not product:
                db.rollback()
                return JSONResponse(status_code=404, content={
                    "success": False, 
                    "message": f"Ürün bulunamadı veya yetkisiz erişim (ID: {item.product_id})"
                })

            # Satış kaydı oluştur
            sale = Sale(
                TenantID=context.effective_tenant_id,
                BranchID=context.active_branch_id,
                ProductID=product.ProductID,
                SalePrice=item.price,
                Quantity=item.quantity,
                PaymentType=payload.payment_type,
                UserID=context.user.UserID
            )
            db.add(sale)

            # Ürün stok miktarını azalt
            product.StockQty = round(product.StockQty - item.quantity, 2)

        db.commit()
        return {"success": True, "message": "Satış işlemi başarıyla tamamlandı."}

    except Exception as exc:
        db.rollback()
        return JSONResponse(status_code=500, content={
            "success": False,
            "message": f"Satış kaydedilirken bir hata oluştu: {str(exc)}"
        })
