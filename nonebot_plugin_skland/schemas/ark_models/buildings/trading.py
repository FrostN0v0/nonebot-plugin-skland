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
    instId: int
    type: str
    delivery: list[DeliveryItem]
    gain: Gain
    isViolated: bool


class Trading(BaseModel):
    slotId: str
    level: int
    chars: list[BuildingChar]
    completeWorkTime: int
    lastUpdateTime: int
    strategy: str
    stock: list[StockItem]
    stockLimit: int
