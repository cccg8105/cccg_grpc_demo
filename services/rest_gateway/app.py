"""FastAPI application for REST pipeline gateway."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.rest_gateway.routes.health import router as health_router
from services.rest_gateway.routes.jobs import router as jobs_router
from services.rest_gateway.routes.progress import router as progress_router

app = FastAPI(title="REST Pipeline Gateway")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(jobs_router)
app.include_router(progress_router)
