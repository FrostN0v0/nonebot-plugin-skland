"""抽卡统计和称号模型"""

from typing import Any, ClassVar
from collections.abc import Sequence

from pydantic import BaseModel
from nonebot.compat import model_validator

from .pool import GachaPool


class GachaTitleInfo(BaseModel):
    """抽卡称号信息"""

    title: str
    """称号名称"""
    six_star_rate: float
    """六星出货率（百分比）"""
    up_rate: float
    """UP率（百分比）"""
    total_score: float
    """综合得分（0-100）"""


class GroupedGachaRecord(BaseModel):
    """分组后的抽卡记录"""

    GACHA_RULE_TYPES: ClassVar[dict[str, list[int]]] = {"limit": [1, 2, 3, 8], "norm": [0, 5, 9], "doub": [4, 6, 7, 10]}

    pools: list[GachaPool]
    gacha_title: GachaTitleInfo | None = None
    """抽卡生涯评价称号"""

    @model_validator(mode="before")
    @classmethod
    def sort_pools(cls, values) -> Any:
        if "pools" in values:
            values["pools"] = sorted(values["pools"], key=lambda x: x.openTime, reverse=True)
        return values

    @model_validator(mode="after")
    @classmethod
    def calculate_gacha_title(cls, values) -> Any:
        """自动计算并填充抽卡称号"""
        if isinstance(values, dict):
            if values.get("gacha_title") is not None:
                return values
            return values
        else:
            if values.gacha_title is None:
                values.gacha_title = values.calculate_title()
            return values

    def _sum_by(self, attr: str, group: str) -> int:
        ids = self.GACHA_RULE_TYPES[group]
        return sum(getattr(pool, attr) for pool in self.pools if pool.gachaRuleType in ids)

    def _iter_pulls(self, group: str):
        ids = self.GACHA_RULE_TYPES[group]
        for pool in self.pools:
            if pool.gachaRuleType in ids:
                for grp in pool.records:
                    yield from grp.pulls

    def _pity(self, group: str) -> int:
        count = 0
        for pull in self._iter_pulls(group):
            if pull.rarity == 5:
                break
            count += 1
        return count

    @property
    def limit_total_pulls(self) -> int:
        return self._sum_by("total_pulls", "limit")

    @property
    def norm_total_pulls(self) -> int:
        return self._sum_by("total_pulls", "norm")

    @property
    def doub_total_pulls(self) -> int:
        return self._sum_by("total_pulls", "doub")

    @property
    def limit_pity(self) -> int:
        return self._pity("limit")

    @property
    def norm_pity(self) -> int:
        return self._pity("norm")

    @property
    def doub_pity(self) -> int:
        return self._pity("doub")

    @property
    def limit_total_six(self) -> int:
        return self._sum_by("total_six_stars", "limit")

    @property
    def norm_total_six(self) -> int:
        return self._sum_by("total_six_stars", "norm")

    @property
    def doub_total_six(self) -> int:
        return self._sum_by("total_six_stars", "doub")

    @property
    def limit_six_spook(self) -> int:
        return self._sum_by("total_six_spook", "limit")

    @property
    def norm_six_spook(self) -> int:
        return self._sum_by("total_six_spook", "norm")

    @property
    def doub_six_spook(self) -> int:
        return self._sum_by("total_six_spook", "doub")

    @property
    def limit_six_avg(self) -> float:
        total = self.limit_total_six
        return round(self._sum_by("bare_six_consume", "limit") / total, 1) if total else 0.0

    @property
    def norm_six_avg(self) -> float:
        total = self.norm_total_six
        return round(self._sum_by("bare_six_consume", "norm") / total, 1) if total else 0.0

    @property
    def doub_six_avg(self) -> float:
        total = self.doub_total_six
        return round(self._sum_by("bare_six_consume", "doub") / total, 1) if total else 0.0

    @property
    def total_pulls(self) -> int:
        """总抽卡次数"""
        return self.limit_total_pulls + self.norm_total_pulls + self.doub_total_pulls

    @property
    def total_six(self) -> int:
        """总六星数"""
        return self.limit_total_six + self.norm_total_six + self.doub_total_six

    @property
    def total_spook(self) -> int:
        """总歪卡数（不包含中坚）"""
        return self.limit_six_spook + self.norm_six_spook

    @property
    def non_doub_six(self) -> int:
        """除中坚外的六星数"""
        return self.limit_total_six + self.norm_total_six

    @property
    def six_star_rate(self) -> float:
        """六星出货率（百分比）"""
        if self.total_pulls == 0:
            return 0.0
        return round(self.total_six / self.total_pulls * 100, 1)

    @property
    def up_rate(self) -> float:
        """UP率（百分比）- 中坚卡池不参与计算"""
        if self.non_doub_six == 0:
            return 100.0  # 全是中坚卡池，默认100%
        return round((self.non_doub_six - self.total_spook) / self.non_doub_six * 100, 1)

    @staticmethod
    def _calculate_score(value: float, thresholds: Sequence[tuple[float, int]]) -> int:
        """根据阈值表计算得分"""
        return next((score for threshold, score in thresholds if value >= threshold), 0)

    def calculate_title(self) -> GachaTitleInfo:
        """
        计算抽卡生涯评价称号

        评分策略：
        1. 计算出货率得分（0-100）
        2. 计算UP率得分（0-100）
        3. 综合得分 = 出货率得分 * 0.7 + UP率得分 * 0.3
        4. 根据综合得分判定称号

        Returns:
            GachaTitleInfo: 称号信息
        """
        RATE_SCORES = [
            (4.5, 100),
            (4.0, 95),
            (3.5, 88),
            (3.2, 76),
            (3.0, 68),
            (2.8, 60),
            (2.6, 54),
            (2.4, 50),
            (2.2, 45),
            (2.0, 40),
            (1.8, 32),
            (1.5, 24),
            (1.2, 14),
            (0.0, 5),
        ]

        UP_SCORES = [
            (90, 100),
            (85, 95),
            (80, 88),
            (75, 80),
            (70, 70),
            (65, 60),
            (60, 50),
            (55, 40),
            (50, 30),
            (40, 20),
            (30, 10),
            (20, 5),
            (0, 0),
        ]
        TITLES = [
            (95, "绝世欧皇"),
            (80, "双层至尊欧皇"),
            (70, "传说级欧皇"),
            (56, "歪打正着的欧皇"),
            (48, "薛定谔的欧洲人"),
            (35, "脱欧入非"),
            (20, "面目全非"),
            (10, "非入骨髓"),
            (0, "绝世非酋"),
        ]

        six_star_rate = self.six_star_rate
        up_rate = self.up_rate

        total_score = round(
            self._calculate_score(six_star_rate, RATE_SCORES) * 0.7 + self._calculate_score(up_rate, UP_SCORES) * 0.3, 2
        )

        title = next(name for threshold, name in TITLES if total_score >= threshold)

        return GachaTitleInfo(title=title, six_star_rate=six_star_rate, up_rate=up_rate, total_score=total_score)
