import os
import sys
import time
from urllib.parse import quote_plus

import psycopg2


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> int:
    host = _required("DB_HOST")
    port = int(os.getenv("DB_PORT", "5432"))
    user = _required("DB_USER")
    password = _required("DB_PASSWORD")
    dbname = _required("DB_NAME")

    timeout_s = int(os.getenv("DB_WAIT_TIMEOUT", "60"))
    interval_s = float(os.getenv("DB_WAIT_INTERVAL", "1"))

    dsn = (
        f"dbname={quote_plus(dbname)} user={quote_plus(user)} "
        f"password={quote_plus(password)} host={quote_plus(host)} port={port}"
    )

    deadline = time.monotonic() + timeout_s
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            conn = psycopg2.connect(dsn)
            conn.close()
            return 0
        except Exception as exc:  # noqa: BLE001 - intentionally broad for retries
            last_error = exc
            time.sleep(interval_s)

    print(f"Timed out waiting for Postgres at {host}:{port}/{dbname}", file=sys.stderr)
    if last_error:
        print(f"Last error: {last_error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
