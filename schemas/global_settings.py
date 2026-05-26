from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class GlobalSettingBase(BaseModel):
    value: str
    description: Optional[str] = None


class GlobalSettingCreate(GlobalSettingBase):
    key: str


class GlobalSettingUpdate(GlobalSettingBase):
    pass


class GlobalSettingRead(GlobalSettingBase):
    key: str
    updated_at: datetime

    model_config = {"from_attributes": True}
