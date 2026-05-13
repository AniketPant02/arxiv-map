#!/usr/bin/env bash
set -euo pipefail

# This script uses docker exec commands to apply SQL migration files to a PostgreSQL database running via local docker compose.

PROFILE="${PROFILE:-dev}"
DB_SERVICE="${DB_SERVICE:-db}"
DB_USER="${POSTGRES_USER:-arxiv}"
DB_NAME="${POSTGRES_DB:-arxiv}"
MIGRATIONS_DIR="${MIGRATIONS_DIR:-db/migrations}"

if [ ! -d "$MIGRATIONS_DIR" ]; then
  echo "Missing migrations directory: $MIGRATIONS_DIR"
  exit 1
fi

echo "Starting Postgres service..."
docker compose --profile "$PROFILE" up -d "$DB_SERVICE"

echo "Waiting for Postgres to be ready..."
until docker compose exec -T "$DB_SERVICE" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; do
  sleep 1
done

echo "Postgres is ready."

echo "Ensuring schema_migrations table exists..."
docker compose exec -T "$DB_SERVICE" psql \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  -v ON_ERROR_STOP=1 \
  -c "
CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  filename TEXT NOT NULL,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"

for file in "$MIGRATIONS_DIR"/*.sql; do
  [ -e "$file" ] || continue

  filename="$(basename "$file")"
  version="${filename%%_*}"

  already_applied="$(
    docker compose exec -T "$DB_SERVICE" psql \
      -U "$DB_USER" \
      -d "$DB_NAME" \
      -tAc "SELECT 1 FROM schema_migrations WHERE version = '$version';"
  )"

  if [ "$already_applied" = "1" ]; then
    echo "Skipping already-applied migration: $filename"
    continue
  fi

  echo "Applying migration: $filename"

  docker compose exec -T "$DB_SERVICE" psql \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -v ON_ERROR_STOP=1 \
    < "$file"

  docker compose exec -T "$DB_SERVICE" psql \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -v ON_ERROR_STOP=1 \
    -c "INSERT INTO schema_migrations (version, filename) VALUES ('$version', '$filename');"

  echo "Applied migration: $filename"
done

echo "All migrations complete."
