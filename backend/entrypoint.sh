#!/bin/bash
set -e

# Determine if this is a Celery worker or FastAPI backend
IS_CELERY=false
if [[ "$@" == *"celery"* ]]; then
  IS_CELERY=true
fi

echo "======================================================"
if [ "$IS_CELERY" = true ]; then
  echo "🔄 Starting Celery Worker"
else
  echo "🚀 Starting FastAPI Backend"
fi
echo "======================================================"

# Wait for database to be ready (only if in containerized environment)
if [ ! -z "$DATABASE_URL" ] && [[ "$DATABASE_URL" == *"@"* ]]; then
  echo "Waiting for PostgreSQL to be ready..."
  for i in {1..30}; do
    if nc -z db 5432 2>/dev/null || nc -z ${DATABASE_URL#*@} 5432 2>/dev/null; then
      echo "✓ PostgreSQL is ready!"
      break
    fi
    echo "  Retrying... ($i/30)"
    sleep 1
  done
fi

# Only run migrations on backend (NOT on celery worker)
if [ "$IS_CELERY" = false ]; then
  echo "Setting up database extensions..."
  
  # Create pgvector extension for embeddings
  PGPASSWORD=$POSTGRES_PASSWORD psql -h db -U $POSTGRES_USER -d $POSTGRES_DB \
    -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || \
  echo "  (pgvector extension may already exist or db not ready)"
  
  echo "✓ Database initialization complete"
  echo ""
else
  echo "Skipping database setup (handled by backend service)"
fi

# Start the application
echo "Starting service..."
exec "$@"

