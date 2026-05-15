from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import init_db, run_migrations
from app.services.scheduler import init_scheduler
from app.routes.auth_routes import router as auth_router
from app.routes.dashboard import router as dashboard_router
from app.routes.api import router as api_router
from app.routes.webhooks import router as webhooks_router
from app.routes.campaigns import router as campaigns_router
from app.routes.campaign_api import router as campaign_api_router
from app.routes.ghl_webhooks import router as ghl_webhooks_router
from app.routes.referrals import router as referrals_router
from app.routes.referral_api import router as referral_api_router
from app.routes.referral_public import router as referral_public_router
from app.routes.marketing_assets import router as marketing_assets_router

# Ensure directories exist
Path("media/images").mkdir(parents=True, exist_ok=True)
Path("media/marketing_assets").mkdir(parents=True, exist_ok=True)
Path("data").mkdir(parents=True, exist_ok=True)
Path("prompts").mkdir(parents=True, exist_ok=True)
Path("config").mkdir(parents=True, exist_ok=True)


# ── Security Headers Middleware ──────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.tailwindcss.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: blob: https:; "
            "connect-src 'self'; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "frame-ancestors 'none'"
        )

        # Cache-Control on sensitive pages/API routes
        path = request.url.path
        if path.startswith("/dashboard") or path.startswith("/api/") or path.startswith("/campaigns"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"

        return response


# ── CSRF Protection Middleware ───────────────────────────
# Webhooks are exempt (external services POST to them)
_CSRF_EXEMPT_PREFIXES = ("/webhooks/", "/ghl/webhook", "/referral/track")


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)

        # Exempt webhook endpoints (external services need to POST)
        path = request.url.path
        for prefix in _CSRF_EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # HTMX requests send a custom header — custom headers trigger CORS preflight
        # so cross-origin HTMX requests are blocked by the browser
        if request.headers.get("HX-Request"):
            return await call_next(request)

        # For non-HTMX POST (traditional form submissions), check Origin/Referer
        origin = request.headers.get("origin") or ""
        referer = request.headers.get("referer") or ""
        request_host = request.headers.get("host", "")

        if origin:
            if urlparse(origin).netloc == request_host:
                return await call_next(request)
        elif referer:
            if urlparse(referer).netloc == request_host:
                return await call_next(request)
        else:
            # No Origin or Referer header — allow (same-origin form submissions
            # may omit these headers in some browsers/privacy settings)
            return await call_next(request)

        # Origin/Referer present but mismatched — block
        return JSONResponse({"error": "CSRF validation failed"}, status_code=403)


app = FastAPI(title="Zerona Content Engine")
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=500)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(api_router)
app.include_router(webhooks_router)
app.include_router(campaigns_router)
app.include_router(campaign_api_router)
app.include_router(ghl_webhooks_router)
app.include_router(referrals_router)
app.include_router(referral_api_router)
app.include_router(referral_public_router)
app.include_router(marketing_assets_router)


@app.on_event("startup")
def startup():
    init_db()
    run_migrations()
    init_scheduler()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")
