from __future__ import annotations

from pydantic import BaseModel


class JobProgress(BaseModel):
    task_id: str
    status: str = "PENDING"
    percent: int = 0
    stage: str = "aguardando"
    message: str = ""

