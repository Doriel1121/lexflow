#!/bin/bash
set -e

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
  if nc -z db 5432 2>/dev/null; then
    echo "PostgreSQL is ready!"
    break
  fi
  echo "Waiting for PostgreSQL... ($i/30)"
  sleep 1
done

# Only run migrations on backend service (not on celery_worker)
# Check if the first argument contains "celery" to detect celery worker
if [[ "$@" == *"celery"* ]]; then
  echo "Skipping database setup on celery worker (handled by backend service)"
else
  # Create pgvector extension (needed for embeddings)
  echo "Attempting to create pgvector extension..."
  PGPASSWORD=$POSTGRES_PASSWORD psql -h db -U $POSTGRES_USER -d $POSTGRES_DB -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || true
  
  echo "Note: Database tables will be created by the FastAPI startup event (SQLAlchemy)"
  echo "Skipping Alembic migrations due to complexity with multiple head revisions"
fi

# Start the application
echo "Starting application..."
exec "$@"

