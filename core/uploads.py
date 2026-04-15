from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

from fastapi import UploadFile


def _safe_segment(value: str) -> str:
    value = (value or "").strip() or "unknown"
    value = re.sub(r"[^a-zA-Z0-9_-]+", "_", value)
    return value[:80]


def ensure_driver_upload_dir(driver_name: str | None, firebase_uid: str) -> Path:
    base = Path(os.getenv("UPLOADS_DIR", "uploads")).resolve()
    folder = f"{_safe_segment(driver_name or 'driver')}_{_safe_segment(firebase_uid)}"
    dest = base / "drivers" / folder
    dest.mkdir(parents=True, exist_ok=True)
    return dest


async def save_upload_file(file: UploadFile, dest_dir: Path) -> Path:
    suffix = Path(file.filename or "").suffix
    filename = f"{uuid.uuid4().hex}{suffix}"
    dest_path = dest_dir / filename

    content = await file.read()
    dest_path.write_bytes(content)
    return dest_path


def uploaded_file_url_path(driver_name: str | None, firebase_uid: str, filename: str) -> str:
    folder = f"{_safe_segment(driver_name or 'driver')}_{_safe_segment(firebase_uid)}"
    # URL-ish relative path; serving is app-specific
    return f"/uploads/drivers/{folder}/{filename}"
