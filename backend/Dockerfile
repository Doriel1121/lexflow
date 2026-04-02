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
# netcat-openbsd       → check if postgres is ready
# postgresql-client    → psql command for creating extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-heb \
    tesseract-ocr-ara \
    poppler-utils \
    libpq5 \
    curl \
    netcat-openbsd \
    postgresql-client \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Download spacy English NER model
RUN python -m spacy download en_core_web_sm

# ── App setup ────────────────────────────────────────────────
WORKDIR /app/backend

# Create temp dir for cloud file downloads during OCR processing
RUN mkdir -p /tmp/lexflow_processing

# Copy application source
COPY . .

# Copy entrypoint and supervisord config
COPY entrypoint.sh /entrypoint.sh
COPY supervisord.conf /app/backend/supervisord.conf
RUN chmod +x /entrypoint.sh

# ── Expose & health check ────────────────────────────────────
EXPOSE 8000

# Checks the FastAPI root endpoint every 30 s.
# Gives the app 40 s to start before the first check (--start-period).
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# ── Entrypoint — runs migrations then starts app ──────────────
ENTRYPOINT ["/entrypoint.sh"]

# Entrypoint handles migrations + supervisord (uvicorn + celery)
CMD []
