from __future__ import annotations

import re
from html import unescape
from bisect import bisect_right

from pydantic import Field, BaseModel
from nonebot.compat import model_dump

from .models.status import Avatar
from ...filters import ark_enemy_icon_url, garrison_asset_url, charId_to_portraitUrl

_OFFICIAL_TAG = re.compile(r"<@[^>]*>|</>|</?(?:color|size|font|sprite)(?:=[^>]*)?>", re.IGNORECASE)
_TAG = re.compile(r"<([^<>]*)>")
_HTML_TAG = re.compile(r"/?(?:a|b|br|div|em|i|img|p|s|span|strong|u|script|style)(?:\s.*|/)?$", re.IGNORECASE)
_TITLE_PIC_ID = re.compile(r"comment_icon_[1-6](?:_[0-2])?")

_BOSS_NAMES = {
    "enemy_1521_dslily": "盐风主教昆图斯",
    "enemy_1559_vtlionk": "阿利斯泰尔，帝国余晖",
    "enemy_2054_smdeer": "“萨米的意志”",
    "enemy_2124_dyjsfg": "矩兽",
    "enemy_9013_acstmk": "假想敌：胄",
    "enemy_9013_acstmk_2": "假想敌：胄",
    "enemy_9017_achunt": "假想敌：铳",
    "enemy_9017_achunt_2": "假想敌：铳",
    "enemy_9021_acduml": "假想敌：管",
    "enemy_9021_acduml_2": "假想敌：管",
    "enemy_9029_acfnc": "假想敌：械",
    "enemy_9035_acspider": "假想敌：茧",
    "enemy_9037_aceel": "假想敌：鳍",
}


def _text(value: str) -> str:
    """Turn official rich text into plain text, retaining semantic angle-bracket labels."""
    value = _OFFICIAL_TAG.sub("", unescape(value).replace("\\n", "\n"))
    value = _TAG.sub(lambda match: "" if _HTML_TAG.fullmatch(match[1]) else match[1], value)
    return value.replace("<", "〈").replace(">", "〉").strip()


def _number(value: int | None) -> str:
    return "未知" if value is None else str(value)


def _title_icon_url(pic_id: str) -> str:
    return garrison_asset_url(f"titles/{pic_id}.png") if _TITLE_PIC_ID.fullmatch(pic_id) else ""


def _difficulty_background_url(difficulty: str) -> str:
    if difficulty not in {"FUNNY", "NORMAL", "HARD", "ABYSS", "FAST", "TRAINING"}:
        return ""
    return garrison_asset_url(f"modes/img_title_mode_{difficulty.lower()}.png")


class GarrisonProgress(BaseModel):
    current: int | None = None
    count: int | None = None


class GarrisonVersion(BaseModel):
    versionId: str = ""
    activityId: str = ""
    seasonName: str = ""
    startTime: int = 0
    endTime: int = 0


class GarrisonBandInfo(BaseModel):
    id: str = ""
    name: str = ""
    effectName: str = ""
    desc: str = ""
    totalHp: int = 0
    icon: str = ""


class GarrisonBondInfo(BaseModel):
    id: str = ""
    name: str = ""
    desc: str = ""
    activeCount: int = 0
    type: str = ""
    icon: str = ""


class GarrisonEquipInfo(BaseModel):
    id: str = ""
    name: str = ""
    desc: str = ""
    icon: str = ""
    skillId: str = ""
    isUpgraded: bool = False
    itemType: str = ""
    itemLevel: int = 0


class GarrisonChessInfo(BaseModel):
    id: str = ""
    goldenChessId: str = ""
    chessLevel: int = 0
    charId: str = ""
    charName: str = ""
    charLevel: int = 0
    evolvePhase: int = 0
    garrisonIds: list[str] = Field(default_factory=list)
    bondIds: list[str] = Field(default_factory=list)
    chessType: int = 0
    charProfession: str = ""
    charSubProfession: str = ""


class GarrisonAbilityInfo(BaseModel):
    id: str = ""
    description: str = ""
    eventTypeDesc: str = ""
    eventTypeIcon: str = ""
    eventTypeSmallIcon: str = ""
    icon: str = ""


class GarrisonTitleInfo(BaseModel):
    id: str = ""
    name: str = ""
    picId: str = ""


class GarrisonBossInfo(BaseModel):
    id: str = ""
    enemyId: str = ""
    handbookEnemyId: str = ""


class GarrisonResource(BaseModel):
    versionInfo: GarrisonVersion = Field(default_factory=GarrisonVersion)
    bandInfo: dict[str, GarrisonBandInfo] = Field(default_factory=dict)
    bondInfo: dict[str, GarrisonBondInfo] = Field(default_factory=dict)
    equipInfo: dict[str, GarrisonEquipInfo] = Field(default_factory=dict)
    chessInfo: dict[str, GarrisonChessInfo] = Field(default_factory=dict)
    garrisonInfo: dict[str, GarrisonAbilityInfo] = Field(default_factory=dict)
    titleInfo: dict[str, GarrisonTitleInfo] = Field(default_factory=dict)
    bossInfo: dict[str, GarrisonBossInfo] = Field(default_factory=dict)


class GarrisonResources(BaseModel):
    resources: list[GarrisonResource]
    guidePublishUrl: str = ""
    guideTagUrl: str = ""

    @property
    def current_activity_id(self) -> str:
        if not self.resources or not self.resources[0].versionInfo.activityId.strip():
            raise ValueError("卫戍协议资源未提供有效的当前活动")
        return self.resources[0].versionInfo.activityId

    def current_resource(self, activity_id: str | None = None) -> GarrisonResource:
        current_id = self.current_activity_id
        current = self.resources[0]
        if not current.versionInfo.versionId.strip():
            raise ValueError("卫戍协议资源未提供有效的当前版本")
        if activity_id is None or activity_id == current_id:
            return current
        for resource in self.resources:
            if resource.versionInfo.activityId == activity_id and resource.versionInfo.versionId.strip():
                return resource
        raise ValueError(f"卫戍协议资源未提供活动 {_text(activity_id)}")

    def for_version(self, version_id: str, activity_id: str = "") -> GarrisonResource | None:
        if not version_id:
            return None
        return next(
            (
                resource
                for resource in self.resources
                if resource.versionInfo.versionId == version_id
                and (not activity_id or resource.versionInfo.activityId == activity_id)
            ),
            None,
        )


class GarrisonEquipment(BaseModel):
    equipId: str = ""


class GarrisonChess(BaseModel):
    chessId: str = ""
    charId: str = ""
    chessInfo: GarrisonChessInfo | None = None
    equips: list[GarrisonEquipment] = Field(default_factory=list)
    moduleId: str = ""
    skillId: str = ""
    mergeLevel: int = 0


class GarrisonRecordBond(BaseModel):
    bondId: str = ""
    layer: int = 0
    activate: int = 0


class GarrisonRecordBoss(BaseModel):
    bossId: str = ""
    isHidden: bool = False
    isKilled: bool = False


class GarrisonRecord(BaseModel):
    id: str
    completeState: int = 0
    teamComplete: int = 0
    trophyBefore: int = 0
    trophyAfter: int = 0
    coinCost: int = 0
    syncCnt: int = 0
    killCnt: int = 0
    bandId: str = ""
    title: str = ""
    bondInfo: list[GarrisonRecordBond] = Field(default_factory=list)
    chessSquad: list[GarrisonChess] = Field(default_factory=list)
    passRound: int = 0
    acBossInfo: list[GarrisonRecordBoss] = Field(default_factory=list)
    gameStartTs: int = 0
    gameEndTs: int = 0
    modeType: str = ""
    modeDifficulty: str = ""
    mode: str = ""
    events: list[str] = Field(default_factory=list)
    versionId: str = ""
    activityId: str = ""


class GarrisonHistory(BaseModel):
    records: list[GarrisonRecord] = Field(default_factory=list)
    favourRecords: list[GarrisonRecord] = Field(default_factory=list)


class GarrisonCareerTitle(GarrisonTitleInfo):
    count: int | None = None
    type: str = ""


class GarrisonBandBadge(BaseModel):
    id: str = ""
    masterVictor: bool = False


class GarrisonCareer(BaseModel):
    medal: GarrisonProgress = Field(default_factory=GarrisonProgress)
    bp: GarrisonProgress = Field(default_factory=GarrisonProgress)
    bpPercent: int | None = None
    mode: str = ""
    modeDifficulty: str = ""
    totalMultiBattleCnt: int | None = None
    totalMultiBattleWinCnt: int | None = None
    totalMultiBattleHardWinCnt: int | None = None
    totalSingleBattleCnt: int | None = None
    totalSingleBattleWinCnt: int | None = None
    totalSingleBattleHardWinCnt: int | None = None
    totalTrophyCnt: int | None = None
    totalBeLikeCnt: int | None = None
    top1ActivateBondId: str = ""
    top2ActivateBondId: str = ""
    top3ActivateBondId: str = ""
    top1BandUseId: str = ""
    top1BandUseCnt: int | None = None
    top2BandUseId: str = ""
    top2BandUseCnt: int | None = None
    top3BandUseId: str = ""
    top3BandUseCnt: int | None = None
    titleCntInfo: dict[str, int] = Field(default_factory=dict)
    titleTypeCnt: dict[str, int] = Field(default_factory=dict)
    specialBandIds: list[str] = Field(default_factory=list)
    bandBadges: list[GarrisonBandBadge] = Field(default_factory=list)
    normalTitles: list[GarrisonCareerTitle] = Field(default_factory=list)
    specialTitles: list[GarrisonCareerTitle] = Field(default_factory=list)


class GarrisonPlayer(BaseModel):
    name: str = ""
    level: int = 0
    avatar: Avatar | None = None
    isOfficial: bool = False
    registerTs: int = 0


class GarrisonData(BaseModel):
    currentTs: int = 0
    history: GarrisonHistory
    career: GarrisonCareer = Field(default_factory=GarrisonCareer)
    gameUserInfo: GarrisonPlayer = Field(default_factory=GarrisonPlayer)


class GarrisonMetric(BaseModel):
    label: str
    value: str
    detail: str = ""
    secondary_label: str = ""
    secondary_value: str = ""
    icon_url: str = ""
    background_url: str = ""


class GarrisonMode(BaseModel):
    label: str
    total: int
    wins: int
    losses: int
    win_percent: float | None


class GarrisonItem(BaseModel):
    id: str = ""
    name: str
    icon_url: str = ""
    description: str = ""
    count: int | None = None
    badge: str = ""
    badge_icon_url: str = ""


class GarrisonStrategyStat(GarrisonItem):
    recent_count: int
    recent_wins: int

    @property
    def win_percent(self) -> float | None:
        return 100 * self.recent_wins / self.recent_count if self.recent_count else None


class GarrisonBondStat(GarrisonItem):
    recent_count: int
    max_layer: int | None


class GarrisonTitleDimension(BaseModel):
    key: str
    label: str
    count: int | None
    icon_url: str


class GarrisonBoss(BaseModel):
    id: str
    name: str
    icon_url: str = ""
    is_hidden: bool
    is_killed: bool

    @property
    def status_label(self) -> str:
        kind = "隐秘核心" if self.is_hidden else "领袖"
        return f"{kind} · {'已击败' if self.is_killed else '未击败'}"


class GarrisonOperator(BaseModel):
    char_id: str
    name: str
    tier: int
    rank_label: str
    level: int
    elite_phase: int
    skill_id: str
    module_id: str
    equipment: list[GarrisonItem] = Field(default_factory=list)
    abilities: list[GarrisonItem] = Field(default_factory=list)

    @property
    def half_portrait_url(self) -> str:
        return charId_to_portraitUrl(self.char_id) if self.char_id else ""

    @property
    def tier_icon_url(self) -> str:
        return garrison_asset_url(f"tiers/chess_level_icon_{self.tier}.png") if 1 <= self.tier <= 6 else ""


class GarrisonRecordView(BaseModel):
    index: int
    record_id: str
    version_id: str
    activity_id: str
    result_label: str
    success: bool
    is_favored: bool
    mode_label: str
    difficulty_label: str
    difficulty_background_url: str = ""
    rounds: int
    started_at: int = 0
    ended_at: int
    duration_label: str
    trophy_before: int
    trophy_after: int
    trophy_change: int
    coin_cost: int
    kill_count: int
    strategy: GarrisonItem
    title: str
    title_icon_url: str = ""
    operators: list[GarrisonOperator] = Field(default_factory=list)
    bonds: list[GarrisonItem] = Field(default_factory=list)
    bosses: list[GarrisonBoss] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)

    @property
    def trophy_icon_url(self) -> str:
        level = bisect_right((10, 30, 60, 100, 150, 200, 300), self.trophy_after) + 1
        return garrison_asset_url(f"trophies/trophy_level{level}_icon.png")


def _band_item(
    resource: GarrisonResource | None,
    band_id: str,
    *,
    badge: GarrisonBandBadge | None = None,
) -> GarrisonItem:
    meta = resource.bandInfo.get(band_id) if resource else None
    return GarrisonItem(
        id=_text(band_id),
        name=_text((meta.name or meta.effectName or band_id) if meta else band_id) or "未提供策略",
        icon_url=meta.icon if meta else "",
        description=_text(meta.desc) if meta else "",
        badge=("大师标识" if badge.masterVictor else "胜利标识") if badge else "",
        badge_icon_url=(
            garrison_asset_url(f"title_team_logo_{'master' if badge.masterVictor else 'victor'}.png") if badge else ""
        ),
    )


def _bond_item(resource: GarrisonResource | None, bond_id: str, *, count: int | None = None) -> GarrisonItem:
    meta = resource.bondInfo.get(bond_id) if resource else None
    return GarrisonItem(
        id=_text(bond_id),
        name=_text(meta.name or bond_id) if meta else _text(bond_id),
        icon_url=meta.icon if meta else "",
        description=_text(meta.desc) if meta else "",
        count=count,
    )


def _operator(chess: GarrisonChess, resource: GarrisonResource | None) -> GarrisonOperator:
    meta = resource.chessInfo.get(chess.chessId) if resource else None
    info = chess.chessInfo or meta
    char_id = chess.charId or (info.charId if info else "") or (meta.charId if meta else "")
    equipment = []
    for equip in chess.equips:
        item = resource.equipInfo.get(equip.equipId) if resource else None
        equipment.append(
            GarrisonItem(
                id=_text(equip.equipId),
                name=_text(item.name or equip.equipId) if item else _text(equip.equipId),
                icon_url=item.icon if item else "",
                description=_text(item.desc) if item else "",
                badge="升级" if item and item.isUpgraded else "",
            )
        )
    abilities = []
    for ability_id in info.garrisonIds if info else []:
        ability = resource.garrisonInfo.get(ability_id) if resource else None
        abilities.append(
            GarrisonItem(
                id=_text(ability_id),
                name=_text(ability.eventTypeDesc or ability_id) if ability else _text(ability_id),
                icon_url=(ability.icon or ability.eventTypeIcon) if ability else "",
                description=_text(ability.description) if ability else "",
            )
        )
    golden = bool(info and info.id and info.id == info.goldenChessId)
    return GarrisonOperator(
        char_id=_text(char_id),
        name=_text((info.charName if info else "") or (meta.charName if meta else "") or char_id or chess.chessId)
        or "未知干员",
        tier=info.chessLevel if info else 0,
        rank_label="精锐" if golden else "普通" if info and info.id and info.goldenChessId else "未知",
        level=info.charLevel if info else 0,
        elite_phase=info.evolvePhase if info else 0,
        skill_id=_text(chess.skillId),
        module_id=_text(chess.moduleId),
        equipment=equipment,
        abilities=abilities,
    )


def _record_view(
    record: GarrisonRecord,
    resources: GarrisonResources,
    *,
    index: int,
    is_favored: bool,
    band_badge: GarrisonBandBadge | None,
) -> GarrisonRecordView:
    resource = resources.for_version(record.versionId, record.activityId)
    strategy = _band_item(resource, record.bandId, badge=band_badge)
    title = resource.titleInfo.get(record.title) if resource and record.title else None
    bonds = []
    for bond in sorted(record.bondInfo, key=lambda item: item.layer, reverse=True):
        item = _bond_item(resource, bond.bondId, count=bond.layer)
        item.badge = "已激活" if bond.activate else "未激活"
        bonds.append(item)
    bosses = []
    for boss in record.acBossInfo:
        meta = resource.bossInfo.get(boss.bossId) if resource else None
        enemy_id = _text((meta.handbookEnemyId or meta.enemyId) if meta else "")
        bosses.append(
            GarrisonBoss(
                id=_text(boss.bossId),
                name=_BOSS_NAMES.get(enemy_id, enemy_id or _text(boss.bossId)),
                icon_url=ark_enemy_icon_url(enemy_id) if enemy_id else "",
                is_hidden=boss.isHidden,
                is_killed=boss.isKilled,
            )
        )
    duration = "未提供"
    if record.gameStartTs > 0 and record.gameEndTs >= record.gameStartTs:
        minutes, seconds = divmod(record.gameEndTs - record.gameStartTs, 60)
        hours, minutes = divmod(minutes, 60)
        duration = f"{hours}时{minutes}分{seconds}秒" if hours else f"{minutes}分{seconds}秒"
    # Official record cards and detail Info.isWin both use completeState, including MULTI.
    success = record.completeState == 1
    operators = [_operator(chess, resource) for chess in record.chessSquad]
    operators.sort(key=lambda item: (-item.tier, -item.elite_phase, -item.level))
    return GarrisonRecordView(
        index=index,
        record_id=_text(record.id),
        version_id=_text(record.versionId),
        activity_id=_text(record.activityId),
        result_label="模拟完成" if success else "模拟中断",
        success=success,
        is_favored=is_favored,
        mode_label={"SINGLE": "独立", "MULTI": "联合", "LOCAL": "教学模拟"}.get(
            record.modeType, _text(record.modeType)
        ),
        difficulty_label=_text(record.mode or record.modeDifficulty) or "未提供难度",
        difficulty_background_url=_difficulty_background_url(record.modeDifficulty),
        rounds=record.passRound,
        started_at=record.gameStartTs,
        ended_at=record.gameEndTs,
        duration_label=duration,
        trophy_before=record.trophyBefore,
        trophy_after=record.trophyAfter,
        trophy_change=record.trophyAfter - record.trophyBefore,
        coin_cost=record.coinCost,
        kill_count=record.killCnt,
        strategy=strategy,
        title=_text(title.name or record.title) if title else _text(record.title),
        title_icon_url=_title_icon_url(title.picId) if title else "",
        operators=operators,
        bonds=bonds,
        bosses=bosses,
        events=[_text(event) for event in record.events],
    )


class GarrisonView(BaseModel):
    nickname: str
    uid: str
    server_name: str
    level: int
    avatar_url: str
    season_name: str
    activity_id: str
    version_id: str
    background_url: str = ""
    is_detail: bool
    favored: bool
    records: list[GarrisonRecordView] = Field(default_factory=list)
    metrics: list[GarrisonMetric] = Field(default_factory=list)
    modes: list[GarrisonMode] = Field(default_factory=list)
    recent_count: int = 0
    recent_scope: str = "暂无战绩记录"
    strategies: list[GarrisonStrategyStat] = Field(default_factory=list)
    bonds: list[GarrisonBondStat] = Field(default_factory=list)
    normal_titles: list[GarrisonItem] = Field(default_factory=list)
    special_titles: list[GarrisonItem] = Field(default_factory=list)
    other_titles: list[GarrisonItem] = Field(default_factory=list)
    title_dimensions: list[GarrisonTitleDimension] = Field(default_factory=list)
    title_scale: int = Field(default=1, ge=1)
    title_radar_complete: bool = False

    @classmethod
    def from_data(
        cls,
        data: GarrisonData,
        resources: GarrisonResources,
        *,
        uid: str,
        server_name: str = "",
        channel_master_id: str = "",
        activity_id: str | None = None,
        record_index: int | None = None,
        favored: bool = False,
    ) -> GarrisonView:
        resource = resources.current_resource(activity_id)
        selected = data.history.favourRecords if favored else data.history.records
        # Preserve API ordering, including ties; history and favorite indices are independent.
        if record_index is not None and not 1 <= record_index <= len(selected):
            label = "收藏战绩" if favored else "战绩记录"
            raise ValueError(f"{label}编号超出范围：共 {len(selected)} 条，请选择 1..{len(selected)} 中的编号")
        favorites = {record.id for record in data.history.favourRecords}
        indexed = enumerate(selected, 1) if record_index is None else [(record_index, selected[record_index - 1])]
        career = data.career
        badges = {badge.id: badge for badge in career.bandBadges}
        # Preferences use this activity's unique records, never the selected list.
        recent_records: dict[str, GarrisonRecord] = {}
        for record in data.history.records:
            if record.activityId == resource.versionInfo.activityId and record.id not in recent_records:
                recent_records[record.id] = record
        recent_count = len(recent_records)
        recent_scope = f"共{recent_count}场记录" if recent_count else "暂无战绩记录"
        recent_bands: dict[str, tuple[int, int]] = {}
        recent_bonds: dict[str, tuple[int, int]] = {}
        boss_kills = 0
        hidden_boss_kills = 0
        recent_duration: int | None = 0 if recent_count else None
        for record in recent_records.values():
            if record.bandId.strip():
                count, wins = recent_bands.get(record.bandId, (0, 0))
                recent_bands[record.bandId] = (count + 1, wins + (record.completeState == 1))
            activated_bonds: dict[str, int] = {}
            for bond in record.bondInfo:
                if bond.activate and bond.bondId.strip():
                    activated_bonds[bond.bondId] = max(activated_bonds.get(bond.bondId, bond.layer), bond.layer)
            for bond_id, layer in activated_bonds.items():
                count, max_layer = recent_bonds.get(bond_id, (0, layer))
                recent_bonds[bond_id] = (count + 1, max(max_layer, layer))
            for boss in record.acBossInfo:
                if boss.isKilled:
                    boss_kills += 1
                    hidden_boss_kills += boss.isHidden
            if record.gameStartTs <= 0 or record.gameEndTs < record.gameStartTs:
                recent_duration = None
            elif recent_duration is not None:
                recent_duration += record.gameEndTs - record.gameStartTs
        duration_label = "未知"
        if recent_duration is not None:
            hours, minutes = divmod(recent_duration // 60, 60)
            duration_label = f"{hours}时{minutes}分" if hours else f"{minutes}分"
        records = [
            _record_view(
                record,
                resources,
                index=index,
                is_favored=favored or record.id in favorites,
                band_badge=badges.get(record.bandId) if record.activityId == resource.versionInfo.activityId else None,
            )
            for index, record in indexed
        ]
        single_total, multi_total = career.totalSingleBattleCnt, career.totalMultiBattleCnt
        total = None if single_total is None or multi_total is None else single_total + multi_total
        metrics = [
            GarrisonMetric(label="总模拟数", value=_number(total)),
            GarrisonMetric(
                label="奖杯数量",
                value=_number(career.totalTrophyCnt),
                icon_url=garrison_asset_url("id_info_cup_icon.png"),
            ),
            GarrisonMetric(
                label="最佳记录",
                value=_text(career.mode) or "暂无数据",
                background_url=_difficulty_background_url(career.modeDifficulty),
            ),
            GarrisonMetric(
                label="游戏时长",
                value=duration_label,
                detail=recent_scope,
                icon_url=garrison_asset_url("time_icon.png"),
            ),
            GarrisonMetric(
                label="已获赞",
                value=_number(career.totalBeLikeCnt),
                icon_url=garrison_asset_url("like_icon.png"),
            ),
            GarrisonMetric(
                label="Boss 击杀",
                value=_number(boss_kills if recent_count else None),
                secondary_label="隐秘",
                secondary_value=_number(hidden_boss_kills if recent_count else None),
                detail=recent_scope,
            ),
        ]
        modes = []
        for label, count, wins in [
            ("独立", single_total, career.totalSingleBattleWinCnt),
            ("联合", multi_total, career.totalMultiBattleWinCnt),
        ]:
            modes.append(
                GarrisonMode(
                    label=label,
                    total=count if count is not None else 0,
                    wins=wins if wins is not None else 0,
                    losses=count - wins if count is not None and wins is not None else 0,
                    win_percent=100 * wins / count if count and wins is not None else None,
                )
            )
        strategies = [
            GarrisonStrategyStat(
                **model_dump(_band_item(resource, band_id, badge=badges.get(band_id))),
                recent_count=count,
                recent_wins=wins,
            )
            for band_id, (count, wins) in sorted(recent_bands.items(), key=lambda item: item[1][0], reverse=True)[:5]
        ]
        bonds = [
            GarrisonBondStat(**model_dump(_bond_item(resource, bond_id)), recent_count=count, max_layer=max_layer)
            for bond_id, (count, max_layer) in sorted(recent_bonds.items(), key=lambda item: item[1][0], reverse=True)[
                :5
            ]
        ]
        normal_titles = []
        special_titles = []
        other_titles = []
        seen_titles = set()
        for entries, target in [(career.normalTitles, normal_titles), (career.specialTitles, special_titles)]:
            for title in entries:
                if title.id in seen_titles:
                    continue
                meta = resource.titleInfo.get(title.id)
                count = title.count if title.count is not None else career.titleCntInfo.get(title.id)
                target.append(
                    GarrisonItem(
                        id=_text(title.id),
                        name=_text(title.name or (meta.name if meta else "") or title.id),
                        icon_url=_title_icon_url(title.picId or (meta.picId if meta else "")),
                        count=count,
                        badge=_text(title.type),
                    )
                )
                seen_titles.add(title.id)
        for title_id, count in career.titleCntInfo.items():
            if title_id in seen_titles:
                continue
            meta = resource.titleInfo.get(title_id)
            pic_id = meta.picId if meta else ""
            icon_url = _title_icon_url(pic_id)
            if icon_url and pic_id.endswith("_0"):
                target = special_titles
            elif icon_url and pic_id.endswith(("_1", "_2")):
                target = normal_titles
            else:
                target = other_titles
            target.append(
                GarrisonItem(
                    id=_text(title_id),
                    name=_text((meta.name if meta else "") or title_id),
                    icon_url=icon_url,
                    count=count,
                )
            )
        title_dimensions = [
            GarrisonTitleDimension(
                key=key,
                label=label,
                count=career.titleTypeCnt.get(key),
                icon_url=garrison_asset_url(f"titles/comment_icon_{icon}.png"),
            )
            for key, label, icon in [
                ("COIN", "资金管理", 4),
                ("KILL", "补救能力", 2),
                ("DAMAGE", "领袖挑战", 6),
                ("BOND", "盟约理解", 1),
                ("CHAR", "人力调度", 5),
                ("EQUIP", "装备活用", 3),
            ]
        ]
        version = resource.versionInfo
        if record_index is not None:
            selected_record = selected[record_index - 1]
            detail_resource = resources.for_version(selected_record.versionId, selected_record.activityId)
            version = (
                detail_resource.versionInfo
                if detail_resource
                else GarrisonVersion(activityId=selected_record.activityId, versionId=selected_record.versionId)
            )
        player = data.gameUserInfo
        return cls(
            nickname=_text(player.name) or _text(uid),
            uid=_text(uid),
            server_name=_text({"1": "官服", "2": "bilibili服"}.get(channel_master_id, server_name)),
            level=player.level,
            avatar_url=player.avatar.url if player.avatar else "",
            season_name=_text(version.seasonName) or _text(version.activityId) or "未知赛季",
            activity_id=_text(version.activityId),
            version_id=_text(version.versionId),
            is_detail=record_index is not None,
            favored=favored,
            records=records,
            metrics=metrics,
            modes=modes,
            recent_count=recent_count,
            recent_scope=recent_scope,
            strategies=strategies,
            bonds=bonds,
            normal_titles=normal_titles,
            special_titles=special_titles,
            other_titles=other_titles,
            title_dimensions=title_dimensions,
            title_scale=max(1, max((item.count for item in title_dimensions if item.count is not None), default=1)),
            title_radar_complete=all(item.count is not None for item in title_dimensions),
        )
