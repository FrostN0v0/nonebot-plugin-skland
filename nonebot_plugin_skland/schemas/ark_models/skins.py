from pydantic import BaseModel


class Skin(BaseModel):
    """持有皮肤"""

    id: str
    ts: int
