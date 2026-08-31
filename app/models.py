from pydantic import BaseModel
from typing import Optional


class ReportRequest(BaseModel):
    report_type: str
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    threshold_days: int = 180


class ReportResult(BaseModel):
    report_type: str
    title: str
    summary: dict
    data: list[dict]
    filename: Optional[str] = None
