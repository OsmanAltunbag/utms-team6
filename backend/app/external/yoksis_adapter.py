import asyncio
from dataclasses import dataclass

from app.external.ubys_adapter import ExternalServiceTimeoutError


@dataclass
class YOKSISRecord:
    gpa_4: float
    institution: str
    credits: int


class YOKSISAdapter:
    _TIMEOUT = 10.0

    async def fetch_academic_record(self, national_id: str) -> YOKSISRecord:
        try:
            async with asyncio.timeout(self._TIMEOUT):
                # Production: call real YÖKSİS REST endpoint here
                await asyncio.sleep(0)
                return YOKSISRecord(gpa_4=3.50, institution="IZTECH", credits=120)
        except asyncio.TimeoutError:
            raise ExternalServiceTimeoutError(
                f"YÖKSİS timed out for national_id={national_id}"
            )
