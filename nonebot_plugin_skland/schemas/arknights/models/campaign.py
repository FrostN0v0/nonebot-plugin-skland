from pydantic import BaseModel

from .base import BaseCount


class CampaignRecord(BaseModel):
    """
    剿灭记录

    Attributes:
        campaignId : 剿灭 ID
        maxKills : 最大击杀数
    """

    campaignId: str
    maxKills: int


class Campaign(BaseModel):
    """剿灭作战信息"""

    records: list[CampaignRecord]
    reward: BaseCount
