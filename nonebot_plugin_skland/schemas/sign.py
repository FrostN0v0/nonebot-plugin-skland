"""Shared sign cache and presentation contracts."""

from typing import Any, Literal, TypedDict

from pydantic import BaseModel

SignGame = Literal["arknights", "endfield"]


class SignCacheEntry(TypedDict):
    owner_id: int
    character_id: int
    nickname: str
    role_id: str
    server_id: str
    server_name: str
    result: dict[str, Any] | str


class SignCache(TypedDict):
    timestamp: str
    data: list[SignCacheEntry]


class SignResult(BaseModel):
    success_count: int
    failed_count: int
    results: list[tuple[str, str]]
    summary: str
