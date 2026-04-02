#!/bin/bash
set -e

echo "======================================================"
echo "Starting LexFlow Backend + Celery (supervisord)"
echo "======================================================"

# Extract DB host/port from DATABASE_URL for readiness check
if [ -n "$DATABASE_URL" ]; then
  # Strip driver prefix, extract host
  # e.g. postgresql+asyncpg://user:pass@host:5432/db -> host
  PLAIN_URL=$(echo "$DATABASE_URL" | sed 's|postgresql+asyncpg://||' | sed 's|postgresql://||')
  DB_HOST=$(echo "$PLAIN_URL" | sed -E 's|.*@([^:/]+).*|\1|')
  DB_PORT=$(echo "$PLAIN_URL" | sed -E 's|.*@[^:]+:([0-9]+)/.*|\1|')
  DB_PORT="${DB_PORT:-5432}"

  echo "Waiting for PostgreSQL at $DB_HOST:$DB_PORT ..."
  for i in $(seq 1 30); do
    if nc -z "$DB_HOST" "$DB_PORT" 2>/dev/null; then
      echo "✓ PostgreSQL is ready!"
      break
    fi
    echo "Attempt $i/30..."
    sleep 2
  done
fi

echo "Creating pgvector extension..."
# Use psql with the DATABASE_URL (convert asyncpg URL to standard psql URL)
PSQL_URL=$(echo "$DATABASE_URL" | sed 's|postgresql+asyncpg://|postgresql://|')
psql "$PSQL_URL" -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null && \
  echo "✓ pgvector ready" || echo "⚠ pgvector setup skipped (may already exist)"

echo "Running Alembic migrations..."
alembic upgrade head

echo "Running seed..."
PYTHONPATH=/app/backend python scripts/seed.py

echo "Launching supervisord (uvicorn + celery)..."
exec supervisord -c /app/backend/supervisord.conf
