"""FastAPI application assembly."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.gateway.routes.health import router as health_router
from services.gateway.routes.jobs import router as jobs_router

app = FastAPI(title="gRPC Pipeline Gateway")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(jobs_router)
