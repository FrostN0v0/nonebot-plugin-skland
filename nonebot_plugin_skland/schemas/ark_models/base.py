from pydantic import BaseModel


class BaseCount(BaseModel):
    """
    获取/完成进度

    Attributes:
        current (int): 当前值。
        total (int): 总值/上限。
    """

    current: int
    total: int
