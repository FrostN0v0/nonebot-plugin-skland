from pydantic import BaseModel


class ClearInfo(BaseModel):
    difficulty: str
    grade: int
    endings: list[str]


class Color(BaseModel):
    blue: int
    red: int
    green: int


class Predict(BaseModel):
    totem: int
    chaos: int


class Alchemy(BaseModel):
    shield: int
    relic: int
    population: int


class Fragment(BaseModel):
    wish: int
    inspiration: int
    idea: int


class EndingSanDetail(BaseModel):
    endingSan: list[int]


class Vision(BaseModel):
    vision: dict[str, int]


class RogueCareer(BaseModel):
    clearInfo: ClearInfo
    invest: int
    gold: int
    node: int
    hope: int
    upgrade: int
    sacrifice: int
    expedition: int
    chaosGain: int
    chaosLost: int
    game: int
    friend: int
    abyss: int
    totem: int
    totemUse: int
    enchant: int
    relic: int
    color: dict[str, int]
    predict: Predict
    travel: int
    step: int
    history: int
    explore: int
    memory: int
    protect: int
    alchemy: Alchemy
    fragment: Fragment
    visions: list[Vision]
    modeStop: dict[str, str]
    wish: int
    variation: int
    mutation: int
    diceTrend: list[int]
    dice: int
    coin: int
    cost: int
    endingSanList: dict[str, EndingSanDetail]
