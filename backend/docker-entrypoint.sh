#!/bin/sh
set -eu

read_secret() {
  var_name="$1"
  file_var_name="${var_name}_FILE"
  eval "current_value=\${$var_name:-}"
  eval "file_path=\${$file_var_name:-}"

  if [ -n "$current_value" ] && [ -n "$file_path" ]; then
    echo "Both $var_name and $file_var_name are set; use only one." >&2
    exit 1
  fi

  if [ -n "$file_path" ]; then
    if [ ! -f "$file_path" ]; then
      echo "Secret file for $var_name does not exist: $file_path" >&2
      exit 1
    fi
    secret_value="$(tr -d '\r' < "$file_path")"
    export "$var_name=$secret_value"
  fi
}

read_secret "DB_PASSWORD"
read_secret "POSTGRES_PASSWORD"
read_secret "AUTH_TOKEN_SECRET"
read_secret "ADMIN_LOGIN_PASSWORD"
read_secret "ANNOTATOR_LOGIN_PASSWORD"

if [ -z "${DATABASE_URL:-}" ]; then
  export DB_HOST="${DB_HOST:-postgres}"
  export DB_PORT="${DB_PORT:-5432}"
  export DB_NAME="${DB_NAME:-interview}"
  export DB_USER="${DB_USER:-postgres}"
  export DB_PASSWORD="${DB_PASSWORD:-${POSTGRES_PASSWORD:-}}"

  if [ -z "${DB_PASSWORD:-}" ]; then
    echo "DATABASE_URL is not set and no DB password was provided." >&2
    exit 1
  fi

  DATABASE_URL="$(
    python - <<'PY'
import os
from urllib.parse import quote

user = quote(os.environ["DB_USER"], safe="")
password = quote(os.environ["DB_PASSWORD"], safe="")
host = os.environ["DB_HOST"]
port = os.environ["DB_PORT"]
name = os.environ["DB_NAME"]
print(f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}")
PY
  )"
  export DATABASE_URL
fi

echo "Waiting for PostgreSQL..."
python - <<'PY'
import os
import sys
import time

import psycopg

database_url = os.environ["DATABASE_URL"]
timeout = int(os.environ.get("DB_WAIT_TIMEOUT_SECONDS", "60"))
deadline = time.time() + timeout
last_error = None

while time.time() < deadline:
    try:
        with psycopg.connect(database_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        sys.exit(0)
    except Exception as exc:  # pragma: no cover - container startup path
        last_error = exc
        time.sleep(2)

print(f"Database did not become ready within {timeout}s: {last_error}", file=sys.stderr)
sys.exit(1)
PY

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting API server..."
exec uvicorn apps.api.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers "${UVICORN_WORKERS:-1}"
