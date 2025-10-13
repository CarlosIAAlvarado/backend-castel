from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Balance(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    user_id_db: str = Field(alias="userIdDB")
    user_id: str = Field(alias="userId")
    account_id: Optional[str] = Field(default=None, alias="account_id")  # Agregado por migracion
    balance: float
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

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
