import time
from collections import defaultdict

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.auth import verify_password, create_session_token, revoke_token, SESSION_MAX_AGE

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# ── Login rate limiting ──────────────────────────────────
_login_attempts: dict[str, list[float]] = defaultdict(list)
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW = 900  # 15 minutes


def _is_login_rate_limited(ip: str) -> bool:
    now = time.time()
    cutoff = now - _LOGIN_WINDOW
    _login_attempts[ip] = [t for t in _login_attempts[ip] if t > cutoff]
    return len(_login_attempts[ip]) >= _LOGIN_MAX_ATTEMPTS


def _record_login_attempt(ip: str):
    _login_attempts[ip].append(time.time())


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
async def login(request: Request, password: str = Form(...)):
    client_ip = request.client.host if request.client else "unknown"
    if _is_login_rate_limited(client_ip):
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Too many login attempts. Try again in 15 minutes."},
        )
    if verify_password(password):
        _login_attempts.pop(client_ip, None)
        token = create_session_token()
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie("session", token, httponly=True, samesite="lax", max_age=SESSION_MAX_AGE)
        return response
    _record_login_attempt(client_ip)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid password"})


@router.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("session")
    if token:
        revoke_token(token)
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session")
    return response
