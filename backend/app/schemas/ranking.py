import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class GenerateRankingRequest(BaseModel):
    program_id: uuid.UUID
    period_id: uuid.UUID


class RankingEntryOut(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    composite_score: Decimal
    position: int
    is_primary: bool

    model_config = {"from_attributes": True}


class RankingOut(BaseModel):
    id: uuid.UUID
    program_id: uuid.UUID
    period_id: uuid.UUID
    status: str
    approved_by: Optional[uuid.UUID]
    approved_at: Optional[datetime]
    published_at: Optional[datetime]
    entries: List[RankingEntryOut]

    model_config = {"from_attributes": True}
