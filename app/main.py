from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

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

app = FastAPI(title="Zerona Content Engine")

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
