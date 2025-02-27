from pydantic import BaseModel

from .base import BaseCount


class TowerRecord(BaseModel):
    """
    保全派驻记录

    Attributes:
        towerId : 保全派驻 ID
        best : 最高进度
    """

    towerId: str
    best: int


class TowerReward(BaseModel):
    """保全派驻奖励进度"""

    higherItem: BaseCount
    lowerItem: BaseCount
    termTs: int


class Tower(BaseModel):
    """保全派驻信息"""

    records: list[TowerRecord]
    reward: TowerReward
