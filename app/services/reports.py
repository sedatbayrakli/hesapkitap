"""
Raporlama ve finansal analiz hesaplama servisleri.
"""

from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text


def get_kpi_summary(
    db: Session,
    tenant_id: int,
    start_date: date,
    end_date: date,
    branch_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Belirli tarih aralığı ve şube için ciro (nakit+kart), alış, masraf ve kâr hesaplar.
    """
    branch_filter = "AND BranchID = :branch_id" if branch_id else ""
    params = {
        "tenant_id": tenant_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat()
    }
    if branch_id:
        params["branch_id"] = branch_id

    # 1. Satış Gelirleri
    sales_sql = f"""
        SELECT 
            COALESCE(SUM(CASE WHEN PaymentType = 'CASH' THEN SalePrice * Quantity ELSE 0 END), 0) AS CashRevenue,
            COALESCE(SUM(CASE WHEN PaymentType = 'CARD' THEN SalePrice * Quantity ELSE 0 END), 0) AS CardRevenue,
            COALESCE(SUM(SalePrice * Quantity), 0) AS TotalRevenue,
            COALESCE(COUNT(SaleID), 0) AS TransactionCount
        FROM Sales
        WHERE TenantID = :tenant_id
          AND DATE(SaleDate) BETWEEN :start_date AND :end_date
          {branch_filter}
    """
    sales_res = db.execute(text(sales_sql), params).mappings().one()

    # 2. Alış Giderleri
    pur_branch_filter = "AND (BranchID = :branch_id OR BranchID IS NULL)" if branch_id else ""
    pur_sql = f"""
        SELECT 
            COALESCE(SUM(UnitCost * Quantity), 0) AS TotalPurchases
        FROM Purchases
        WHERE TenantID = :tenant_id
          AND DATE(PurchaseDate) BETWEEN :start_date AND :end_date
          {pur_branch_filter}
    """
    pur_res = db.execute(text(pur_sql), params).mappings().one()

    # 3. Kasa Masrafları (DailyRegister)
    exp_sql = f"""
        SELECT 
            COALESCE(SUM(ExpenseTotal), 0) AS TotalExpense
        FROM DailyRegister
        WHERE TenantID = :tenant_id
          AND RegisterDate BETWEEN :start_date AND :end_date
          {branch_filter}
    """
    exp_res = db.execute(text(exp_sql), params).mappings().one()

    total_revenue = float(sales_res["TotalRevenue"])
    cash_revenue = float(sales_res["CashRevenue"])
    card_revenue = float(sales_res["CardRevenue"])
    total_purchases = float(pur_res["TotalPurchases"])
    total_expense = float(exp_res["TotalExpense"])
    net_profit = round(total_revenue - total_purchases - total_expense, 2)
    profit_margin = round((net_profit / total_revenue * 100), 1) if total_revenue > 0 else 0.0

    return {
        "total_revenue": total_revenue,
        "cash_revenue": cash_revenue,
        "card_revenue": card_revenue,
        "transaction_count": int(sales_res["TransactionCount"]),
        "total_purchases": total_purchases,
        "total_expense": total_expense,
        "net_profit": net_profit,
        "profit_margin": profit_margin
    }


def get_trend_chart_data(
    db: Session,
    tenant_id: int,
    start_date: date,
    end_date: date,
    branch_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Günlük bazda nakit ve kart satış trendi (Çizgi Grafik için).
    """
    branch_filter = "AND BranchID = :branch_id" if branch_id else ""
    params = {
        "tenant_id": tenant_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat()
    }
    if branch_id:
        params["branch_id"] = branch_id

    sql = f"""
        SELECT 
            DATE(SaleDate) as sale_day,
            COALESCE(SUM(CASE WHEN PaymentType = 'CASH' THEN SalePrice * Quantity ELSE 0 END), 0) AS cash_val,
            COALESCE(SUM(CASE WHEN PaymentType = 'CARD' THEN SalePrice * Quantity ELSE 0 END), 0) AS card_val
        FROM Sales
        WHERE TenantID = :tenant_id
          AND DATE(SaleDate) BETWEEN :start_date AND :end_date
          {branch_filter}
        GROUP BY DATE(SaleDate)
        ORDER BY DATE(SaleDate) ASC
    """
    rows = db.execute(text(sql), params).mappings().all()

    # Tarih aralığını doldur
    curr = start_date
    date_map = {r["sale_day"]: r for r in rows}
    labels = []
    cash_series = []
    card_series = []

    while curr <= end_date:
        key = curr.isoformat()
        labels.append(curr.strftime("%d.%m"))
        if key in date_map:
            cash_series.append(float(date_map[key]["cash_val"]))
            card_series.append(float(date_map[key]["card_val"]))
        else:
            cash_series.append(0.0)
            card_series.append(0.0)
        curr += timedelta(days=1)

    return {
        "labels": labels,
        "cash_series": cash_series,
        "card_series": card_series
    }


def get_branch_comparison_data(
    db: Session,
    tenant_id: int,
    start_date: date,
    end_date: date
) -> Dict[str, Any]:
    """
    Şubeler arası ciro karşılaştırma çubuk grafiği verisi.
    """
    params = {
        "tenant_id": tenant_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat()
    }
    sql = """
        SELECT 
            b.BranchName,
            COALESCE(SUM(s.SalePrice * s.Quantity), 0) AS TotalRevenue
        FROM Branches b
        LEFT JOIN Sales s ON b.BranchID = s.BranchID 
                          AND s.TenantID = :tenant_id 
                          AND DATE(s.SaleDate) BETWEEN :start_date AND :end_date
        WHERE b.TenantID = :tenant_id AND b.IsActive = 1
        GROUP BY b.BranchID, b.BranchName
        ORDER BY TotalRevenue DESC
    """
    rows = db.execute(text(sql), params).mappings().all()
    return {
        "labels": [r["BranchName"] for r in rows],
        "values": [float(r["TotalRevenue"]) for r in rows]
    }


def get_product_profitability(
    db: Session,
    tenant_id: int
) -> List[Dict[str, Any]]:
    """
    vw_ProductProfitMargins view'ından ürün bazında marj ve satış verileri.
    """
    sql = """
        SELECT 
            ProductID,
            Barcode,
            ProductName,
            CurrentSalePrice,
            StockQty,
            CriticalStockLevel,
            LastUnitCost,
            AvgUnitCost,
            ProfitMarginAmount,
            ProfitMarginPercent,
            TotalSoldQty,
            CASE WHEN StockQty <= CriticalStockLevel THEN 1 ELSE 0 END AS IsCriticalStock
        FROM vw_ProductProfitMargins
        WHERE TenantID = :tenant_id AND IsActive = 1
        ORDER BY TotalSoldQty DESC, ProductName ASC
    """
    rows = db.execute(text(sql), {"tenant_id": tenant_id}).mappings().all()
    return [dict(r) for r in rows]
