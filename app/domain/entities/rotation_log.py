from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class RotationReason(str, Enum):
    THREE_DAYS_FALL = "three_days_fall"
    STOP_LOSS = "stop_loss"
    MANUAL = "manual"


class RotationLog(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    date: datetime
    agent_out: str
    agent_in: str
    reason: RotationReason
    roi_7d_out: float
    roi_total_out: float
    roi_7d_in: float
    n_accounts: int
    total_aum: float
    created_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    def to_dict(self) -> dict:
        data = self.model_dump(by_alias=True)
        if data.get("_id"):
            data["_id"] = str(data["_id"])
        return data
