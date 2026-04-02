#!/bin/bash
set -e

echo "======================================================"
echo "Starting LexFlow Backend + Celery (supervisord)"
echo "======================================================"

# Extract DB host/port from DATABASE_URL for readiness check
if [ -n "$DATABASE_URL" ]; then
  PLAIN_URL="${DATABASE_URL/+asyncpg/}"
  DB_HOST=$(echo "$PLAIN_URL" | sed -E 's|.*@([^:/]+).*|\1|')
  DB_PORT=$(echo "$PLAIN_URL" | sed -E 's|.*:([0-9]+)/.*|\1|')
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

echo "Running Alembic migrations..."
alembic upgrade head

echo "Launching supervisord (uvicorn + celery)..."
exec supervisord -c /app/backend/supervisord.conf
