"""Build Endfield item icons from official website and Wiki data."""

import re
from urllib.parse import urljoin
from html.parser import HTMLParser
from collections.abc import Iterable

from pydantic import BaseModel

from .gacha.base import EfGachaContentPool

_AVATAR_RULE = re.compile(r"([^{}]*__02-Operator_image__[^{}]*)\{([^{}]*)\}")
_DATA_KEY = re.compile(r"\[data-key=([\"']?)([^\]\"']+)\1\]")
_BACKGROUND_URL = re.compile(r"background-image\s*:\s*url\(\s*([\"']?)(.*?)\1\s*\)")


class _OperatorPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stylesheets: list[str] = []
        self.characters: dict[str, set[str]] = {}
        self._div_depth = 0
        self._card_depth = 0
        self._key = ""
        self._name: list[str] = []
        self._name_tag: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if tag == "link" and "stylesheet" in (attributes.get("rel") or "").split():
            if href := attributes.get("href"):
                self.stylesheets.append(href)
        if tag == "div":
            self._div_depth += 1
            if any(value.startswith("OperatorItem_operatorItem__") for value in classes):
                self._card_depth = self._div_depth
                self._key = ""
                self._name = []
        if not self._card_depth:
            return
        if any(value.startswith("OperatorItem_image__") for value in classes):
            self._key = attributes.get("data-key") or ""
        if any(value.startswith("OperatorItem_nameText__") for value in classes):
            self._name_tag = tag

    def handle_endtag(self, tag: str) -> None:
        if tag == self._name_tag:
            self._name_tag = None
        if tag == "div":
            if self._card_depth and self._div_depth == self._card_depth:
                name = "".join(self._name).strip()
                if name and self._key:
                    self.characters.setdefault(name, set()).add(self._key)
                self._card_depth = 0
            self._div_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._name_tag is not None:
            self._name.append(data)


class EfOperatorIconPage(BaseModel):
    characters: dict[str, set[str]]
    stylesheets: tuple[str, ...]

    @classmethod
    def from_html(cls, html: str, base_url: str) -> "EfOperatorIconPage":
        parser = _OperatorPageParser()
        parser.feed(html)
        if not parser.characters or not parser.stylesheets:
            raise ValueError("官网角色列表或样式表缺失")
        return cls(
            characters=parser.characters,
            stylesheets=tuple(dict.fromkeys(urljoin(base_url, href) for href in parser.stylesheets)),
        )


class _WikiBrief(BaseModel):
    cover: str


class _WikiItem(BaseModel):
    name: str
    brief: _WikiBrief


class _WikiSubtype(BaseModel):
    id: str
    items: list[_WikiItem]


class _WikiCategory(BaseModel):
    id: str
    typeSub: list[_WikiSubtype]


class EfWikiWeaponCatalog(BaseModel):
    catalog: list[_WikiCategory]

    def icons_by_name(self) -> dict[str, set[str]]:
        result: dict[str, set[str]] = {}
        for category in self.catalog:
            if category.id != "1":
                continue
            for subtype in category.typeSub:
                if subtype.id != "2":
                    continue
                for item in subtype.items:
                    name = item.name.strip()
                    result.setdefault(name, set()).add(item.brief.cover)
        if not result:
            raise ValueError("官方武器目录为空")
        return result


def build_ef_item_icons(
    pools: Iterable[EfGachaContentPool],
    operators: EfOperatorIconPage,
    stylesheets: Iterable[str],
    weapons: EfWikiWeaponCatalog,
) -> dict[str, str]:
    avatars: dict[str, str] = {}
    for css in stylesheets:
        for selector, declarations in _AVATAR_RULE.findall(css):
            key_match = _DATA_KEY.search(selector)
            url_match = _BACKGROUND_URL.search(declarations)
            if key_match is None or url_match is None:
                continue
            key, url = key_match[2].strip(), url_match[2].strip()
            if key in avatars and avatars[key] != url:
                raise ValueError(f"官网角色头像不唯一：{key}")
            avatars[key] = url
    weapon_icons = weapons.icons_by_name()
    item_names: dict[str, set[str]] = {}
    for pool in pools:
        for item in pool.all:
            # Historical pools can retain an older name for the same game item ID.
            item_names.setdefault(item.id, set()).add(item.name.strip())
    if not item_names:
        raise ValueError("卡池物品目录为空")
    result: dict[str, str] = {}
    for item_id, names in item_names.items():
        if item_id.startswith("chr_"):
            matches = {avatars[key] for name in names for key in operators.characters.get(name, ()) if key in avatars}
        elif item_id.startswith("wpn_"):
            matches = {url for name in names for url in weapon_icons.get(name, ())}
        else:
            raise ValueError(f"未知终末地物品 ID：{item_id}")
        if len(matches) != 1:
            raise ValueError(f"官方物品图标缺失或不唯一：{item_id}")
        result[item_id] = matches.pop()
    return result
