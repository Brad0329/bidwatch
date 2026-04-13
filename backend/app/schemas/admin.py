from datetime import datetime

from pydantic import BaseModel


class SystemSourceResponse(BaseModel):
    id: int
    name: str
    collector_type: str
    is_active: bool
    last_collected_at: datetime | None
    last_collected_count: int | None

    model_config = {"from_attributes": True}


class CollectionRunRequest(BaseModel):
    source_id: int | None = None
    days: int = 1
    sync: bool = False


class CollectionRunResponse(BaseModel):
    status: str
    message: str
    task_id: str | None = None
