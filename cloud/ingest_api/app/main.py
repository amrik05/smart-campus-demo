from fastapi import FastAPI

from .db import Base, engine
from .routes import router

app = FastAPI(title="Smart Campus Ingest API")
app.include_router(router)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
