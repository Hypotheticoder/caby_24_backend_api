#!/usr/bin/env bash
# Safe dev wrapper: export variables from .env then run alembic with passed args.
# Usage: ./scripts/run_alembic.sh upgrade head
set -euo pipefail

ENV_FILE=".env"
if [ -f "$ENV_FILE" ]; then
  # export all variables in .env into the environment
  # using `set -a` ensures they are exported; `.` sources the file
  set -a
  # shellcheck disable=SC1091
  . "$ENV_FILE"
  set +a
fi

# Forward all args to alembic
alembic "$@"
