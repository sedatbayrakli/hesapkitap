# KantinPos — Çok Kiracılı Kantin & Büfe Nakit Akış Takip Sistemi

KantinPos, okul kantinleri, kafeteryalar ve büfeler gibi hızlı nakit ve POS döngüsüne sahip işletmeler için tasarlanmış, çok kiracılı (multi-tenant), mobil öncelikli bir yönetim ve takip uygulamasıdır.

---

## 🚀 Özellikler

1. **Çok Kiracılı Mimari (Multi-Tenant):**
   - Her işletme (Tenant) tamamen izole edilmiş kendi şube, ürün, alış, satış, kasa ve personel verilerini görür.
   - Süper Admin tek arayüzden tüm işletmeler arasında geçiş yapabilir ve yeni işletmeler oluşturabilir.
2. **Hızlı Satış Ekranı (POS):**
   - Dokunmatik uyumlu büyük ürün kartları.
   - Barkod okuyucu ve filtreleme desteği.
   - Sepet üzerinden anlık fiyat/iskonto düzenleme ve adet artırma/azaltma.
   - Nakit ve Kredi Kartı tahsilat toggle'ı.
   - **Stok Otomasyonu:** Satış onaylandığı anda tek transaction içinde stok miktarı anında düşürülür.
3. **Mal Alış & Ürün Yönetimi:**
   - Tedarikçilerden gelen ürünlerin alış maliyetlerini ve miktarlarını kaydetme.
   - Alış yapıldığında stok miktarı otomatik artar ve son maliyet güncellenir.
   - Hızlı yeni ürün tanımlama modalı (barkod, satış fiyatı, kritik stok seviyesi).
4. **Gün Sonu Kasa Sayımı & Z-Raporu:**
   - 200, 100, 50, 20, 10, 5 TL banknot/madeni para adet sayım modu veya direkt nakit tutar girişi.
   - Canlı sticky toplam hesaplama.
   - Kredi kartı (POS) cirosu, devir kasa ve masraf düşümü.
   - **Otomatik Trigger'lar:** Nakit ve toplam ciro SQLite trigger'ları ile otomatik hesaplanır.
   - **Z-Raporu PDF Çıktısı:** ReportLab ile tek tıkla resmi gün sonu Z-raporu ve kasa mutabakat tutanağı üretimi.
5. **Raporlar & Finansal Kârlılık:**
   - Bugün, Son 7 Gün, Son 30 Gün ve Şube bazlı filtreleme.
   - KPI Kartları: Toplam Ciro, Mal Alış Tutarı, Kasa Masrafları ve Net Kâr (Kâr yeşil, Zarar kırmızı).
   - Chart.js ile günlük ciro trend çizgisi, ödeme tipi pasta grafiği ve şubeler arası ciro karşılaştırma çubuğu.
   - Ürün kârlılık tablosu: Son maliyet, brüt kâr marjı (₺ ve %), kritik stok uyarı rozetleri.
   - Tek tıkla CSV dışa aktarma (Excel uyumlu UTF-8 BOM).
6. **Personel & Rol Tabanlı Yetkilendirme (RBAC):**
   - Satış, Mal Alış, Kasa Sayımı, Raporlar ve Personel Yönetimi için ayrı izinler.
   - Yetkisiz personele ait menü ve sekmeler HTML'de hiç render edilmez; backend'de 403 Forbidden döner.

---

## 🛠️ Teknik Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.x
- **Veritabanı:** SQLite (WAL Modu, `busy_timeout=5000`, `foreign_keys=ON`)
- **Kimlik Doğrulama:** Starlette `SessionMiddleware` (HttpOnly, SameSite=Lax), `passlib[bcrypt]`
- **Frontend:** Jinja2 Şablonları, TailwindCSS (CDN), Chart.js (CDN), Vanilla JavaScript
- **PDF & Raporlama:** ReportLab
- **Konteyner:** Docker (python:3.12-slim, non-root `appuser`)

---

## 📦 Kurulum ve Coolify Deployment

### Coolify Üzerinde Deploy Etme Adımları

1. **Coolify Paneline Giriş Yapın.**
2. **Yeni Servis / Proje Ekleyin:**
   - *Sources -> GitHub / Git Repository* seçin.
   - Repo URL olarak `sedatbayrakli/hesapkitap` reposunu bağlayın.
   - Build Pack olarak **Dockerfile** veya **Docker Compose** seçin (Dockerfile önerilir).
3. **Kalıcı Depolama (Persistent Volume) Tanımlayın:**
   - SQLite veritabanının silinmemesi için Volume ekleyin:
   - **Destination Path:** `/data`
   - **Name:** `kantinpos_data`
4. **Ortam Değişkenlerini (Environment Variables) Tanımlayın:**
   ```env
   SECRET_KEY=buraya-cok-gizli-rastgele-32-karakter-anahtar-yazin
   ADMIN_PASSWORD=guclu_admin_sifreniz
   DB_PATH=/data/kantinpos.db
   COOKIE_SECURE=true
   ```
5. **Port ve Healthcheck:**
   - **Port:** `8000`
   - **Healthcheck Path:** `/health`
6. **Deploy Et Butonuna Basın:**
   - Coolify konteyneri derler, otomatik SSL sertifikasını tanımlar ve yayına alır.

---

## 💻 Yerel Geliştirme (Local Development)

```bash
# 1. Sanal ortamı kurun ve aktifleştirin
python3 -m venv .venv
source .venv/bin/activate

# 2. Bağımlılıkları yükleyin
pip install -r requirements.txt

# 3. Uygulamayı başlatın
uvicorn app.main:app --reload --port 8000
```

---

## 🔑 Varsayılan Kullanıcılar (Seed Data)

| Rol | Kullanıcı Adı | Şifre | Açıklama |
|---|---|---|---|
| **Süper Admin** | `superadmin` | `admin123` | Tüm işletmeleri ve platformu yönetir |
| **Kantin Patronu** | `patrona` | `kantin123` | "Örnek Kantin A" Yöneticisi (Tüm yetkiler açık) |
| **Personel** | `personela` | `pers123` | "Örnek Kantin A" Kasiyeri |
| **Büfe Patronu** | `patronb` | `bufe123` | "Arkadaş Büfesi" Yöneticisi |

*(Süper admin şifresi konteyner ortam değişkeni `ADMIN_PASSWORD` ile değiştirilebilir).*
