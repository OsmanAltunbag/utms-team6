import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.redis import get_redis
from app.domain.enums import UserRole
from app.domain.user import User
from app.repositories.application_repository import ApplicationRepository

router = APIRouter()


@router.get("/{application_id}/events")
async def stream_status_events(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    repo = ApplicationRepository(db)
    application = await repo.get_by_id(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    if (
        current_user.role == UserRole.APPLICANT
        and application.applicant_id != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    r = await get_redis()

    async def event_generator():
        pubsub = r.pubsub()
        await pubsub.subscribe(f"app_status:{application_id}")
        try:
            heartbeat = 0
            while True:
                try:
                    msg = await pubsub.get_message(ignore_subscribe_messages=True)
                except asyncio.CancelledError:
                    break
                if msg and msg.get("type") == "message":
                    yield f"data: {msg['data']}\n\n"
                    heartbeat = 0
                heartbeat += 1
                if heartbeat >= 15:
                    yield ": ping\n\n"
                    heartbeat = 0
                try:
                    await asyncio.sleep(1)
                except asyncio.CancelledError:
                    break
        finally:
            await pubsub.unsubscribe(f"app_status:{application_id}")
            await pubsub.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
