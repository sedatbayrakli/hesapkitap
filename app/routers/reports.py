"""
Raporlar ve Finansal Kârlılık Router'ı.
KPI kartları, Chart.js grafik verileri, ürün kâr marjları ve CSV/PDF indirme.
"""

import io
import csv
from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException, Response, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import get_current_context, require_can_view_reports, CurrentContext
from app.security import generate_csrf_token
from app.services.reports import (
    get_kpi_summary,
    get_trend_chart_data,
    get_branch_comparison_data,
    get_product_profitability
)

router = APIRouter(prefix="/reports", tags=["reports"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def reports_page(
    request: Request,
    range: str = Query("7d", regex="^(today|7d|30d)$"),
    branch_id: Optional[str] = Query(None),
    context: CurrentContext = Depends(require_can_view_reports),
    db: Session = Depends(get_db)
):
    """Raporlar ve grafikler ana sayfası."""
    today = date.today()
    if range == "today":
        start_date = today
        end_date = today
    elif range == "30d":
        start_date = today - timedelta(days=30)
        end_date = today
    else:  # 7d
        start_date = today - timedelta(days=7)
        end_date = today

    selected_branch = int(branch_id) if branch_id and branch_id.isdigit() else None

    # 1. KPI Hesaplamaları
    kpi = get_kpi_summary(
        db=db,
        tenant_id=context.effective_tenant_id,
        start_date=start_date,
        end_date=end_date,
        branch_id=selected_branch
    )

    # 2. Günlük Trend Çizgi Grafiği
    trend_data = get_trend_chart_data(
        db=db,
        tenant_id=context.effective_tenant_id,
        start_date=start_date,
        end_date=end_date,
        branch_id=selected_branch
    )

    # 3. Şube Karşılaştırma Grafiği
    branch_comparison = get_branch_comparison_data(
        db=db,
        tenant_id=context.effective_tenant_id,
        start_date=start_date,
        end_date=end_date
    )

    # 4. Ürün Kârlılık Tablosu
    product_margins = get_product_profitability(
        db=db,
        tenant_id=context.effective_tenant_id
    )

    return templates.TemplateResponse("reports.html", {
        "request": request,
        "user": context.user,
        "active_tenant": context.active_tenant,
        "active_branch_id": context.active_branch_id,
        "branches": context.branches,
        "all_tenants": context.all_tenants,
        "selected_range": range,
        "selected_branch_id": selected_branch,
        "end_date_str": today.isoformat(),
        "kpi": kpi,
        "trend_data": trend_data,
        "branch_comparison": branch_comparison,
        "product_margins": product_margins,
        "csrf_token": generate_csrf_token(request),
        "active_page": "reports"
    })


@router.get("/export-csv")
def export_csv_report(
    range: str = Query("7d"),
    branch_id: Optional[str] = Query(None),
    context: CurrentContext = Depends(require_can_view_reports),
    db: Session = Depends(get_db)
):
    """Ürün kârlılık ve satış verilerini CSV olarak dışa aktarır."""
    products = get_product_profitability(db=db, tenant_id=context.effective_tenant_id)

    output = io.StringIO()
    # UTF-8 BOM ekle (Excel'in Türkçe karakterleri düzgün açması için)
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';')

    # Başlık satırı
    writer.writerow(["Ürün ID", "Barkod", "Ürün Adı", "Son Alış Maliyeti (TL)", "Satış Fiyatı (TL)", "Kâr Marjı (TL)", "Kâr Marjı (%)", "Kalan Stok", "Toplam Satılan Adet"])

    for p in products:
        writer.writerow([
            p["ProductID"],
            p["Barcode"] or "",
            p["ProductName"],
            f"{p['LastUnitCost']:.2f}",
            f"{p['CurrentSalePrice']:.2f}",
            f"{p['ProfitMarginAmount']:.2f}",
            f"{p['ProfitMarginPercent']:.1f}%",
            p["StockQty"],
            p["TotalSoldQty"]
        ])

    csv_data = output.getvalue()
    filename = f"KantinPos_Karlilik_Raporu_{date.today().isoformat()}.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
