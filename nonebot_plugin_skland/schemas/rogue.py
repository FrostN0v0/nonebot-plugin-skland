from dataclasses import field, dataclass

from nonebot.compat import PYDANTIC_V2
from pydantic import HttpUrl, BaseModel, ConfigDict


@dataclass
class Topics:
    topic: str
    topic_id: str = field(init=False)

    _MAPPING = {"萨米": "rogue_3", "萨卡兹": "rogue_4"}

    def __post_init__(self):
        self.topic_id = self._MAPPING[self.topic]


class Dynamic(BaseModel):
    type: int
    url: HttpUrl
    videoId: str
    kind: int
    filename: str
    transcodeStatus: int


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
    favourRecords: list

    if PYDANTIC_V2:
        model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)
    else:

        class Config:
            extra = "allow"
            arbitrary_types_allowed = True
