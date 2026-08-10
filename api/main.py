"""FastAPI application entrypoint: `uvicorn api.main:app`."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import capacity, meta, regions

app = FastAPI(title="BNetzA Renewable Capacity API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(meta.router)
app.include_router(regions.router)
app.include_router(capacity.router)
