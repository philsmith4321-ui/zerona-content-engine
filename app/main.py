from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.services.scheduler import init_scheduler
from app.routes.auth_routes import router as auth_router
from app.routes.dashboard import router as dashboard_router
from app.routes.api import router as api_router

# Ensure directories exist
Path("media/images").mkdir(parents=True, exist_ok=True)
Path("data").mkdir(parents=True, exist_ok=True)
Path("prompts").mkdir(parents=True, exist_ok=True)
Path("config").mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Zerona Content Engine")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(api_router)


@app.on_event("startup")
def startup():
    init_db()
    init_scheduler()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")
