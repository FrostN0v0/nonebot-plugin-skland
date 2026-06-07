from pydantic import BaseModel


class PerChar(BaseModel):
    rarityRank: int
    charIdList: list[str]


class UpCharInfo(BaseModel):
    perCharList: list[PerChar]


class AvailCharInfo(BaseModel):
    perAvailList: list[PerChar]


class GachaDetailInfo(BaseModel):
    upCharInfo: UpCharInfo | None = None
    availCharInfo: AvailCharInfo | None = None
    """UP角色信息"""


class GachaDetail(BaseModel):
    detailInfo: GachaDetailInfo
    """卡池详情"""


class GachaDetails(BaseModel):
    """抽卡详情"""

    gachaPoolDetail: GachaDetail
    gachaPoolId: str


class CharTable(BaseModel):
    """角色信息表"""

    char_id: str = ""
    """角色ID"""
    name: str
    """角色名称"""
