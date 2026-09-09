import os
import time
from typing import Any, Dict
from jose import jwt, JWTError

SECRET_KEY = os.getenv("JWT_SECRET_KEY", os.getenv("SECRET_KEY", "dev-secret-key"))
ALGORITHM = "HS256"

def create_access_token(data: Dict[str, Any], expires_delta_seconds: int = 60 * 60 * 24) -> str:
    to_encode = data.copy()
    expire = int(time.time()) + expires_delta_seconds
    to_encode.update({"iat": int(time.time()), "exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
