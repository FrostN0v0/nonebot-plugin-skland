from dataclasses import field, dataclass

from pydantic import BaseModel

from .ark_models import Avatar
from .rogue_models import RogueCareer, RogueHistory


@dataclass
class Topics:
    topic: str
    topic_id: str = field(init=False)

    _MAPPING = {"傀影": "rogue_1", "水月": "rogue_2", "萨米": "rogue_3", "萨卡兹": "rogue_4"}

    def __post_init__(self):
        self.topic_id = self._MAPPING[self.topic]


class GameUserInfo(BaseModel):
    name: str
    level: int
    avatar: Avatar
    isOfficial: bool


class ItemInfo(BaseModel):
    name: str
    description: str
    usage: str


class CharInfo(BaseModel):
    skinId: str
    evolvePhase: int


class Topic(BaseModel):
    id: str
    isSelected: bool
    name: str
    pic: str


class RogueData(BaseModel):
    topics: list[Topic]
    history: RogueHistory
    gameUserInfo: GameUserInfo
    itemInfo: dict[str, ItemInfo]
    userCharInfo: dict[str, CharInfo]
    career: RogueCareer

    @property
    def topic(self) -> str:
        return next((topic.id for topic in self.topics if topic.isSelected), "None")

    @property
    def topic_img(self) -> str:
        return next((topic.pic for topic in self.topics if topic.isSelected), "None")
