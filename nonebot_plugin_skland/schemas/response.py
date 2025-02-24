from nonebot.compat import PYDANTIC_V2
from pydantic import BaseModel, ConfigDict


class Resource(BaseModel):
    name: str


class Award(BaseModel):
    resource: Resource
    count: int


class ArkSignResponse(BaseModel):
    awards: list[Award]

    if PYDANTIC_V2:
        model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)
    else:

        class Config:
            extra = "allow"
            arbitrary_types_allowed = True
