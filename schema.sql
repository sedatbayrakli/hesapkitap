-- KantinPos Veritabanı Şeması ve Seed Verileri (SQLite)

PRAGMA foreign_keys = ON;

-- 1. İşletmeler (Tenants)
CREATE TABLE IF NOT EXISTS Tenants (
    TenantID INTEGER PRIMARY KEY AUTOINCREMENT,
    TenantName TEXT NOT NULL UNIQUE,
    IsActive INTEGER NOT NULL DEFAULT 1,
    CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. Şubeler (Branches)
CREATE TABLE IF NOT EXISTS Branches (
    BranchID INTEGER PRIMARY KEY AUTOINCREMENT,
    TenantID INTEGER NOT NULL,
    BranchName TEXT NOT NULL,
    IsActive INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (TenantID) REFERENCES Tenants(TenantID) ON DELETE CASCADE
);

-- 3. Kullanıcılar (Users)
CREATE TABLE IF NOT EXISTS Users (
    UserID INTEGER PRIMARY KEY AUTOINCREMENT,
    TenantID INTEGER NULL,
    DefaultBranchID INTEGER NULL,
    Username TEXT NOT NULL UNIQUE,
    PasswordHash TEXT NOT NULL,
    FullName TEXT NOT NULL,
    IsSuperAdmin INTEGER NOT NULL DEFAULT 0,
    CanManagePurchases INTEGER NOT NULL DEFAULT 0,
    CanManageSales INTEGER NOT NULL DEFAULT 0,
    CanManageCashRegister INTEGER NOT NULL DEFAULT 0,
    CanViewReports INTEGER NOT NULL DEFAULT 0,
    CanManageUsers INTEGER NOT NULL DEFAULT 0,
    IsActive INTEGER NOT NULL DEFAULT 1,
    CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (TenantID) REFERENCES Tenants(TenantID) ON DELETE CASCADE,
    FOREIGN KEY (DefaultBranchID) REFERENCES Branches(BranchID) ON DELETE SET NULL
);

-- 4. Ürünler (Products)
CREATE TABLE IF NOT EXISTS Products (
    ProductID INTEGER PRIMARY KEY AUTOINCREMENT,
    TenantID INTEGER NOT NULL,
    Barcode TEXT NULL,
    ProductName TEXT NOT NULL,
    CurrentSalePrice REAL NOT NULL,
    StockQty REAL NOT NULL DEFAULT 0,
    CriticalStockLevel REAL NOT NULL DEFAULT 0,
    IsActive INTEGER NOT NULL DEFAULT 1,
    CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (TenantID) REFERENCES Tenants(TenantID) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_products_tenant_barcode ON Products(TenantID, Barcode);
CREATE INDEX IF NOT EXISTS idx_products_tenant_name ON Products(TenantID, ProductName);

-- 5. Mal Alışları (Purchases)
CREATE TABLE IF NOT EXISTS Purchases (
    PurchaseID INTEGER PRIMARY KEY AUTOINCREMENT,
    TenantID INTEGER NOT NULL,
    ProductID INTEGER NOT NULL,
    BranchID INTEGER NULL,
    UnitCost REAL NOT NULL,
    Quantity REAL NOT NULL,
    SupplierName TEXT,
    PurchaseDate DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (TenantID) REFERENCES Tenants(TenantID) ON DELETE CASCADE,
    FOREIGN KEY (ProductID) REFERENCES Products(ProductID) ON DELETE RESTRICT,
    FOREIGN KEY (BranchID) REFERENCES Branches(BranchID) ON DELETE SET NULL
);

-- 6. Satışlar (Sales)
CREATE TABLE IF NOT EXISTS Sales (
    SaleID INTEGER PRIMARY KEY AUTOINCREMENT,
    TenantID INTEGER NOT NULL,
    BranchID INTEGER NOT NULL,
    ProductID INTEGER NOT NULL,
    SalePrice REAL NOT NULL,
    Quantity REAL NOT NULL,
    PaymentType TEXT NOT NULL CHECK(PaymentType IN ('CASH', 'CARD')),
    SaleDate DATETIME DEFAULT CURRENT_TIMESTAMP,
    UserID INTEGER NOT NULL,
    FOREIGN KEY (TenantID) REFERENCES Tenants(TenantID) ON DELETE CASCADE,
    FOREIGN KEY (BranchID) REFERENCES Branches(BranchID) ON DELETE RESTRICT,
    FOREIGN KEY (ProductID) REFERENCES Products(ProductID) ON DELETE RESTRICT,
    FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE RESTRICT
);

-- 7. Gün Sonu Kasa (DailyRegister)
CREATE TABLE IF NOT EXISTS DailyRegister (
    RegisterID INTEGER PRIMARY KEY AUTOINCREMENT,
    TenantID INTEGER NOT NULL,
    BranchID INTEGER NOT NULL,
    RegisterDate DATE NOT NULL,
    Count200 INTEGER NOT NULL DEFAULT 0,
    Count100 INTEGER NOT NULL DEFAULT 0,
    Count50 INTEGER NOT NULL DEFAULT 0,
    Count20 INTEGER NOT NULL DEFAULT 0,
    Count10 INTEGER NOT NULL DEFAULT 0,
    Count5 INTEGER NOT NULL DEFAULT 0,
    DirectCashTotal REAL NULL,
    CashTotal REAL NOT NULL DEFAULT 0,
    CreditCardTotal REAL NOT NULL DEFAULT 0,
    ExpenseTotal REAL NOT NULL DEFAULT 0,
    OpeningCash REAL NOT NULL DEFAULT 0,
    TotalRevenue REAL NOT NULL DEFAULT 0,
    Notes TEXT,
    UNIQUE(TenantID, BranchID, RegisterDate),
    FOREIGN KEY (TenantID) REFERENCES Tenants(TenantID) ON DELETE CASCADE,
    FOREIGN KEY (BranchID) REFERENCES Branches(BranchID) ON DELETE RESTRICT
);

-- DailyRegister Otomatik Hesaplama Tetikleyicileri (Triggers)
DROP TRIGGER IF EXISTS trg_daily_register_insert;
CREATE TRIGGER trg_daily_register_insert AFTER INSERT ON DailyRegister
FOR EACH ROW
BEGIN
    UPDATE DailyRegister
    SET CashTotal = CASE
            WHEN NEW.DirectCashTotal IS NOT NULL THEN NEW.DirectCashTotal
            ELSE (NEW.Count200 * 200 + NEW.Count100 * 100 + NEW.Count50 * 50 + NEW.Count20 * 20 + NEW.Count10 * 10 + NEW.Count5 * 5)
        END,
        TotalRevenue = (
            CASE
                WHEN NEW.DirectCashTotal IS NOT NULL THEN NEW.DirectCashTotal
                ELSE (NEW.Count200 * 200 + NEW.Count100 * 100 + NEW.Count50 * 50 + NEW.Count20 * 20 + NEW.Count10 * 10 + NEW.Count5 * 5)
            END + NEW.CreditCardTotal
        )
    WHERE RegisterID = NEW.RegisterID;
END;

DROP TRIGGER IF EXISTS trg_daily_register_update;
CREATE TRIGGER trg_daily_register_update AFTER UPDATE ON DailyRegister
FOR EACH ROW
WHEN (
    OLD.Count200 != NEW.Count200 OR OLD.Count100 != NEW.Count100 OR OLD.Count50 != NEW.Count50 OR
    OLD.Count20 != NEW.Count20 OR OLD.Count10 != NEW.Count10 OR OLD.Count5 != NEW.Count5 OR
    OLD.DirectCashTotal IS NOT NEW.DirectCashTotal OR OLD.CreditCardTotal != NEW.CreditCardTotal
)
BEGIN
    UPDATE DailyRegister
    SET CashTotal = CASE
            WHEN NEW.DirectCashTotal IS NOT NULL THEN NEW.DirectCashTotal
            ELSE (NEW.Count200 * 200 + NEW.Count100 * 100 + NEW.Count50 * 50 + NEW.Count20 * 20 + NEW.Count10 * 10 + NEW.Count5 * 5)
        END,
        TotalRevenue = (
            CASE
                WHEN NEW.DirectCashTotal IS NOT NULL THEN NEW.DirectCashTotal
                ELSE (NEW.Count200 * 200 + NEW.Count100 * 100 + NEW.Count50 * 50 + NEW.Count20 * 20 + NEW.Count10 * 10 + NEW.Count5 * 5)
            END + NEW.CreditCardTotal
        )
    WHERE RegisterID = NEW.RegisterID;
END;

-- 8. Görünümler (Views)
-- vw_ProductProfitMargins: Son maliyet, ortalama maliyet, son satış fiyatı, kâr marjı
DROP VIEW IF EXISTS vw_ProductProfitMargins;
CREATE VIEW vw_ProductProfitMargins AS
SELECT 
    p.ProductID,
    p.TenantID,
    p.Barcode,
    p.ProductName,
    p.CurrentSalePrice,
    p.StockQty,
    p.CriticalStockLevel,
    p.IsActive,
    COALESCE(last_pur.UnitCost, 0) AS LastUnitCost,
    COALESCE(avg_pur.AvgUnitCost, last_pur.UnitCost, 0) AS AvgUnitCost,
    ROUND(p.CurrentSalePrice - COALESCE(last_pur.UnitCost, 0), 2) AS ProfitMarginAmount,
    CASE 
        WHEN p.CurrentSalePrice > 0 THEN 
            ROUND(((p.CurrentSalePrice - COALESCE(last_pur.UnitCost, 0)) / p.CurrentSalePrice) * 100, 2)
        ELSE 0 
    END AS ProfitMarginPercent,
    COALESCE(sales_summary.TotalSoldQty, 0) AS TotalSoldQty
FROM Products p
LEFT JOIN (
    -- Her ürünün en son alış maliyeti
    SELECT pur.ProductID, pur.UnitCost
    FROM Purchases pur
    INNER JOIN (
        SELECT ProductID, MAX(PurchaseDate) AS MaxDate, MAX(PurchaseID) as MaxID
        FROM Purchases
        GROUP BY ProductID
    ) latest ON pur.ProductID = latest.ProductID AND pur.PurchaseID = latest.MaxID
) last_pur ON p.ProductID = last_pur.ProductID
LEFT JOIN (
    -- Ağırlıklı ya da düz ortalama birim maliyet
    SELECT ProductID, ROUND(SUM(UnitCost * Quantity) / SUM(Quantity), 2) AS AvgUnitCost
    FROM Purchases
    GROUP BY ProductID
) avg_pur ON p.ProductID = avg_pur.ProductID
LEFT JOIN (
    SELECT ProductID, SUM(Quantity) AS TotalSoldQty
    FROM Sales
    GROUP BY ProductID
) sales_summary ON p.ProductID = sales_summary.ProductID;

-- vw_DailyProfit: Günlük ciro, alış, masraf ve kâr
DROP VIEW IF EXISTS vw_DailyProfit;
CREATE VIEW vw_DailyProfit AS
SELECT 
    base.TenantID,
    base.BranchID,
    base.ReportDate,
    COALESCE(s.CashSales, 0) AS CashSales,
    COALESCE(s.CardSales, 0) AS CardSales,
    COALESCE(s.TotalRevenue, 0) AS TotalRevenue,
    COALESCE(p.TotalPurchases, 0) AS TotalPurchases,
    COALESCE(r.ExpenseTotal, 0) AS ExpenseTotal,
    ROUND(COALESCE(s.TotalRevenue, 0) - COALESCE(p.TotalPurchases, 0) - COALESCE(r.ExpenseTotal, 0), 2) AS NetProfit
FROM (
    SELECT TenantID, BranchID, DATE(SaleDate) AS ReportDate FROM Sales
    UNION
    SELECT TenantID, BranchID, DATE(PurchaseDate) AS ReportDate FROM Purchases WHERE BranchID IS NOT NULL
    UNION
    SELECT TenantID, BranchID, DATE(RegisterDate) AS ReportDate FROM DailyRegister
) base
LEFT JOIN (
    SELECT 
        TenantID, 
        BranchID, 
        DATE(SaleDate) AS SaleDateOnly,
        ROUND(SUM(CASE WHEN PaymentType = 'CASH' THEN SalePrice * Quantity ELSE 0 END), 2) AS CashSales,
        ROUND(SUM(CASE WHEN PaymentType = 'CARD' THEN SalePrice * Quantity ELSE 0 END), 2) AS CardSales,
        ROUND(SUM(SalePrice * Quantity), 2) AS TotalRevenue
    FROM Sales
    GROUP BY TenantID, BranchID, DATE(SaleDate)
) s ON base.TenantID = s.TenantID AND base.BranchID = s.BranchID AND base.ReportDate = s.SaleDateOnly
LEFT JOIN (
    SELECT 
        TenantID, 
        BranchID, 
        DATE(PurchaseDate) AS PurchaseDateOnly,
        ROUND(SUM(UnitCost * Quantity), 2) AS TotalPurchases
    FROM Purchases
    WHERE BranchID IS NOT NULL
    GROUP BY TenantID, BranchID, DATE(PurchaseDate)
) p ON base.TenantID = p.TenantID AND base.BranchID = p.BranchID AND base.ReportDate = p.PurchaseDateOnly
LEFT JOIN (
    SELECT 
        TenantID, 
        BranchID, 
        DATE(RegisterDate) AS RegisterDateOnly,
        ROUND(SUM(ExpenseTotal), 2) AS ExpenseTotal
    FROM DailyRegister
    GROUP BY TenantID, BranchID, DATE(RegisterDate)
) r ON base.TenantID = r.TenantID AND base.BranchID = r.BranchID AND base.ReportDate = r.RegisterDateOnly;
