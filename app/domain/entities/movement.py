from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Movement(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    agente_id: Optional[str] = Field(default=None, alias="agente_id")
    user: str
    user_id: str = Field(alias="userId")
    created_time: str = Field(alias="createdTime")
    updated_time: str = Field(alias="updatedTime")
    symbol: str
    side: str
    leverage: int
    qty: str
    closed_pnl: float = Field(alias="closedPnl")
    avg_entry_price: str = Field(alias="avgEntryPrice")
    avg_exit_price: str = Field(alias="avgExitPrice")
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")
    updated_at: Optional[datetime] = Field(default=None, alias="updatedAt")

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
