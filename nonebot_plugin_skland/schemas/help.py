from typing import Any, Literal
from collections.abc import Mapping, Sequence

from pydantic import Field, BaseModel

HelpCategory = Literal["account", "arknights", "endfield", "interaction", "admin", "other"]
HelpVariant = Literal["overview", "detail", "roster"]

_SECTION_TITLES: dict[HelpCategory, tuple[str, str]] = {
    "account": ("账号与角色", "开始使用"),
    "arknights": ("明日方舟", "ARKNIGHTS"),
    "endfield": ("明日方舟：终末地", "ENDFIELD"),
    "interaction": ("图片交互", "探索更多"),
    "admin": ("管理工具", "仅超级用户"),
    "other": ("其他功能", "更多帮助"),
}


class HelpEntry(BaseModel):
    func: str
    category: HelpCategory
    command: str
    brief_des: str
    condition: str
    examples: tuple[str, ...]
    detail_des: str
    use_prefix: bool = True
    template: str | None = None

    def to_menu_data(self, prefix: str) -> dict[str, Any]:
        def command(value: str) -> str:
            return f"{prefix if self.use_prefix else ''}{value.replace('{prefix}', prefix)}"

        examples = "\n".join(command(example) for example in self.examples)
        detail = f"### 常用示例\n\n```text\n{examples}\n```\n\n{self.detail_des}"
        result: dict[str, Any] = {
            "func": self.func,
            "trigger_method": self.condition,
            "trigger_condition": f"`{command(self.command)}`",
            "brief_des": self.brief_des,
            "detail_des": detail,
            "pmn_hidden": self.category == "admin",
        }
        if self.template is not None:
            result["pmn_template"] = self.template
        return result


class HelpItem(BaseModel):
    index: int | None
    category: HelpCategory
    func: str
    trigger_method: str
    trigger_condition: str
    brief_des: str
    detail_des: str

    @property
    def category_title(self) -> str:
        return _SECTION_TITLES[self.category][0]

    @classmethod
    def from_menu(cls, data: Mapping[str, Any], *, index: int | None, category: HelpCategory) -> "HelpItem":
        return cls(
            index=index,
            category=category,
            func=data["func"],
            trigger_method=data["trigger_method"],
            trigger_condition=data["trigger_condition"],
            brief_des=data["brief_des"],
            detail_des=data["detail_des"],
        )


class HelpSection(BaseModel):
    category: HelpCategory
    title: str
    subtitle: str
    items: list[HelpItem]


class HelpView(BaseModel):
    name: str
    version: str | None
    plugin_index: int
    prefix: str
    markdown: bool
    showing_hidden: bool
    user_can_see_hidden: bool | None
    variant: HelpVariant
    sections: list[HelpSection] = Field(default_factory=list)
    function: HelpItem | None = None

    @property
    def help_command(self) -> str:
        hidden_option = " -H" if self.showing_hidden and self.user_can_see_hidden is not False else ""
        return f"{self.prefix}帮助{hidden_option} {self.name}"

    @property
    def function_count(self) -> int:
        return sum(len(section.items) for section in self.sections)

    @classmethod
    def from_menu(
        cls,
        *,
        name: str,
        version: str | None,
        info_index: int,
        prefix: str,
        markdown: bool,
        showing_hidden: bool,
        user_can_see_hidden: bool | None,
        categories: Mapping[str, HelpCategory],
        menu_data: Sequence[Mapping[str, Any]] = (),
        func_data: Mapping[str, Any] | None = None,
        func_index: int | None = None,
        roster: bool = False,
    ) -> "HelpView":
        sections: list[HelpSection] = []
        function: HelpItem | None = None
        if func_data is not None:
            function = HelpItem.from_menu(
                func_data,
                index=func_index + 1 if func_index is not None else None,
                category=categories.get(func_data["func"], "other"),
            )
        else:
            grouped: dict[HelpCategory, list[HelpItem]] = {}
            # 编号来自 PicMenu 当前可见列表，分组不能改变数字查询的目标。
            for index, data in enumerate(menu_data, 1):
                category = categories.get(data["func"], "other")
                grouped.setdefault(category, []).append(HelpItem.from_menu(data, index=index, category=category))
            sections = [
                HelpSection(category=category, title=title, subtitle=subtitle, items=grouped[category])
                for category, (title, subtitle) in _SECTION_TITLES.items()
                if category in grouped
            ]
        return cls(
            name=name,
            version=version,
            plugin_index=info_index + 1,
            prefix=prefix,
            markdown=markdown,
            showing_hidden=showing_hidden,
            user_can_see_hidden=user_can_see_hidden,
            variant="roster" if roster and function is not None else "detail" if function is not None else "overview",
            sections=sections,
            function=function,
        )
