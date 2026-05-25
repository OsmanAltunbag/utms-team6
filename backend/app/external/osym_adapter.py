import asyncio
from dataclasses import dataclass

from app.external.ubys_adapter import ExternalServiceTimeoutError


@dataclass
class YKSScore:
    score: float
    exam_year: int
    score_type: str


class OSYMAdapter:
    _TIMEOUT = 10.0

    async def fetch_yks_score(self, national_id: str) -> YKSScore:
        try:
            async with asyncio.timeout(self._TIMEOUT):
                # Production: call real ÖSYM REST endpoint here
                await asyncio.sleep(0)
                return YKSScore(score=450.0, exam_year=2024, score_type="SAY")
        except asyncio.TimeoutError:
            raise ExternalServiceTimeoutError(
                f"ÖSYM timed out for national_id={national_id}"
            )
