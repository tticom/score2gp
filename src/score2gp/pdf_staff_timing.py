from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PdfStaffTimingEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    page_index: int = Field(ge=1)
    system_index: int = Field(ge=1)
    staff_index: int | None = Field(default=None, ge=1)
    local_bar_index: int = Field(ge=1)
    x: float
    onset_ticks: int = Field(ge=0)
    duration_ticks: int = Field(ge=0)
    is_rest: bool = False
    voice_index: int = 0

