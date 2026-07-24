#!/bin/bash
set -euo pipefail

PROCESS_MODE="${LEXFLOW_PROCESS_MODE:-all}"
ENV_NAME="${ENVIRONMENT:-${APP_ENV:-development}}"
RUN_MIGRATIONS="${RUN_MIGRATIONS_ON_STARTUP:-}"
RUN_SEED="${RUN_SEED_ON_STARTUP:-}"

export PORT="${PORT:-8000}"
export UVICORN_WORKERS="${UVICORN_WORKERS:-1}"
export CELERY_LOGLEVEL="${CELERY_LOGLEVEL:-info}"
export CELERY_POOL="${CELERY_POOL:-threads}"
export CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-4}"
export CELERY_QUEUES="${CELERY_QUEUES:-default,documents,ai,celery}"

case "$PROCESS_MODE" in
  api|worker|all|migrate) ;;
  *)
    echo "ERROR: Invalid LEXFLOW_PROCESS_MODE='$PROCESS_MODE'. Expected: api, worker, all, migrate."
    exit 1
    ;;
esac

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL environment variable is not set"
  echo "Set DATABASE_URL or configure DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME before startup."
  exit 1
fi

if [ -z "$RUN_MIGRATIONS" ]; then
  if [ "$PROCESS_MODE" = "api" ] || [ "$PROCESS_MODE" = "all" ]; then
    RUN_MIGRATIONS="true"
  else
    RUN_MIGRATIONS="false"
  fi
fi

if [ -z "$RUN_SEED" ]; then
  if [ "$RUN_MIGRATIONS" = "true" ] && [ "$ENV_NAME" != "production" ]; then
    RUN_SEED="true"
  else
    RUN_SEED="false"
  fi
fi

log_header() {
  echo "======================================================"
  echo "LexFlow startup"
  echo "  mode:        $PROCESS_MODE"
  echo "  environment: $ENV_NAME"
  echo "  migrations:  $RUN_MIGRATIONS"
  echo "  seed:        $RUN_SEED"
  echo "======================================================"
}

extract_db_host_port() {
  PLAIN_URL=$(echo "$DATABASE_URL" | sed 's|postgresql+asyncpg://||' | sed 's|postgresql://||')
  DB_HOST=$(echo "$PLAIN_URL" | sed -E 's|[^@]+@([^:/]+).*|\1|')
  DB_PORT=$(echo "$PLAIN_URL" | grep -oE ':[0-9]+/' | tr -d ':/' || true)
  DB_PORT="${DB_PORT:-5432}"
}

wait_for_tcp() {
  local name="$1"
  local host="$2"
  local port="$3"
  local attempts="${4:-30}"

  echo "Waiting for $name at $host:$port ..."
  for i in $(seq 1 "$attempts"); do
    if nc -z "$host" "$port" 2>/dev/null; then
      echo "✓ $name is ready"
      return 0
    fi
    echo "Attempt $i/$attempts..."
    sleep 2
  done

  echo "ERROR: $name was not reachable at $host:$port"
  exit 1
}

wait_for_db() {
  extract_db_host_port
  wait_for_tcp "PostgreSQL" "$DB_HOST" "$DB_PORT" 30
}

wait_for_redis() {
  if [ "$PROCESS_MODE" != "worker" ] && [ "$PROCESS_MODE" != "all" ]; then
    return 0
  fi

  local redis_url="${CELERY_BROKER_URL:-${REDIS_URL:-redis://redis:6379/0}}"
  local redis_without_scheme="${redis_url#*://}"
  local redis_host_port="${redis_without_scheme%%/*}"
  local redis_host="${redis_host_port%%:*}"
  local redis_port="${redis_host_port##*:}"

  if [ "$redis_host" = "$redis_port" ]; then
    redis_port="6379"
  fi

  wait_for_tcp "Redis" "$redis_host" "$redis_port" 30
}

ensure_pgvector() {
  if [ "$RUN_MIGRATIONS" != "true" ] && [ "$PROCESS_MODE" != "migrate" ]; then
    return 0
  fi

  echo "Creating pgvector extension if needed..."
  PSQL_URL=$(echo "$DATABASE_URL" | sed 's|postgresql+asyncpg://|postgresql://|')
  psql "$PSQL_URL" -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null && \
    echo "✓ pgvector ready" || echo "⚠ pgvector setup skipped or already handled"
}

run_migrations() {
  if [ "$RUN_MIGRATIONS" != "true" ] && [ "$PROCESS_MODE" != "migrate" ]; then
    echo "Skipping migrations."
    return 0
  fi

  echo "Running Alembic migrations..."
  PYTHONPATH=/app/backend python scripts/migrate.py
}

run_seed() {
  if [ "$RUN_SEED" != "true" ]; then
    echo "Skipping seed."
    return 0
  fi

  echo "Running seed..."
  PYTHONPATH=/app/backend python scripts/seed.py
}

start_api() {
  echo "Starting FastAPI only..."
  if [ "${UVICORN_RELOAD:-false}" = "true" ]; then
    exec uvicorn app.main:app \
      --host 0.0.0.0 \
      --port "${PORT:-8000}" \
      --proxy-headers \
      --forwarded-allow-ips "*" \
      --reload \
      --reload-dir /app/backend/app
  fi

  exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${UVICORN_WORKERS:-1}" \
    --proxy-headers \
    --forwarded-allow-ips "*"
}

start_worker() {
  echo "Starting Celery worker only..."
  exec celery -A app.core.celery worker \
    --loglevel="${CELERY_LOGLEVEL:-info}" \
    --pool="${CELERY_POOL:-threads}" \
    --concurrency="${CELERY_CONCURRENCY:-4}" \
    --queues="${CELERY_QUEUES:-default,documents,ai,celery}"
}

start_all() {
  echo "Starting combined FastAPI + Celery via supervisord..."
  exec supervisord -c /app/backend/supervisord.conf
}

log_header
wait_for_db
wait_for_redis
ensure_pgvector
run_migrations
run_seed

case "$PROCESS_MODE" in
  api)
    start_api
    ;;
  worker)
    start_worker
    ;;
  all)
    start_all
    ;;
  migrate)
    echo "Migration mode complete. Exiting."
    exit 0
    ;;
esac
