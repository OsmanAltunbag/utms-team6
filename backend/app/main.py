from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.applications import router as applications_router
from app.api.documents import router as documents_router
from app.api.programs import router as programs_router
from app.core.redis import close_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_redis()


app = FastAPI(
    title="UTMS — Undergraduate Transfer Management System",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(applications_router, prefix="/api/applications", tags=["applications"])
app.include_router(documents_router, prefix="/api/documents", tags=["documents"])
app.include_router(programs_router, prefix="/api", tags=["programs"])
