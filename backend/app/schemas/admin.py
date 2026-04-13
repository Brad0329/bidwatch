from pydantic import BaseModel


class CollectionRunRequest(BaseModel):
    source_id: int | None = None
    days: int = 1
    sync: bool = False


class CollectionRunResponse(BaseModel):
    status: str
    message: str
    task_id: str | None = None
