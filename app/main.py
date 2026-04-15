from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Zerona Content Engine")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")


@app.get("/health")
async def health():
    return {"status": "ok"}
