from pydantic import BaseModel

from .base import BuildingChar


class DeliveryItem(BaseModel):
    id: str
    count: int
    type: str


class Gain(BaseModel):
    id: str
    count: int
    type: str


class StockItem(BaseModel):
    """储存订单"""

    instId: int
    type: str
    delivery: list[DeliveryItem]
    gain: Gain
    isViolated: bool


class Trading(BaseModel):
    """贸易站"""

    slotId: str
    level: int
    chars: list[BuildingChar]
    completeWorkTime: int
    lastUpdateTime: int
    strategy: str
    stock: list[StockItem]
    stockLimit: int
