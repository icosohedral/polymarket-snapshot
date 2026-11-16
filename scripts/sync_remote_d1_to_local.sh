#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DB_NAME="polymarket-snapshot"
EXPORT_FILE_BASE="$(mktemp -t polymarket-d1-export)"
EXPORT_FILE="${EXPORT_FILE_BASE}.sql"
mv "$EXPORT_FILE_BASE" "$EXPORT_FILE"

cleanup() {
  rm -f "$EXPORT_FILE"
}

trap cleanup EXIT

load_env_file() {
  local file="$1"
  if [[ -f "$file" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$file"
    set +a
  fi
}

load_env_file "$ROOT_DIR/.env"
load_env_file "$ROOT_DIR/.dev.vars"

if [[ -z "${CLOUDFLARE_API_TOKEN:-}" ]]; then
  echo "CLOUDFLARE_API_TOKEN is required for remote D1 export." >&2
  echo "Set the token in your shell or .dev.vars, then rerun: npm run d1:local:sync" >&2
  exit 1
fi

echo "Exporting remote D1 database to temporary SQL: $EXPORT_FILE"
npx wrangler d1 export "$DB_NAME" --remote --output "$EXPORT_FILE"

echo "Resetting local D1 database"
npx wrangler d1 execute "$DB_NAME" --local --file="$ROOT_DIR/d1/reset.sql"

echo "Importing remote SQL into local D1 database"
npx wrangler d1 execute "$DB_NAME" --local --file="$EXPORT_FILE"

echo "Local D1 sync complete"
