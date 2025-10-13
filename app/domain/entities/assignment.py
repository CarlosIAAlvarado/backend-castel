from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Assignment(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    date: datetime
    account_id: str
    agent_id: str
    balance: float
    assigned_at: datetime
    unassigned_at: Optional[datetime] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    def to_dict(self) -> dict:
        data = self.model_dump(by_alias=True)
        if data.get("_id"):
            data["_id"] = str(data["_id"])
        return data
