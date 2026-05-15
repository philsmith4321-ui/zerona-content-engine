import hashlib
import hmac
import os
import time

from fastapi import Request, HTTPException
from app.config import settings

SESSION_MAX_AGE = 86400  # 24 hours

# Server-side session revocation set
_revoked_tokens: set[str] = set()


def _sign(payload: str) -> str:
    key = settings.admin_password.encode()
    return hmac.HMAC(key, payload.encode(), hashlib.sha256).hexdigest()


def verify_password(plain: str) -> bool:
    if not settings.admin_password:
        raise ValueError("ADMIN_PASSWORD not set in environment — refusing to start with empty password")
    if len(settings.admin_password) < 8:
        raise ValueError("ADMIN_PASSWORD must be at least 8 characters")
    return hmac.compare_digest(plain, settings.admin_password)


def create_session_token() -> str:
    nonce = os.urandom(16).hex()
    issued = str(int(time.time()))
    payload = f"{issued}.{nonce}"
    sig = _sign(payload)
    return f"{payload}.{sig}"


def revoke_token(token: str):
    """Add a token to the server-side revocation set."""
    _revoked_tokens.add(token)


def is_authenticated(request: Request) -> bool:
    token = request.cookies.get("session")
    if not token:
        return False
    if token in _revoked_tokens:
        return False
    parts = token.rsplit(".", 1)
    if len(parts) != 2:
        return False
    payload, sig = parts
    if not hmac.compare_digest(sig, _sign(payload)):
        return False
    try:
        issued_str = payload.split(".")[0]
        issued = int(issued_str)
    except (ValueError, IndexError):
        return False
    if time.time() - issued > SESSION_MAX_AGE:
        return False
    return True


def require_auth(request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=303, headers={"Location": "/login"})
