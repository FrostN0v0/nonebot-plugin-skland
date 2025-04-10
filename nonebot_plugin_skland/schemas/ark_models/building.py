from datetime import datetime

from pydantic import BaseModel

from .base import BaseCount
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
    manufacture_stoke: BaseCount | None = None

    @property
    def rested_chars(self):
        """此处未计算基建技能影响，因此实际休息进度可能有差异"""
        rested_count = 0
        for dorm in self.dormitories:
            for char in dorm.chars:
                ap_gain_rate = 1.5 + dorm.level * 0.1 + 0.0004 * dorm.comfort * 100
                time_diff = datetime.now().timestamp() - char.lastApAddTime
                ap_now = min(char.ap + time_diff * ap_gain_rate, 8640000)
                if ap_now == 8640000:
                    rested_count += 1
        return rested_count

    @property
    def dorm_chars(self):
        dorm_char_count = 0
        for dorm in self.dormitories:
            dorm_char_count += len(dorm.chars)
        return dorm_char_count

    @property
    def trading_stock(self):
        """获取交易站库存"""
        stock_count = 0
        for trading in self.tradings:
            if trading.completeWorkTime >= datetime.now().timestamp():
                stock_count += 1
            stock_count += len(trading.stock)
        return stock_count

    @property
    def trading_stock_limit(self):
        """获取交易站库存上限"""
        stock_limit = 0
        for trading in self.tradings:
            stock_limit += trading.stockLimit
        return stock_limit
