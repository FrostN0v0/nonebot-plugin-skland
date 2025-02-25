from dataclasses import field, dataclass

from nonebot.compat import PYDANTIC_V2
from pydantic import BaseModel, ConfigDict


@dataclass
class Topics:
    topic: str
    topic_id: str = field(init=False)

    _MAPPING = {"萨米": "rogue_3", "萨卡兹": "rogue_4"}

    def __post_init__(self):
        self.topic_id = self._MAPPING[self.topic]


class RougeHistory(BaseModel):
    # Not Finished
    if PYDANTIC_V2:
        model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)
    else:

        class Config:
            extra = "allow"
            arbitrary_types_allowed = True
