from pydantic import BaseModel


class Recruit(BaseModel):
    """
    公招信息

    Attributes:
        startTs : 开始时间戳
        finishTs : 结束时间戳
        state : 状态
    """

    startTs: int
    finishTs: int
    state: int
