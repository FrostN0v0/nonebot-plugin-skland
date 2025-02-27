from pydantic import BaseModel

from .base import Bubble


class TiredChar(BaseModel):
    charId: str
    ap: int
    lastApAddTime: int
    roomSlotId: str
    index: int
    bubble: Bubble
    workTime: int
