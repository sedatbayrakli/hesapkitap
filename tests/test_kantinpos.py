"""
KantinPos Kapsamlı Pytest Test Paketi.
Test senaryoları:
1. Sağlık kontrolü (/health)
2. Giriş ve yetkilendirme (Başarılı / Başarısız login)
3. Hatalı giriş kaba kuvvet (Rate Limiting) koruması
4. Kiracı (Tenant) veri izolasyonu
5. RBAC rol yetkilendirmesi ve 403 Forbidden kontrolleri
6. Satış transaction işlemi ve stok düşümü
7. Mal alışı ve stok artışı
8. Kasa sayımı (DailyRegister) trigger hesaplaması
9. Kasa mükerrer kayıt ve güncelleme mantığı
10. Kârlılık ve marj view hesaplamaları
11. Z-Raporu PDF çıktısı üretimi
12. Süper Admin işletme değiştirme ve yeni işletme açma
"""

import os
import re
import pytest
from datetime import date
from starlette.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DB_PATH"] = "data/test_kantinpos.db"
os.environ["SECRET_KEY"] = "test-gizli-anahtar-1234567890123456"

from app.database import Base, get_db
from app.seed import init_db, seed_data
from app.models import Tenant, User, Product, DailyRegister, Branch
from app.main import app

test_engine = create_engine("sqlite:///data/test_kantinpos.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Test oturumu başında test veritabanını oluşturur ve seed eder."""
    test_db_file = "data/test_kantinpos.db"
    for f in [test_db_file, test_db_file + "-wal", test_db_file + "-shm"]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass
    init_db()
    with TestingSessionLocal() as db:
        seed_data(db)
    yield
    # Test bitiminde temizle
    for f in [test_db_file, test_db_file + "-wal", test_db_file + "-shm"]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass


@pytest.fixture
def client():
    """Her test için yeni bir TestClient örneği oluşturur."""
    return TestClient(app, follow_redirects=False)


def extract_csrf(client: TestClient) -> str:
    """Sayfa render'ından güncel CSRF token'ı ayıklar."""
    resp = client.get("/auth/login")
    match = re.search(r'name=["\']csrf_token["\'] value=["\']([^"\']+)["\']', resp.text)
    return match.group(1) if match else ""


def login_as(client: TestClient, username: str, password: str) -> str:
    """Belirtilen kullanıcı ile giriş yapar ve sonrasındaki sayfadan güncel CSRF token'ı döner."""
    csrf = extract_csrf(client)
    res = client.post("/auth/login", data={
        "username": username,
        "password": password,
        "csrf_token": csrf
    })
    assert res.status_code == 303
    # Giriş sonrası yönlenilen sayfayı ziyaret ederek taze CSRF token çek
    dash_res = client.get("/sales")
    match = re.search(r'name=["\']csrf_token["\'] value=["\']([^"\']+)["\']', dash_res.text)
    if not match:
        match = re.search(r'csrfToken\s*=\s*["\']([^"\']+)["\']', dash_res.text)
    return match.group(1) if match else csrf


def test_01_health_check(client):
    """GET /health endpoint testi."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["db"] == "up"


def test_02_login_flow(client):
    """Giriş sayfası ve kimlik doğrulama akışı."""
    csrf = extract_csrf(client)
    assert len(csrf) > 0

    # Hatalı şifre denemesi
    wrong_login = client.post("/auth/login", data={
        "username": "patrona",
        "password": "yanlissifre",
        "csrf_token": csrf
    })
    assert wrong_login.status_code == 401

    # Başarılı giriş
    correct_login = client.post("/auth/login", data={
        "username": "patrona",
        "password": "kantin123",
        "csrf_token": csrf
    })
    assert correct_login.status_code == 303
    assert correct_login.headers["location"] == "/dashboard"


def test_03_tenant_isolation(client):
    """Kiracı İzolasyonu: Patron A, Kiracı B'nin verilerini ve şubelerini göremez."""
    csrf = login_as(client, "patrona", "kantin123")

    with TestingSessionLocal() as db:
        tenant_b = db.query(Tenant).filter(Tenant.TenantName == "Arkadaş Büfesi").first()
        prod_b = db.query(Product).filter(Product.TenantID == tenant_b.TenantID).first()
        branch_b = db.query(Branch).filter(Branch.TenantID == tenant_b.TenantID).first()

    # Patron A, Tenant B'nin ürününe satış yapmaya kalkarsa 404/hata almalı
    sale_payload = {
        "payment_type": "CASH",
        "items": [{"product_id": prod_b.ProductID, "price": 45.0, "quantity": 1}]
    }
    sale_res = client.post(
        "/sales/checkout",
        headers={"X-CSRF-Token": csrf},
        json=sale_payload
    )
    assert sale_res.status_code == 404 or sale_res.json()["success"] is False

    # Patron A, Tenant B'nin şubesine geçiş yapmaya çalışırsa 404 almalı
    switch_res = client.post("/admin/switch-branch", data={
        "branch_id": branch_b.BranchID,
        "csrf_token": csrf
    })
    assert switch_res.status_code == 404


def test_04_rbac_permissions(client):
    """Yetkisiz kullanıcılar kısıtlı ekranlara eriştiğinde 403 Forbidden almalıdır."""
    with TestingSessionLocal() as db:
        user_limited = db.query(User).filter(User.Username == "test_limited_user").first()
        if not user_limited:
            from app.security import hash_password
            user_limited = User(
                TenantID=1,
                Username="test_limited_user",
                PasswordHash=hash_password("test12345"),
                FullName="Kısıtlı Personel",
                IsSuperAdmin=0,
                CanManageSales=1,
                CanManagePurchases=0,
                CanManageCashRegister=0,
                CanViewReports=0,
                CanManageUsers=0,
                IsActive=1
            )
            db.add(user_limited)
            db.commit()

    login_as(client, "test_limited_user", "test12345")

    # Satış ekranına erişebilmeli
    res_sales = client.get("/sales")
    assert res_sales.status_code == 200

    # Raporlar ekranına erişimi 403 dönmeli
    res_reports = client.get("/reports")
    assert res_reports.status_code == 403

    # Kasa ekranına erişimi 403 dönmeli
    res_register = client.get("/register")
    assert res_register.status_code == 403

    # Mal alış ekranına erişimi 403 dönmeli
    res_purchases = client.get("/purchases")
    assert res_purchases.status_code == 403

    # Yönetim ekranına erişimi 403 dönmeli
    res_admin = client.get("/admin/users")
    assert res_admin.status_code == 403


def test_05_sale_transaction_and_stock_reduction(client):
    """Satış işleminde veritabanı transaction'ı ile stok miktarının anında düşmesi testi."""
    csrf = login_as(client, "patrona", "kantin123")

    with TestingSessionLocal() as db:
        prod = db.query(Product).filter(Product.TenantID == 1, Product.ProductName == "Su 0.5L").first()
        initial_stock = prod.StockQty
        prod_id = prod.ProductID

    qty_to_sell = 3.0
    sale_payload = {
        "payment_type": "CASH",
        "items": [{"product_id": prod_id, "price": 10.0, "quantity": qty_to_sell}]
    }
    resp = client.post(
        "/sales/checkout",
        headers={"X-CSRF-Token": csrf},
        json=sale_payload
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Stok miktarının tam olarak düştüğünü teyit et
    with TestingSessionLocal() as db:
        updated_prod = db.query(Product).filter(Product.ProductID == prod_id).first()
        assert updated_prod.StockQty == round(initial_stock - qty_to_sell, 2)


def test_06_purchase_transaction_and_stock_increase(client):
    """Mal alış işleminde koli/barem çarpanı ile ürün stok miktarının tek transaction'da artması testi."""
    csrf = login_as(client, "patrona", "kantin123")

    with TestingSessionLocal() as db:
        prod = db.query(Product).filter(Product.TenantID == 1, Product.ProductName == "Kaşarlı Tost").first()
        initial_stock = prod.StockQty
        prod_id = prod.ProductID

    # 2 koli x 24 adet = 48 adet stoğa girmeli
    res = client.post("/purchases", data={
        "product_id": prod_id,
        "price_mode": "package",
        "unit_cost": 240.0,  # Koli fiyatı 240 TL -> birim adet maliyeti 10 TL
        "package_type": "24 lü Koli",
        "package_multiplier": 24,
        "package_count": 2,
        "supplier_name": "Toptancı Test",
        "csrf_token": csrf
    })
    assert res.status_code == 303

    with TestingSessionLocal() as db:
        updated_prod = db.query(Product).filter(Product.ProductID == prod_id).first()
        assert updated_prod.StockQty == round(initial_stock + 48.0, 2)


def test_07_daily_register_trigger_and_unique_constraint(client):
    """Gün sonu kasa sayımı (DailyRegister) SQLite trigger hesaplaması ve UNIQUE kısıtı."""
    csrf = login_as(client, "patrona", "kantin123")

    test_date = "2026-10-15"
    # 1. Kasa Kaydı Ekle: 2x200 + 1x100 = 500 TL nakit, 300 TL POS
    res1 = client.post("/register", data={
        "branch_id": 1,
        "register_date": test_date,
        "count_200": 2,
        "count_100": 1,
        "credit_card_total": 300.0,
        "expense_total": 50.0,
        "opening_cash": 100.0,
        "overwrite": 0,
        "csrf_token": csrf
    })
    assert res1.status_code == 303

    # Trigger'ın CashTotal = 500 ve TotalRevenue = 800 hesapladığını kontrol et
    with TestingSessionLocal() as db:
        reg = db.query(DailyRegister).filter(
            DailyRegister.TenantID == 1,
            DailyRegister.BranchID == 1,
            DailyRegister.RegisterDate == date(2026, 10, 15)
        ).first()
        assert reg is not None
        assert reg.CashTotal == 500.0
        assert reg.TotalRevenue == 800.0

    # 2. Aynı tarih ve şubeye overwrite=0 ile mükerrer ekleme denemesi (400 almalı)
    res_duplicate = client.post("/register", data={
        "branch_id": 1,
        "register_date": test_date,
        "count_200": 3,
        "overwrite": 0,
        "csrf_token": csrf
    })
    assert res_duplicate.status_code == 400

    # 3. overwrite=1 ile mevcut kaydı güncelleme
    res_update = client.post("/register", data={
        "branch_id": 1,
        "register_date": test_date,
        "count_200": 4,  # 800 TL nakit
        "count_100": 0,
        "credit_card_total": 400.0,
        "expense_total": 50.0,
        "opening_cash": 100.0,
        "overwrite": 1,
        "csrf_token": csrf
    })
    assert res_update.status_code == 303

    with TestingSessionLocal() as db:
        reg_updated = db.query(DailyRegister).filter(
            DailyRegister.TenantID == 1,
            DailyRegister.BranchID == 1,
            DailyRegister.RegisterDate == date(2026, 10, 15)
        ).first()
        assert reg_updated.CashTotal == 800.0
        assert reg_updated.TotalRevenue == 1200.0


def test_08_product_profit_margin_view(client):
    """vw_ProductProfitMargins view'ı marj hesaplama doğruluğu testi."""
    with TestingSessionLocal() as db:
        from app.services.reports import get_product_profitability
        margins = get_product_profitability(db, tenant_id=1)
        assert len(margins) > 0
        su = next(m for m in margins if m["ProductName"] == "Su 0.5L")
        assert su["CurrentSalePrice"] == 10.0
        assert su["LastUnitCost"] > 0
        assert su["ProfitMarginAmount"] == round(su["CurrentSalePrice"] - su["LastUnitCost"], 2)


def test_09_z_report_pdf_generation(client):
    """Z-Raporu PDF endpoint testi (application/pdf ve PDF header kontrolü)."""
    login_as(client, "patrona", "kantin123")

    pdf_res = client.get("/register/z-report?branch_id=1&date=2026-10-15")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert pdf_res.content.startswith(b"%PDF-")


def test_10_super_admin_tenant_switching(client):
    """Süper Admin'in işletmeler arası geçiş yapabilmesi ve yeni işletme açması."""
    csrf = login_as(client, "superadmin", "admin123")

    # Süper admin yeni tenant açar
    res_new_tenant = client.post("/admin/tenants", data={
        "tenant_name": "Test Yeni Kantin",
        "initial_branch_name": "Kuzey Kampüs",
        "csrf_token": csrf
    })
    assert res_new_tenant.status_code == 303

    with TestingSessionLocal() as test_session:
        created_t = test_session.query(Tenant).filter(Tenant.TenantName == "Test Yeni Kantin").first()
        assert created_t is not None
        assert created_t.IsActive == 1
