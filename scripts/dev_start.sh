#!/usr/bin/env bash
# Loads .env into environment for local development, then starts uvicorn.
# Usage: ./scripts/dev_start.sh

set -e
if [ -f .env ]; then
  # shellcheck disable=SC1091
  export $(grep -v '^#' .env | xargs)
fi

uvicorn main:app --reload --host 0.0.0.0 --port ${PORT:-8000}
