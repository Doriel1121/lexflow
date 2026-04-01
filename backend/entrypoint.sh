#!/bin/bash
set -e

echo "======================================================"
echo "🚀 Starting LexFlow Backend + Celery"
echo "======================================================"

# Wait for database to be ready
echo "Waiting for PostgreSQL to be ready..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
  # Try to extract host from DATABASE_URL and test connection
  if [ ! -z "$DATABASE_URL" ]; then
    # For Render Postgres: postgresql+asyncpg://user:pass@host:5432/db
    DB_HOST=$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:]*\).*/\1/p')
    if [ ! -z "$DB_HOST" ] && nc -z "$DB_HOST" 5432 2>/dev/null; then
      echo "✓ PostgreSQL is ready!"
      break
    fi
  fi
  
  attempt=$((attempt + 1))
  echo "  Waiting... ($attempt/$max_attempts)"
  sleep 1
done

# Create pgvector extension (if local postgres)
echo "Setting up database extensions..."
if [ ! -z "$POSTGRES_PASSWORD" ] && [ ! -z "$POSTGRES_USER" ]; then
  PGPASSWORD=$POSTGRES_PASSWORD psql -h db -U $POSTGRES_USER -d $POSTGRES_DB \
    -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || \
  echo "  (Skipping local pgvector setup - using remote database)"
fi

echo "✓ Database ready"
echo ""

# Start FastAPI and Celery in background
echo "Starting FastAPI backend..."
cd /app/backend
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 2 &

UVICORN_PID=$!
echo "  FastAPI PID: $UVICORN_PID"

sleep 2

echo "Starting Celery worker..."
celery -A app.core.celery worker \
  --loglevel=info \
  --concurrency=2 &

CELERY_PID=$!
echo "  Celery PID: $CELERY_PID"

echo ""
echo "✓ Both services started"
echo "======================================================"

# Wait for both processes
wait

