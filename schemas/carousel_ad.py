from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CarouselAdBase(BaseModel):
    title: Optional[str] = None
    media_type: str = "image"
    target_url: Optional[str] = None
    is_active: bool = True
    display_order: int = 0


class CarouselAdRead(CarouselAdBase):
    id: str
    media_url: str
    created_at: datetime

    model_config = {"from_attributes": True}
