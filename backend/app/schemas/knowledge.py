"""Knowledge summary response schemas."""

import datetime

from pydantic import BaseModel, ConfigDict


class KnowledgeSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    type: str
    content: str
    generated_at: datetime.datetime
    model: str | None = None
