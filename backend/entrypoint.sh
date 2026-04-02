#!/bin/bash
set -e

echo "======================================================"
echo "Starting LexFlow Backend + Celery"
echo "======================================================"

# Wait for PostgreSQL
echo "Waiting for PostgreSQL..."
for i in {1..30}; do
  if nc -z db 5432 2>/dev/null || (echo > /dev/tcp/localhost/5432) 2>/dev/null; then
    echo "✓ PostgreSQL is ready!"
    break
  fi
  echo "Attempt $i/30..."
  sleep 1
done

# Create pgvector extension
echo "Creating pgvector extension..."
PGPASSWORD=$POSTGRES_PASSWORD psql -h db -U $POSTGRES_USER -d $POSTGRES_DB \
  -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || \
echo "  (Extension setup skipped)"

echo ""
echo "Starting services..."

# Start both in parallel
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 &
celery -A app.core.celery worker --loglevel=info --concurrency=2 &

# Keep both running
wait

