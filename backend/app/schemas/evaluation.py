import uuid
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class DeptConditionItem(BaseModel):
    id: uuid.UUID
    rule_key: str
    rule_value: str
    description: Optional[str]
    is_active: bool

    model_config = {"from_attributes": True}


class DeptConditionsResponse(BaseModel):
    application_id: uuid.UUID
    program_id: uuid.UUID
    conditions: List[DeptConditionItem]


class EvaluateConditionsRequest(BaseModel):
    notes: Optional[str] = None


class ConditionResult(BaseModel):
    rule_key: str
    passed: bool
    detail: Optional[str]


class EvaluateConditionsResponse(BaseModel):
    application_id: uuid.UUID
    all_passed: bool
    results: List[ConditionResult]


class CourseMappingItem(BaseModel):
    source_course: str
    target_course: str
    source_credits: Optional[Decimal] = None
    target_credits: Optional[Decimal] = None
    equivalence_type: str = "FULL"
    notes: Optional[str] = None


class ManualCourseMappingRequest(BaseModel):
    mappings: List[CourseMappingItem]


class ManualCourseMappingResponse(BaseModel):
    intibak_table_id: uuid.UUID
    application_id: uuid.UUID
    mappings_added: int
