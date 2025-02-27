from pydantic import BaseModel

from .buildings import (
    Hire,
    Labor,
    Power,
    Control,
    Meeting,
    Trading,
    Training,
    Dormitory,
    Furniture,
    TiredChar,
    Manufacture,
)


class Building(BaseModel):
    """
    基建信息

    Attributes:
        tiredChars :  疲劳干员
        powers :  发电站
        manufactures :  制造站
        tradings :  交易站
        dormitories :  宿舍
        meeting :  会客室
        hire :  人力办公室
        training :  训练室
        labor :  无人机
        furniture :  家具
        control :  控制中枢
    """

    tiredChars: list[TiredChar]
    powers: list[Power]
    manufactures: list[Manufacture]
    tradings: list[Trading]
    dormitories: list[Dormitory]
    meeting: Meeting
    hire: Hire
    training: Training
    labor: Labor
    furniture: Furniture
    control: Control
