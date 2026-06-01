import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def create_access_token(data: Dict[str, Any], expires_delta_seconds: int = 60 * 60 * 24) -> str:
    secret_key = os.getenv("JWT_SECRET_KEY", os.getenv("SECRET_KEY", "dev-secret-key"))
    header = {"alg": "HS256", "typ": "JWT"}

    payload = dict(data)
    payload["iat"] = int(time.time())
    payload["exp"] = payload["iat"] + expires_delta_seconds

    header_segment = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_segment = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    signature = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_segment = _b64url_encode(signature)

    return f"{header_segment}.{payload_segment}.{signature_segment}"
