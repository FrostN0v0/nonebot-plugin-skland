from pydantic import BaseModel

from .base import BaseCount


class Routine(BaseModel):
    """
    日/周常任务完成进度

    Attributes:
        daily : 日常任务进度
        weekly : 周常任务进度
    """

    daily: BaseCount
    weekly: BaseCount
