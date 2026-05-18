def test_extra_pool_uses_all_rarity_six_as_up_chars(app):
    from nonebot_plugin_skland.schemas.endfield.gacha.base import EfGachaContentChar, EfGachaContentPool

    pool = EfGachaContentPool(
        pool_gacha_type="char",
        pool_type="extra",
        up6_name="莱万汀",
        all=[
            EfGachaContentChar(id="chr_0016_laevat", name="莱万汀", rarity=6),
            EfGachaContentChar(id="chr_0013_aglina", name="洁尔佩塔", rarity=6),
            EfGachaContentChar(id="chr_0025_ardelia", name="艾尔黛拉", rarity=6),
            EfGachaContentChar(id="chr_0029_pograni", name="骏卫", rarity=6),
            EfGachaContentChar(id="chr_0004_pelica", name="佩丽卡", rarity=5),
        ],
    )

    assert pool.up_six_char_ids == [
        "chr_0016_laevat",
        "chr_0013_aglina",
        "chr_0025_ardelia",
        "chr_0029_pograni",
    ]
    assert pool.up_six_display_name == "莱万汀 / 洁尔佩塔 / 艾尔黛拉 / 骏卫"


def test_endfield_joint_pool_type_value(app):
    from nonebot_plugin_skland.schemas.endfield.gacha.base import EndfieldPoolType

    assert EndfieldPoolType.JOINT.value == "E_CharacterGachaPoolType_Joint"


def test_joint_pool_id_is_classified_as_joint(app):
    from nonebot_plugin_skland.utils import _infer_pool_category
    from nonebot_plugin_skland.schemas.endfield.gacha.pool import EfGachaPoolInfo
    from nonebot_plugin_skland.schemas.endfield.gacha.base import EfGachaPull, EfGachaGroup

    pool = EfGachaPoolInfo(
        pool_id="joint_1_2_2",
        pool_name="辉光庆典",
        pool_type="char",
        records=[
            EfGachaGroup(
                gacha_ts=100,
                pulls=[
                    EfGachaPull(
                        pool_name="辉光庆典",
                        item_id="chr_0016_laevat",
                        item_name="莱万汀",
                        item_type="char",
                        rarity=6,
                        is_new=True,
                        is_free=False,
                        seq_id=1,
                    )
                ],
            )
        ],
    )

    assert _infer_pool_category("joint_1_2_2") == "joint"
    assert pool.pool_category == "joint"


def make_record(
    *,
    pool_id: str = "joint_1_2_2",
    char_id: str = "chr_0016_laevat",
    char_name: str = "莱万汀",
    rarity: int = 6,
    gacha_ts: int = 100,
    pos: int = 1,
    is_free: bool = False,
):
    from nonebot_plugin_skland.model import GachaRecord

    return GachaRecord(
        uid=1,
        char_pk_id=1,
        char_uid="endfield-uid",
        app_code="endfield",
        item_type="char",
        pool_id=pool_id,
        pool_name="辉光庆典",
        char_id=char_id,
        char_name=char_name,
        rarity=rarity,
        is_new=True,
        is_free=is_free,
        gacha_ts=gacha_ts,
        pos=pos,
    )


def test_group_ef_gacha_records_routes_joint_pool_separately(app):
    from nonebot_plugin_skland.utils import group_ef_gacha_records

    grouped = group_ef_gacha_records([make_record()])

    assert [p.pool_id for p in grouped.joint_pools] == ["joint_1_2_2"]
    assert grouped.standard_pools == []
    assert (
        grouped.char_pools
        == grouped.beginner_pools + grouped.standard_pools + grouped.special_pools + grouped.joint_pools
    )


def test_joint_statistics_use_only_six_star_count_and_six_average(app):
    from nonebot_plugin_skland.utils import group_ef_gacha_records

    grouped = group_ef_gacha_records(
        [
            make_record(rarity=6, gacha_ts=100, pos=1),
            make_record(char_id="chr_0019_karin", char_name="秋栗", rarity=4, gacha_ts=101, pos=2),
            make_record(char_id="chr_0020_meurs", char_name="卡契尔", rarity=4, gacha_ts=102, pos=3),
        ]
    )

    assert grouped.joint_total_pulls == 3
    assert grouped.joint_total_six == 1
    assert grouped.joint_pity == 2
    assert grouped.joint_pity_remaining == 78
    assert grouped.joint_six_avg == 1.0
    assert grouped.char_total_pulls == 3


def test_joint_pool_type_is_fetched_during_update(app):
    from nonebot_plugin_skland.commands.endfield.gacha import EF_CHAR_POOL_TYPES
    from nonebot_plugin_skland.schemas.endfield.gacha.base import EndfieldPoolType

    assert EF_CHAR_POOL_TYPES == [
        EndfieldPoolType.STANDARD,
        EndfieldPoolType.SPECIAL,
        EndfieldPoolType.BEGINNER,
        EndfieldPoolType.JOINT,
    ]


def test_joint_pool_does_not_show_spook_stats(app):
    from nonebot_plugin_skland.schemas.endfield.gacha.pool import EfGachaPoolInfo
    from nonebot_plugin_skland.schemas.endfield.gacha.base import EfGachaPull, EfGachaGroup

    joint_pool = EfGachaPoolInfo(
        pool_id="joint_1_2_2",
        pool_name="辉光庆典",
        pool_type="char",
        up_six_chars=["chr_0016_laevat", "chr_0013_aglina"],
        records=[
            EfGachaGroup(
                gacha_ts=100,
                pulls=[
                    EfGachaPull(
                        pool_name="辉光庆典",
                        item_id="chr_0016_laevat",
                        item_name="莱万汀",
                        item_type="char",
                        rarity=6,
                        is_new=True,
                        is_free=False,
                        seq_id=1,
                    )
                ],
            )
        ],
    )
    special_pool = joint_pool.model_copy(update={"pool_id": "special_1_2_1"})

    assert joint_pool.show_spook_stats is False
    assert special_pool.show_spook_stats is True


def test_ef_gacha_viewport_expands_when_joint_pools_exist(app):
    from nonebot_plugin_skland.utils import group_ef_gacha_records
    from nonebot_plugin_skland.render import get_ef_gacha_viewport_width

    standard_grouped = group_ef_gacha_records([make_record(pool_id="standard", rarity=4)])
    joint_grouped = group_ef_gacha_records([make_record()])

    assert get_ef_gacha_viewport_width(standard_grouped) == 800
    assert get_ef_gacha_viewport_width(joint_grouped) == 1020


def test_joint_pool_keeps_separate_column_with_dynamic_width(app):
    from pathlib import Path

    template_path = (
        Path(__file__).resolve().parents[1]
        / "nonebot_plugin_skland"
        / "resources"
        / "templates"
        / "ef_gacha.html.jinja2"
    )
    template = template_path.read_text(encoding="utf-8")

    assert 'ef_pool_column(record.joint_pools, "联合寻访", "#c084fc"' in template
    assert "{{ 900 if record.joint_pools else 680 }}px" in template


def test_pool_header_renders_up_chars_as_avatars(app):
    from pathlib import Path

    template_path = (
        Path(__file__).resolve().parents[1]
        / "nonebot_plugin_skland"
        / "resources"
        / "templates"
        / "ef_gacha_macros.html.jinja2"
    )
    template = template_path.read_text(encoding="utf-8")

    assert "UP: {{ pool.up6_name }}" not in template
    assert "{% for up_char_id in pool.up_six_chars %}" in template
    assert "{{ up_char_id | ef_charId_to_avatarUrl }}" in template
