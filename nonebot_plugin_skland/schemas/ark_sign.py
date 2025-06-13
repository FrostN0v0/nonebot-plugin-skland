from pydantic import BaseModel


class Resource(BaseModel):
    name: str


class Award(BaseModel):
    resource: Resource
    count: int


class ArkSignResponse(BaseModel):
    awards: list[Award]


class ArkSignResult(BaseModel):
    success_count: int
    failed_count: int
    results: dict[str, str]
    summary: str
