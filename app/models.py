"""
KantinPos SQLAlchemy 2.x Veritabanı Modelleri.
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Date,
    ForeignKey,
    CheckConstraint,
    Index
)
from sqlalchemy.orm import relationship
from app.database import Base


class Tenant(Base):
    """İşletme (Tenant) tablosu."""
    __tablename__ = "Tenants"

    TenantID = Column(Integer, primary_key=True, autoincrement=True)
    TenantName = Column(String(100), unique=True, nullable=False)
    IsActive = Column(Integer, default=1, nullable=False)
    CreatedAt = Column(DateTime, default=datetime.utcnow)

    # İlişkiler
    branches = relationship("Branch", back_populates="tenant", cascade="all, delete-orphan")
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="tenant", cascade="all, delete-orphan")
    purchases = relationship("Purchase", back_populates="tenant", cascade="all, delete-orphan")
    sales = relationship("Sale", back_populates="tenant", cascade="all, delete-orphan")
    daily_registers = relationship("DailyRegister", back_populates="tenant", cascade="all, delete-orphan")


class Branch(Base):
    """Şube (Branch) tablosu."""
    __tablename__ = "Branches"

    BranchID = Column(Integer, primary_key=True, autoincrement=True)
    TenantID = Column(Integer, ForeignKey("Tenants.TenantID", ondelete="CASCADE"), nullable=False)
    BranchName = Column(String(100), nullable=False)
    IsActive = Column(Integer, default=1, nullable=False)

    # İlişkiler
    tenant = relationship("Tenant", back_populates="branches")
    users = relationship("User", back_populates="default_branch")
    purchases = relationship("Purchase", back_populates="branch")
    sales = relationship("Sale", back_populates="branch")
    daily_registers = relationship("DailyRegister", back_populates="branch")


class User(Base):
    """Kullanıcı tablosu (Süper admin, tenant admin ve RBAC rolleriyle)."""
    __tablename__ = "Users"

    UserID = Column(Integer, primary_key=True, autoincrement=True)
    TenantID = Column(Integer, ForeignKey("Tenants.TenantID", ondelete="CASCADE"), nullable=True)
    DefaultBranchID = Column(Integer, ForeignKey("Branches.BranchID", ondelete="SET NULL"), nullable=True)
    Username = Column(String(50), unique=True, nullable=False)
    PasswordHash = Column(String(255), nullable=False)
    FullName = Column(String(100), nullable=False)
    IsSuperAdmin = Column(Integer, default=0, nullable=False)
    CanManagePurchases = Column(Integer, default=0, nullable=False)
    CanManageSales = Column(Integer, default=0, nullable=False)
    CanManageCashRegister = Column(Integer, default=0, nullable=False)
    CanViewReports = Column(Integer, default=0, nullable=False)
    CanManageUsers = Column(Integer, default=0, nullable=False)
    IsActive = Column(Integer, default=1, nullable=False)
    CreatedAt = Column(DateTime, default=datetime.utcnow)

    # İlişkiler
    tenant = relationship("Tenant", back_populates="users")
    default_branch = relationship("Branch", back_populates="users")
    sales = relationship("Sale", back_populates="user")


class Product(Base):
    """Ürün tablosu."""
    __tablename__ = "Products"

    ProductID = Column(Integer, primary_key=True, autoincrement=True)
    TenantID = Column(Integer, ForeignKey("Tenants.TenantID", ondelete="CASCADE"), nullable=False)
    Barcode = Column(String(100), nullable=True)
    ProductName = Column(String(150), nullable=False)
    CurrentSalePrice = Column(Float, nullable=False)
    StockQty = Column(Float, default=0.0, nullable=False)
    CriticalStockLevel = Column(Float, default=0.0, nullable=False)
    IsActive = Column(Integer, default=1, nullable=False)
    CreatedAt = Column(DateTime, default=datetime.utcnow)

    # İlişkiler
    tenant = relationship("Tenant", back_populates="products")
    purchases = relationship("Purchase", back_populates="product")
    sales = relationship("Sale", back_populates="product")

    __table_args__ = (
        Index("idx_products_tenant_barcode", "TenantID", "Barcode"),
        Index("idx_products_tenant_name", "TenantID", "ProductName"),
    )


class Purchase(Base):
    """Mal Alış tablosu."""
    __tablename__ = "Purchases"

    PurchaseID = Column(Integer, primary_key=True, autoincrement=True)
    TenantID = Column(Integer, ForeignKey("Tenants.TenantID", ondelete="CASCADE"), nullable=False)
    ProductID = Column(Integer, ForeignKey("Products.ProductID", ondelete="RESTRICT"), nullable=False)
    BranchID = Column(Integer, ForeignKey("Branches.BranchID", ondelete="SET NULL"), nullable=True)
    UnitCost = Column(Float, nullable=False)
    Quantity = Column(Float, nullable=False)
    PackageMultiplier = Column(Integer, default=1, nullable=False)  # Barem katsayısı (örn: 24'lü koli için 24)
    PackageType = Column(String(50), default="Adet", nullable=False)  # 'Adet', '24 lü Koli', '12 li Paket' vb.
    SupplierName = Column(String(150), nullable=True)
    PurchaseDate = Column(DateTime, default=datetime.utcnow)

    # İlişkiler
    tenant = relationship("Tenant", back_populates="purchases")
    product = relationship("Product", back_populates="purchases")
    branch = relationship("Branch", back_populates="purchases")


class Sale(Base):
    """Satış tablosu."""
    __tablename__ = "Sales"

    SaleID = Column(Integer, primary_key=True, autoincrement=True)
    TenantID = Column(Integer, ForeignKey("Tenants.TenantID", ondelete="CASCADE"), nullable=False)
    BranchID = Column(Integer, ForeignKey("Branches.BranchID", ondelete="RESTRICT"), nullable=False)
    ProductID = Column(Integer, ForeignKey("Products.ProductID", ondelete="RESTRICT"), nullable=False)
    SalePrice = Column(Float, nullable=False)
    Quantity = Column(Float, nullable=False)
    PaymentType = Column(String(10), nullable=False)  # CASH veya CARD
    SaleDate = Column(DateTime, default=datetime.utcnow)
    UserID = Column(Integer, ForeignKey("Users.UserID", ondelete="RESTRICT"), nullable=False)

    # İlişkiler
    tenant = relationship("Tenant", back_populates="sales")
    branch = relationship("Branch", back_populates="sales")
    product = relationship("Product", back_populates="sales")
    user = relationship("User", back_populates="sales")

    __table_args__ = (
        CheckConstraint("PaymentType IN ('CASH', 'CARD')", name="check_payment_type"),
    )


class DailyRegister(Base):
    """Gün Sonu Kasa Sayım tablosu."""
    __tablename__ = "DailyRegister"

    RegisterID = Column(Integer, primary_key=True, autoincrement=True)
    TenantID = Column(Integer, ForeignKey("Tenants.TenantID", ondelete="CASCADE"), nullable=False)
    BranchID = Column(Integer, ForeignKey("Branches.BranchID", ondelete="RESTRICT"), nullable=False)
    RegisterDate = Column(Date, nullable=False)
    Count200 = Column(Integer, default=0, nullable=False)
    Count100 = Column(Integer, default=0, nullable=False)
    Count50 = Column(Integer, default=0, nullable=False)
    Count20 = Column(Integer, default=0, nullable=False)
    Count10 = Column(Integer, default=0, nullable=False)
    Count5 = Column(Integer, default=0, nullable=False)
    DirectCashTotal = Column(Float, nullable=True)
    CashTotal = Column(Float, default=0.0, nullable=False)
    CreditCardTotal = Column(Float, default=0.0, nullable=False)
    ExpenseTotal = Column(Float, default=0.0, nullable=False)
    OpeningCash = Column(Float, default=0.0, nullable=False)
    TotalRevenue = Column(Float, default=0.0, nullable=False)
    Notes = Column(String(500), nullable=True)

    # İlişkiler
    tenant = relationship("Tenant", back_populates="daily_registers")
    branch = relationship("Branch", back_populates="daily_registers")
