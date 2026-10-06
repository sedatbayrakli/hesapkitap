"""
Gün Sonu Kasa Sayımı ve Z-Raporu Router'ı.
"""

from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Request, Depends, Form, HTTPException, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.models import DailyRegister, Branch
from app.deps import get_current_context, require_can_manage_cash_register, CurrentContext
from app.security import generate_csrf_token, verify_csrf_token
from app.services.reports import get_kpi_summary
from app.services.pdf import generate_z_report_pdf

router = APIRouter(prefix="/register", tags=["register"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def register_page(
    request: Request,
    context: CurrentContext = Depends(require_can_manage_cash_register),
    db: Session = Depends(get_db)
):
    """Gün sonu kasa sayım ekranı."""
    today_str = date.today().isoformat()
    return templates.TemplateResponse("register.html", {
        "request": request,
        "user": context.user,
        "active_tenant": context.active_tenant,
        "active_branch_id": context.active_branch_id,
        "branches": context.branches,
        "all_tenants": context.all_tenants,
        "today_str": today_str,
        "csrf_token": generate_csrf_token(request),
        "active_page": "register"
    })


@router.get("/api/check")
def check_existing_register(
    branch_id: int,
    date: str,
    context: CurrentContext = Depends(require_can_manage_cash_register),
    db: Session = Depends(get_db)
):
    """Belirli şube ve tarihte kayıtlı kasa var mı kontrol eder."""
    try:
        reg_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Geçersiz tarih"})

    existing = db.query(DailyRegister).filter(
        DailyRegister.TenantID == context.effective_tenant_id,
        DailyRegister.BranchID == branch_id,
        DailyRegister.RegisterDate == reg_date
    ).first()

    if existing:
        return {
            "exists": True,
            "record": {
                "RegisterID": existing.RegisterID,
                "Count200": existing.Count200,
                "Count100": existing.Count100,
                "Count50": existing.Count50,
                "Count20": existing.Count20,
                "Count10": existing.Count10,
                "Count5": existing.Count5,
                "DirectCashTotal": existing.DirectCashTotal,
                "CashTotal": existing.CashTotal,
                "CreditCardTotal": existing.CreditCardTotal,
                "ExpenseTotal": existing.ExpenseTotal,
                "OpeningCash": existing.OpeningCash,
                "Notes": existing.Notes
            }
        }
    return {"exists": False}


@router.post("")
def save_register(
    request: Request,
    branch_id: int = Form(...),
    register_date: str = Form(...),
    count_200: int = Form(0),
    count_100: int = Form(0),
    count_50: int = Form(0),
    count_20: int = Form(0),
    count_10: int = Form(0),
    count_5: int = Form(0),
    direct_cash_total: Optional[float] = Form(None),
    credit_card_total: float = Form(0.0),
    expense_total: float = Form(0.0),
    opening_cash: float = Form(0.0),
    notes: Optional[str] = Form(None),
    overwrite: int = Form(0),
    csrf_token: str = Form(...),
    context: CurrentContext = Depends(require_can_manage_cash_register),
    db: Session = Depends(get_db)
):
    """
    Kasa sayımını kaydeder veya günceller.
    UNIQUE kısıtı sayesinde aynı şube ve gün için mükerrer kayıt engellenir.
    """
    if not verify_csrf_token(request, csrf_token):
        raise HTTPException(status_code=400, detail="Geçersiz CSRF jetonu.")

    reg_date = datetime.strptime(register_date, "%Y-%m-%d").date()

    existing = db.query(DailyRegister).filter(
        DailyRegister.TenantID == context.effective_tenant_id,
        DailyRegister.BranchID == branch_id,
        DailyRegister.RegisterDate == reg_date
    ).first()

    if existing and overwrite == 0:
        raise HTTPException(status_code=400, detail="Bu şube ve tarih için zaten kasa kaydı mevcut. Güncelleme onayı veriniz.")

    if existing:
        # Mevcut kaydı güncelle
        existing.Count200 = count_200
        existing.Count100 = count_100
        existing.Count50 = count_50
        existing.Count20 = count_20
        existing.Count10 = count_10
        existing.Count5 = count_5
        existing.DirectCashTotal = direct_cash_total
        existing.CreditCardTotal = credit_card_total
        existing.ExpenseTotal = expense_total
        existing.OpeningCash = opening_cash
        existing.Notes = notes.strip() if notes else None
    else:
        # Yeni kayıt oluştur
        new_reg = DailyRegister(
            TenantID=context.effective_tenant_id,
            BranchID=branch_id,
            RegisterDate=reg_date,
            Count200=count_200,
            Count100=count_100,
            Count50=count_50,
            Count20=count_20,
            Count10=count_10,
            Count5=count_5,
            DirectCashTotal=direct_cash_total,
            CreditCardTotal=credit_card_total,
            ExpenseTotal=expense_total,
            OpeningCash=opening_cash,
            Notes=notes.strip() if notes else None
        )
        db.add(new_reg)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Bu tarih ve şube için kasa kaydı zaten mevcut!")

    return RedirectResponse(
        url=f"/register?branch_id={branch_id}&date={register_date}&saved=1",
        status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/z-report")
def download_z_report(
    branch_id: int,
    date: str,
    context: CurrentContext = Depends(require_can_manage_cash_register),
    db: Session = Depends(get_db)
):
    """Seçili gün ve şubenin Z-Raporunu PDF formatında üretir."""
    try:
        reg_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih.")

    branch = db.query(Branch).filter(
        Branch.BranchID == branch_id,
        Branch.TenantID == context.effective_tenant_id
    ).first()

    if not branch:
        raise HTTPException(status_code=404, detail="Şube bulunamadı.")

    # Fiziki Kasa Kaydı
    register_row = db.query(DailyRegister).filter(
        DailyRegister.TenantID == context.effective_tenant_id,
        DailyRegister.BranchID == branch_id,
        DailyRegister.RegisterDate == reg_date
    ).first()

    reg_dict = None
    if register_row:
        reg_dict = {
            "Count200": register_row.Count200,
            "Count100": register_row.Count100,
            "Count50": register_row.Count50,
            "Count20": register_row.Count20,
            "Count10": register_row.Count10,
            "Count5": register_row.Count5,
            "DirectCashTotal": register_row.DirectCashTotal,
            "CashTotal": register_row.CashTotal,
            "CreditCardTotal": register_row.CreditCardTotal,
            "ExpenseTotal": register_row.ExpenseTotal,
            "OpeningCash": register_row.OpeningCash,
            "Notes": register_row.Notes
        }

    # Satış ve Ciro Verileri
    sales_kpi = get_kpi_summary(
        db=db,
        tenant_id=context.effective_tenant_id,
        start_date=reg_date,
        end_date=reg_date,
        branch_id=branch_id
    )

    pdf_bytes = generate_z_report_pdf(
        tenant_name=context.active_tenant.TenantName if context.active_tenant else "Kantin",
        branch_name=branch.BranchName,
        report_date=reg_date,
        register_data=reg_dict,
        sales_data=sales_kpi,
        created_by=context.user.FullName
    )

    filename = f"Z_Raporu_{branch.BranchName}_{reg_date.isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"}
    )
