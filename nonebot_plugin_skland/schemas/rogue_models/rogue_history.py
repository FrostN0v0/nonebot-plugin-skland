from pydantic import HttpUrl, BaseModel


class Char(BaseModel):
    id: str
    rarity: int
    profession: str
    type: str
    upgradePhase: int
    evolvePhase: int
    level: int
    name: str


class Tag(BaseModel):
    name: str
    icon: HttpUrl
    description: str
    id: int


class Band(BaseModel):
    id: str
    name: str


class Totem(BaseModel):
    id: str
    count: int


class Record(BaseModel):
    id: str
    modeGrade: int
    mode: str
    success: int
    lastChars: list[Char]
    initChars: list[Char]
    troopChars: list[Char]
    gainRelicList: list
    cntCrossedZone: int
    cntArrivedNode: int
    cntBattleNormal: int
    cntBattleElite: int
    cntBattleBoss: int
    cntGainRelicItem: int
    cntRecruitUpgrade: int
    totemList: list[Totem]
    seed: str
    tagList: list[Tag]
    lastStage: str
    score: int
    band: Band
    startTs: str
    endTs: str
    endingText: str
    isCollect: bool


class Medal(BaseModel):
    count: int
    current: int


class RogueHistory(BaseModel):
    medal: Medal
    modeGrade: int
    mode: str
    score: int
    bpLevel: int
    chars: list[Char]
    tagList: list[Tag]
    records: list[Record]
    favourRecords: list[Record]
