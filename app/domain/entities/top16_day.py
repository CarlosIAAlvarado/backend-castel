from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime, date


class Top16Day(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }
    )

    id: Optional[str] = Field(default=None, alias="_id")
    date: date
    rank: int
    agent_id: str
    roi_7d: float
    roi_30d: Optional[float] = Field(default=None, exclude=True)
    n_accounts: int
    total_aum: float
    is_in_casterly: bool = False
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")

    def to_dict(self) -> dict:
        data = self.model_dump(by_alias=True, exclude_none=True)
        if data.get("_id"):
            data["_id"] = str(data["_id"])
        return data
