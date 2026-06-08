from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.applications import router as applications_router
from app.api.dean import router as dean_router
from app.api.documents import router as documents_router
from app.api.evaluation import router as evaluation_router
from app.api.events import router as events_router
from app.api.intibak import router as intibak_router
from app.api.programs import router as programs_router
from app.api.qa import router as qa_router
from app.api.ranking import router as ranking_router
from app.api.student_affairs import router as student_affairs_router
from app.api.ydyo import router as ydyo_router
from app.core.config import settings
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

_cors_origins = list({
    "http://localhost:5173",
    settings.FRONTEND_URL,
})

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",  # Vercel preview deploys
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
app.include_router(applications_router, prefix="/api/applications", tags=["applications"])
app.include_router(documents_router, prefix="/api/documents", tags=["documents"])
app.include_router(events_router, prefix="/api/applications", tags=["events"])
app.include_router(programs_router, prefix="/api", tags=["programs"])
app.include_router(student_affairs_router, prefix="/api/staff", tags=["student-affairs"])
app.include_router(qa_router, prefix="/api/messages", tags=["messages"])
app.include_router(evaluation_router, prefix="/api/ygk", tags=["evaluation"])
app.include_router(ranking_router, prefix="/api/ygk/rankings", tags=["ranking"])
app.include_router(intibak_router, prefix="/api/ygk", tags=["intibak"])
app.include_router(ydyo_router, prefix="/api/ydyo", tags=["ydyo"])
app.include_router(dean_router, prefix="/api/dean", tags=["dean"])
