from pydantic import BaseModel


class Resource(BaseModel):
    name: str


class Award(BaseModel):
    resource: Resource
    count: int


class ArkSignResponse(BaseModel):
    awards: list[Award]
