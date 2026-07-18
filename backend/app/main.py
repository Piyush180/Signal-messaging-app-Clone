"""
Application entry point.

The `lifespan` context runs once on startup and once on shutdown. On startup we
(optionally) create tables, reset stale presence, and seed demo data — so a
fresh clone is immediately usable with `uvicorn app.main:app`, exactly as the
assignment asks ("seed your database ... immediately usable").
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import Base, AsyncSessionLocal, engine
from app.services import presence as presence_service
from app.websockets.endpoints import router as ws_router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Import models so every table is registered before create_all.
    from app import models  # noqa: F401
    from app.seed import seed_if_empty

    if settings.AUTO_INIT_DB:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with AsyncSessionLocal() as db:
            await presence_service.reset_all_offline(db)
        await seed_if_empty()
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Explicit origins (never "*" with credentials). Comes from config.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(ws_router)


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok", "service": settings.PROJECT_NAME}
