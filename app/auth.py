import secrets
from fastapi import Request, HTTPException
from app.config import settings

_sessions: dict[str, bool] = {}


def verify_password(plain: str) -> bool:
    return plain == settings.admin_password


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = True
    return token


def is_authenticated(request: Request) -> bool:
    token = request.cookies.get("session")
    return token is not None and _sessions.get(token, False)


def require_auth(request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=303, headers={"Location": "/login"})
