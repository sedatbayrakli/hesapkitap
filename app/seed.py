"""
Veritabanı Başlangıç ve Örnek (Seed) Verileri.
Idempotent çalışır; veritabanında kayıt yoksa oluşturur.
"""

from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy.orm import Session
from app.config import settings
from app.database import engine, SessionLocal
from app.models import Tenant, Branch, User, Product, Purchase, Sale, DailyRegister
from app.security import hash_password


def init_db(db: Session = None):
    """schema.sql dosyasını çalıştırarak tabloları, triggerları ve viewları hazırlar."""
    schema_path = Path(__file__).resolve().parent.parent / "schema.sql"
    if not schema_path.exists():
        schema_path = Path("schema.sql").resolve()

    if schema_path.exists():
        with open(schema_path, "r", encoding="utf-8") as f:
            sql_script = f.read()
        
        with engine.connect() as connection:
            # SQLite script çalıştırma
            raw_conn = connection.connection.dbapi_connection
            raw_conn.executescript(sql_script)

            # Mevcut veritabanında kolon yoksa ekle (Migration)
            cursor = raw_conn.cursor()
            cursor.execute("PRAGMA table_info(Purchases);")
            pur_columns = [row[1] for row in cursor.fetchall()]
            if "PackageMultiplier" not in pur_columns:
                cursor.execute("ALTER TABLE Purchases ADD COLUMN PackageMultiplier INTEGER NOT NULL DEFAULT 1;")
            if "PackageType" not in pur_columns:
                cursor.execute("ALTER TABLE Purchases ADD COLUMN PackageType TEXT NOT NULL DEFAULT 'Adet';")

            cursor.execute("PRAGMA table_info(Products);")
            prod_columns = [row[1] for row in cursor.fetchall()]
            if "PackageMultiplier" not in prod_columns:
                cursor.execute("ALTER TABLE Products ADD COLUMN PackageMultiplier INTEGER NOT NULL DEFAULT 1;")
            if "PackageType" not in prod_columns:
                cursor.execute("ALTER TABLE Products ADD COLUMN PackageType TEXT NOT NULL DEFAULT 'Adet';")

            raw_conn.commit()
            cursor.close()


def seed_data(db: Session):
    """Gerekli başlangıç verilerini ve örnek kayıtları idempotant olarak yükler."""
    # 1. Süper Admin Kontrolü
    super_admin = db.query(User).filter(User.Username == "superadmin").first()
    if not super_admin:
        admin_pass = settings.ADMIN_PASSWORD
        super_admin = User(
            TenantID=None,
            DefaultBranchID=None,
            Username="superadmin",
            PasswordHash=hash_password(admin_pass),
            FullName="Sistem Süper Yöneticisi",
            IsSuperAdmin=1,
            CanManagePurchases=1,
            CanManageSales=1,
            CanManageCashRegister=1,
            CanViewReports=1,
            CanManageUsers=1,
            IsActive=1
        )
        db.add(super_admin)
        db.flush()

    # 2. Örnek Tenant A: "Örnek Kantin A"
    tenant_a = db.query(Tenant).filter(Tenant.TenantName == "Örnek Kantin A").first()
    if not tenant_a:
        tenant_a = Tenant(TenantName="Örnek Kantin A", IsActive=1)
        db.add(tenant_a)
        db.flush()

        # Şubeler
        branch_a1 = Branch(TenantID=tenant_a.TenantID, BranchName="Ana Bina Kantini", IsActive=1)
        branch_a2 = Branch(TenantID=tenant_a.TenantID, BranchName="Spor Salonu Kantini", IsActive=1)
        db.add_all([branch_a1, branch_a2])
        db.flush()

        # Patron A
        patron_a = User(
            TenantID=tenant_a.TenantID,
            DefaultBranchID=branch_a1.BranchID,
            Username="patrona",
            PasswordHash=hash_password("kantin123"),
            FullName="Ahmet Kantinci",
            IsSuperAdmin=0,
            CanManagePurchases=1,
            CanManageSales=1,
            CanManageCashRegister=1,
            CanViewReports=1,
            CanManageUsers=1,
            IsActive=1
        )
        # Personel A
        personel_a = User(
            TenantID=tenant_a.TenantID,
            DefaultBranchID=branch_a1.BranchID,
            Username="personela",
            PasswordHash=hash_password("pers123"),
            FullName="Ayşe Satış",
            IsSuperAdmin=0,
            CanManagePurchases=1,
            CanManageSales=1,
            CanManageCashRegister=1,
            CanViewReports=1,
            CanManageUsers=1,
            IsActive=1
        )
        db.add_all([patron_a, personel_a])
        db.flush()

        # 10 Adet Ürün (Kantin A için) - Stok kartı özellikleri (Barem ve Paket Tipi)
        products_data = [
            ("8690001", "Su 0.5L", "24 lü Koli", 24, 10.0, 100.0, 20.0, 4.0),
            ("8690002", "Kaşarlı Tost", "Adet", 1, 55.0, 40.0, 10.0, 28.0),
            ("8690003", "Karışık Tost", "Adet", 1, 70.0, 35.0, 10.0, 36.0),
            ("8690004", "Soğuk Sandviç", "Adet", 1, 65.0, 25.0, 5.0, 32.0),
            ("8690005", "Çikolatalı Gofret", "24 lü Koli", 24, 20.0, 80.0, 15.0, 11.0),
            ("8690006", "Patates Cipsi", "20 li Koli", 20, 35.0, 50.0, 10.0, 20.0),
            ("8690007", "Kutu Kola 330ml", "24 lü Koli", 24, 40.0, 60.0, 15.0, 22.0),
            ("8690008", "Ayran 200ml", "24 lü Koli", 24, 15.0, 75.0, 20.0, 7.5),
            ("8690009", "Meyve Suyu 200ml", "27 li Koli", 27, 20.0, 65.0, 15.0, 10.0),
            ("8690010", "Simit", "Adet", 1, 20.0, 30.0, 10.0, 9.0),
        ]

        created_products = []
        for barcode, name, pkg_type, pkg_mult, price, stock, crit, cost in products_data:
            p = Product(
                TenantID=tenant_a.TenantID,
                Barcode=barcode,
                ProductName=name,
                PackageType=pkg_type,
                PackageMultiplier=pkg_mult,
                CurrentSalePrice=price,
                StockQty=stock,
                CriticalStockLevel=crit,
                IsActive=1
            )
            db.add(p)
            created_products.append((p, cost))
        db.flush()

        # Alış Hareketleri
        for p, cost in created_products:
            # 1. Alış (10 gün önce)
            pur1 = Purchase(
                TenantID=tenant_a.TenantID,
                ProductID=p.ProductID,
                BranchID=branch_a1.BranchID,
                UnitCost=round(cost * 0.95, 2),
                Quantity=50.0,
                SupplierName="Metro Toptan",
                PurchaseDate=datetime.utcnow() - timedelta(days=10)
            )
            # 2. Alış (3 gün önce)
            pur2 = Purchase(
                TenantID=tenant_a.TenantID,
                ProductID=p.ProductID,
                BranchID=branch_a1.BranchID,
                UnitCost=cost,
                Quantity=60.0,
                SupplierName="Bizim Toptan",
                PurchaseDate=datetime.utcnow() - timedelta(days=3)
            )
            db.add_all([pur1, pur2])
        db.flush()

        # 3 Günlük Örnek Satışlar
        now = datetime.utcnow()
        for day_offset in range(3, 0, -1):
            sale_day = now - timedelta(days=day_offset)
            for idx, (p, cost) in enumerate(created_products):
                # Nakit Satış
                sale_cash = Sale(
                    TenantID=tenant_a.TenantID,
                    BranchID=branch_a1.BranchID,
                    ProductID=p.ProductID,
                    SalePrice=p.CurrentSalePrice,
                    Quantity=5.0,
                    PaymentType="CASH",
                    SaleDate=sale_day.replace(hour=10 + idx, minute=15),
                    UserID=personel_a.UserID
                )
                # Kartlı Satış
                sale_card = Sale(
                    TenantID=tenant_a.TenantID,
                    BranchID=branch_a1.BranchID,
                    ProductID=p.ProductID,
                    SalePrice=p.CurrentSalePrice,
                    Quantity=3.0,
                    PaymentType="CARD",
                    SaleDate=sale_day.replace(hour=11 + idx, minute=45),
                    UserID=personel_a.UserID
                )
                db.add_all([sale_cash, sale_card])
        db.flush()

        # 1 Günlük Örnek DailyRegister
        yesterday = (datetime.utcnow() - timedelta(days=1)).date()
        reg = DailyRegister(
            TenantID=tenant_a.TenantID,
            BranchID=branch_a1.BranchID,
            RegisterDate=yesterday,
            Count200=5,   # 1000
            Count100=8,   # 800
            Count50=10,   # 500
            Count20=15,   # 300
            Count10=20,   # 200
            Count5=20,    # 100 => Nakit Toplam = 2900 ₺
            DirectCashTotal=None,
            CreditCardTotal=1850.0,
            ExpenseTotal=350.0,
            OpeningCash=500.0,
            Notes="Dün gün sonu sorunsuz tamamlandı. Temizlik malzemesi masrafı düşüldü."
        )
        db.add(reg)
        db.flush()

    # 3. Örnek Tenant B: "Arkadaş Büfesi"
    tenant_b = db.query(Tenant).filter(Tenant.TenantName == "Arkadaş Büfesi").first()
    if not tenant_b:
        tenant_b = Tenant(TenantName="Arkadaş Büfesi", IsActive=1)
        db.add(tenant_b)
        db.flush()

        branch_b1 = Branch(TenantID=tenant_b.TenantID, BranchName="Merkez Büfe", IsActive=1)
        db.add(branch_b1)
        db.flush()

        patron_b = User(
            TenantID=tenant_b.TenantID,
            DefaultBranchID=branch_b1.BranchID,
            Username="patronb",
            PasswordHash=hash_password("bufe123"),
            FullName="Barış Büfeci",
            IsSuperAdmin=0,
            CanManagePurchases=1,
            CanManageSales=1,
            CanManageCashRegister=1,
            CanViewReports=1,
            CanManageUsers=1,
            IsActive=1
        )
        db.add(patron_b)
        db.flush()

        # Büfe B için 3 örnek ürün
        p_b1 = Product(TenantID=tenant_b.TenantID, Barcode="990001", ProductName="Filtre Kahve", CurrentSalePrice=45.0, StockQty=50.0, CriticalStockLevel=10.0, IsActive=1)
        p_b2 = Product(TenantID=tenant_b.TenantID, Barcode="990002", ProductName="Kruvasan", CurrentSalePrice=60.0, StockQty=30.0, CriticalStockLevel=5.0, IsActive=1)
        db.add_all([p_b1, p_b2])
        db.flush()

    db.commit()


def setup_database():
    """Tüm veritabanı yapısını ve verilerini hazırlar."""
    init_db()
    with SessionLocal() as db:
        seed_data(db)
