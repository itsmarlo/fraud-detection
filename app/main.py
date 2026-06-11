from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_claims,
    routes_documents,
    routes_files,
    routes_health,
    routes_model,
)
from app.core.config import get_settings


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.metadata_file.parent.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Explainable multimodal fraud scoring for motor insurance claims.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=settings.cors_origin_list != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_health.router)
app.include_router(routes_claims.router)
app.include_router(routes_files.router)
app.include_router(routes_documents.router)
app.include_router(routes_model.router)
