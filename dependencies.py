from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sqlalchemy.orm import Session

from database import get_db
import crud.user as crud_user
from models.user import User


security = HTTPBearer(auto_error=False)


def verify_firebase_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    authorization: Optional[str] = Header(None),
) -> dict:
    """Verify Firebase ID token.

    Expected header: `Authorization: Bearer <firebase_id_token>`.

    Notes:
    - Uses `HTTPBearer` parsing (preferred) and falls back to raw header parsing.
    - Set `AUTH_DEBUG=1` to print diagnostic logs (token prefix + exact verify error).
    - Requires `firebase-admin` and a configured service account.
      Set `GOOGLE_APPLICATION_CREDENTIALS` to a service-account JSON path.
    """

    token: Optional[str] = None
    if credentials is not None:
        token = (credentials.credentials or "").strip()
    elif authorization:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization scheme")
        token = authorization.split(" ", 1)[1].strip()

    # Bypass auth completely when Firebase is disabled (local development)
    if os.getenv("FIREBASE_AUTH_DISABLED") == "1":
        return {"uid": "dev_admin", "phone_number": "0000000000", "email": "admin@caby24.com"}
    
    if not token:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if os.getenv("AUTH_DEBUG") == "1":
        prefix = token[:15]
        print(f"🔥 RECEIVED TOKEN: {prefix}... (Length: {len(token)})")

    try:
        from firebase_admin import auth
    except Exception:
        raise HTTPException(status_code=500, detail="firebase-admin is not installed")

    try:
        return auth.verify_id_token(token)
    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Firebase token expired")
    except auth.RevokedIdTokenError:
        raise HTTPException(status_code=401, detail="Firebase token revoked")
    except auth.InvalidIdTokenError as e:
        # Most common causes: wrong Firebase project credentials, malformed token.
        if os.getenv("AUTH_DEBUG") == "1":
            print(f"❌ FIREBASE VERIFICATION FAILED: {str(e)}")
            raise HTTPException(status_code=401, detail=f"Invalid authentication credentials: {e}")
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except auth.CertificateFetchError as e:
        # Backend cannot fetch Google's public keys (network/DNS). Treat as transient.
        if os.getenv("AUTH_DEBUG") == "1":
            print(f"❌ FIREBASE VERIFICATION FAILED: {str(e)}")
            raise HTTPException(status_code=503, detail=f"Firebase key fetch failed: {e}")
        raise HTTPException(status_code=503, detail="Firebase key fetch failed")
    except Exception as e:
        if os.getenv("AUTH_DEBUG") == "1":
            print(f"❌ FIREBASE VERIFICATION FAILED: {str(e)}")
            raise HTTPException(status_code=401, detail=f"Invalid authentication credentials: {e}")
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")


def verify_raw_firebase_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    if credentials is None or not (credentials.credentials or "").strip():
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = credentials.credentials.strip()

    try:
        from firebase_admin import auth
    except Exception:
        raise HTTPException(status_code=500, detail="firebase-admin is not installed")

    try:
        return auth.verify_id_token(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Firebase token: {str(e)}")


def get_current_user(
    decoded_token: dict = Depends(verify_firebase_token),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the current customer user from the auth token.

    Expects Firebase phone-auth tokens so we can map `phone_number` -> `users.phone`.
    """

    # Bypass for local development
    if os.getenv("FIREBASE_AUTH_DISABLED") == "1":
        return User(id="dev_admin", phone="0000000000")

    phone = decoded_token.get("phone_number") or decoded_token.get("phone")
    if not phone or not str(phone).strip():
        raise HTTPException(status_code=401, detail="Missing phone number in authentication token")

    phone = str(phone).strip()

    candidates: list[str] = [phone]
    if phone.startswith("+91"):
        candidates.append(phone[3:])
    if phone.startswith("+"):
        candidates.append(phone[1:])

    for candidate in candidates:
        user = crud_user.get_user_by_phone(db, candidate)
        if user:
            return user

    raise HTTPException(status_code=404, detail="User not found")


def get_universal_user(
    decoded_token: dict = Depends(verify_firebase_token),
) -> dict:
    uid = decoded_token.get("uid") or decoded_token.get("user_id") or decoded_token.get("sub")
    if not uid:
        raise HTTPException(status_code=401, detail="Missing user id in authentication token")

    role = decoded_token.get("role", "user")
    return {"uid": uid, "role": role}
