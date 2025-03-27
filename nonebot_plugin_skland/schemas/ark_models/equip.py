from pydantic import BaseModel


class Equipment(BaseModel):
    id: str
    name: str
    typeIcon: str
