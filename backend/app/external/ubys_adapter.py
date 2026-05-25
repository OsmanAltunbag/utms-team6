import asyncio
from dataclasses import dataclass


class ExternalServiceTimeoutError(Exception):
    pass


@dataclass
class TranscriptData:
    gpa_4: float
    credits: int
    institution: str


class UBYSAdapter:
    _TIMEOUT = 10.0

    async def fetch_transcript(self, national_id: str) -> TranscriptData:
        try:
            async with asyncio.timeout(self._TIMEOUT):
                # Production: call real UBYS REST endpoint here
                await asyncio.sleep(0)
                return TranscriptData(gpa_4=3.50, credits=120, institution="IZTECH")
        except asyncio.TimeoutError:
            raise ExternalServiceTimeoutError(
                f"UBYS timed out for national_id={national_id}"
            )
