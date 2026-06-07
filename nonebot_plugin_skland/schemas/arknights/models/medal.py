from pydantic import BaseModel


class MedalLayout(BaseModel):
    """
    蚀刻章布局

    Attributes:
        id (str): 奖章的唯一标识符
        pos (List[int]): 奖章的坐标位置,包含两个整数值(x, y)
    """

    id: str
    pos: list[int]


class Medal(BaseModel):
    """
    佩戴蚀刻章信息。

    Attributes:
        type (str): 佩戴蚀刻章类型，自定义或者套装
        template (str): 蚀刻章模板
        templateMedalList (List): 模板蚀刻章列表
        customMedalLayout (List[MedalLayout]): 蚀刻章的自定义布局
        total (int): 拥有的蚀刻章总数
    """

    type: str
    template: str
    templateMedalList: list[str]
    customMedalLayout: list[MedalLayout]
    total: int
