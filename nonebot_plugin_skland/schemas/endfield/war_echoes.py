from __future__ import annotations

from time import time

from pydantic import Field, BaseModel

from .card import KeyValuePair


def _rating(stars: int, all_plus_tasks: bool) -> str:
    normalized = max(0, min(round(stars), 9))
    if normalized == 9 and all_plus_tasks:
        return "S+"
    if normalized == 9:
        return "S"
    if normalized >= 7:
        return "A"
    if normalized >= 5:
        return "B"
    if normalized >= 3:
        return "C"
    if normalized >= 1:
        return "D"
    return "--"


def _timestamp(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


class WarEchoesEnemy(BaseModel):
    id: str = ""
    name: str = ""
    desc: str = ""
    level: int = 0
    imageUrl: str = ""
    ability: str = ""


class WarEchoesCharacter(BaseModel):
    charId: str = ""
    level: int = 0
    potentialLevel: int = 0
    avatarUrl: str = ""
    property: KeyValuePair = Field(default_factory=KeyValuePair)
    rarity: KeyValuePair = Field(default_factory=KeyValuePair)
    evolvePhase: int = 0


class WarEchoesBestRecord(BaseModel):
    chars: list[WarEchoesCharacter] = Field(default_factory=list)
    ts: str = ""
    passTs: str = ""


class WarEchoesDungeon(BaseModel):
    id: str = ""
    isPass: bool = False
    firstPassTs: str = ""
    bestRecord: WarEchoesBestRecord | None = None
    name: str = ""
    desc: str = ""
    feature: str = ""
    enemies: list[WarEchoesEnemy] = Field(default_factory=list)
    recommendLevel: int = 0
    plusTask: bool = False
    additionalChallengeTarget: str = ""


class WarEchoesDungeonGroup(BaseModel):
    star: int = 0
    plusTask: bool = False
    name: str = ""
    normalDungeon: WarEchoesDungeon = Field(default_factory=WarEchoesDungeon)
    hardDungeon: WarEchoesDungeon = Field(default_factory=WarEchoesDungeon)
    cruelDungeon: WarEchoesDungeon = Field(default_factory=WarEchoesDungeon)

    @property
    def selected_dungeon(self) -> WarEchoesDungeon | None:
        return next(
            (dungeon for dungeon in (self.cruelDungeon, self.hardDungeon, self.normalDungeon) if dungeon.isPass),
            None,
        )


class WarEchoesWeek(BaseModel):
    id: str = ""
    name: str = ""
    startTs: str = ""
    endTs: str = ""
    stars: int = 0
    allPlusTasks: bool = False
    dungeonGroups: list[WarEchoesDungeonGroup] = Field(default_factory=list)

    @property
    def rating(self) -> str:
        return _rating(self.stars, self.allPlusTasks)


class WarEchoesSeason(BaseModel):
    id: str = ""
    name: str = ""
    kvImage: str = ""
    headerImage: str = ""
    startTs: str = ""
    endTs: str = ""
    stars: int = 0
    allPlusTasks: bool = False
    weeks: list[WarEchoesWeek] = Field(default_factory=list)

    @property
    def rating(self) -> str:
        return _rating(self.stars, self.allPlusTasks)

    def select_week(self, week_id: str | int | None = None, *, now: float | None = None) -> WarEchoesWeek:
        if not self.weeks:
            raise ValueError(f"战争回响赛季「{self.name or self.id}」暂无轮换数据")
        if week_id is not None:
            selected = next((week for week in self.weeks if week.id == str(week_id)), None)
            if selected is None:
                options = "、".join(f"{week.id}:{week.name}" for week in self.weeks)
                raise ValueError(f"未找到战争回响轮换 {week_id},可选轮换: {options}")
            return selected

        current = time() if now is None else now
        ordered = sorted(self.weeks, key=lambda week: _timestamp(week.startTs))
        active = next(
            (week for week in ordered if _timestamp(week.startTs) <= current <= _timestamp(week.endTs)),
            None,
        )
        if active is not None:
            return active
        return ordered[0] if current < _timestamp(ordered[0].startTs) else ordered[-1]


class WarEchoesAchievement(BaseModel):
    name: str = ""
    star: int = 0
    firstPassTs: str = ""


class WarEchoesActivity(BaseModel):
    name: str = ""


class WarEchoes(BaseModel):
    seasons: list[WarEchoesSeason] = Field(default_factory=list)
    achieves: list[WarEchoesAchievement] = Field(default_factory=list)
    activity: WarEchoesActivity = Field(default_factory=WarEchoesActivity)

    def select_season(self, season_id: str | int | None = None, *, now: float | None = None) -> WarEchoesSeason:
        if not self.seasons:
            raise ValueError("暂无战争回响赛季数据")
        if season_id is not None:
            selected = next((season for season in self.seasons if season.id == str(season_id)), None)
            if selected is None:
                options = "、".join(f"{season.id}:{season.name}" for season in self.seasons)
                raise ValueError(f"未找到战争回响赛季 {season_id},可选赛季: {options}")
            return selected

        current = time() if now is None else now
        ordered = sorted(self.seasons, key=lambda season: _timestamp(season.startTs))
        active = next(
            (season for season in ordered if _timestamp(season.startTs) <= current <= _timestamp(season.endTs)),
            None,
        )
        if active is not None:
            return active
        return ordered[0] if current < _timestamp(ordered[0].startTs) else ordered[-1]


class WarEchoesHonorSummary(BaseModel):
    gold: int = 0
    silver: int = 0
    bronze: int = 0

    @classmethod
    def from_achievements(cls, achievements: list[WarEchoesAchievement]) -> WarEchoesHonorSummary:
        tiers = {"gold": 0, "silver": 0, "bronze": 0}
        for achievement in achievements:
            if _timestamp(achievement.firstPassTs) <= 0:
                continue
            tier = "gold" if achievement.star == 3 else "silver" if achievement.star == 2 else "bronze"
            tiers[tier] += 1
        return cls(
            gold=tiers["gold"],
            silver=tiers["silver"] + tiers["gold"],
            bronze=tiers["bronze"] + tiers["silver"] + tiers["gold"],
        )


class WarEchoesView(BaseModel):
    season: WarEchoesSeason
    week: WarEchoesWeek
    honor: WarEchoesHonorSummary

    @classmethod
    def from_data(
        cls,
        data: WarEchoes,
        *,
        season_id: str | int | None = None,
        week_id: str | int | None = None,
        now: float | None = None,
    ) -> WarEchoesView:
        season = data.select_season(season_id, now=now)
        return cls(
            season=season,
            week=season.select_week(week_id, now=now),
            honor=WarEchoesHonorSummary.from_achievements(data.achieves),
        )
