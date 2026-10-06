# Python Dockerfile - KantinPos
FROM python:3.12-slim

# Temel ortam değişkenleri
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DB_PATH=/data/kantinpos.db

# Sistem bağımlılıkları ve güvenlik
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Çalışma dizini
WORKDIR /app

# Non-root kullanıcı oluşturma
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup appuser

# Kalıcı veri dizini oluştur ve izinleri ver
RUN mkdir -p /data && chown -R appuser:appgroup /data

# Bağımlılıkları kur
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Uygulama kodlarını kopyala
COPY . .
RUN chown -R appuser:appgroup /app

# Non-root kullanıcıya geç
USER appuser

# Port ve Healthcheck
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Uygulamayı başlat
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
