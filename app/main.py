from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import init_db

app = FastAPI(title="Zerona Content Engine")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
async def health():
    return {"status": "ok"}
