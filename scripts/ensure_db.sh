#!/usr/bin/env bash
# Apply CLIENTS migrations + syncdb for Django tables. Idempotent.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
exec python manage.py ensure_db "$@"
