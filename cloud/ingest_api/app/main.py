from fastapi import FastAPI

from .routes import router

app = FastAPI(title="Smart Campus Ingest API")
app.include_router(router)
