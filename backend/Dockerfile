# ============================================================
# LEXFLOW — Backend Dockerfile
# ============================================================
# Multi-stage build:
#   Stage 1 (builder) — install Python deps in an isolated env
#   Stage 2 (runtime) — copy only what's needed, no build tools
#
# Result: lean production image with system OCR libs intact.
# ============================================================

# ── Stage 1: dependency builder ──────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System libs needed to compile some pip packages (psycopg2, cryptography…)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first — Docker cache means this layer is only
# rebuilt when requirements.txt actually changes.
COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime image ───────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="LexFlow Team"
LABEL description="LexFlow backend — FastAPI + Celery"

# ── System dependencies (OCR + PDF) ─────────────────────────
# tesseract-ocr        → pytesseract OCR engine
# tesseract-ocr-heb    → Hebrew language pack
# tesseract-ocr-ara    → Arabic  language pack
# poppler-utils        → pdf2image (pdfinfo / pdftoppm)
# libpq5               → runtime PostgreSQL client library
# curl                 → health-check probe
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-heb \
    tesseract-ocr-ara \
    poppler-utils \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# ── App setup ────────────────────────────────────────────────
WORKDIR /app/backend

# Create uploads directory (persisted via Docker volume in compose)
RUN mkdir -p /app/backend/uploads

# Copy application source
COPY . .

# ── Security: non-root user ──────────────────────────────────
RUN useradd --no-create-home --shell /bin/false appuser && \
    chown -R appuser:appuser /app/backend
USER appuser

# ── Expose & health check ────────────────────────────────────
EXPOSE 8000

# Checks the FastAPI root endpoint every 30 s.
# Gives the app 40 s to start before the first check (--start-period).
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# ── Default command (overridden in docker-compose for dev) ───
# Production: no --reload, 2 workers per CPU core
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
