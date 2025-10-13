from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class AgentStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    OUT = "out"


class AgentState(str, Enum):
    GROWTH = "growth"
    FALL = "fall"


class Agent(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    agent_id: str
    name: Optional[str] = None
    status: AgentStatus = AgentStatus.ACTIVE
    entry_date: Optional[datetime] = None
    exit_date: Optional[datetime] = None
    total_roi: float = 0.0
    current_accounts: int = 0
    current_aum: float = 0.0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

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
