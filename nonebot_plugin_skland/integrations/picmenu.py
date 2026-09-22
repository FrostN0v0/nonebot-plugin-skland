from nonebot.compat import model_dump
from nonebot import require, get_plugin

_registered = False


def register_picmenu_templates() -> bool:
    """Register Skland templates only when PicMenu Next is already loaded."""
    global _registered

    if get_plugin("nonebot_plugin_picmenu_next") is None:
        return False
    if _registered:
        return True

    require("nonebot_plugin_picmenu_next")

    from nonebot_plugin_alconna.uniseg import UniMessage
    from nonebot_plugin_picmenu_next.templates.jj_utils import build_base_render_kwargs
    from nonebot_plugin_picmenu_next.data_source.models import PMDataItem, PMNPluginInfo
    from nonebot_plugin_picmenu_next.templates import detail_templates, func_detail_templates
    from nonebot_plugin_picmenu_next.markdown import b64_prp_transformer, build_default_prp_processor

    from ..render import render_help
    from ..schemas.help import HelpView
    from ..extras import HELP_PREFIX, HELP_CATEGORIES

    prp_processor = build_default_prp_processor(b64_prp_transformer)

    async def render_menu(
        info: PMNPluginInfo,
        info_index: int,
        showing_hidden: bool,
        user_can_see_hidden: bool | None,
        *,
        func: PMDataItem | None = None,
        func_index: int | None = None,
        roster: bool = False,
    ) -> UniMessage:
        view = HelpView.from_menu(
            name=info.name,
            version=info.version,
            info_index=info_index,
            prefix=HELP_PREFIX,
            markdown=info.pmn.markdown,
            showing_hidden=showing_hidden,
            user_can_see_hidden=user_can_see_hidden,
            categories=HELP_CATEGORIES,
            menu_data=[model_dump(item) for item in info.pm_data or ()] if func is None else (),
            func_data=model_dump(func) if func is not None else None,
            func_index=func_index,
            roster=roster,
        )
        layout = build_base_render_kwargs(info, prp_processor=prp_processor)["layout"]
        image = await render_help(view, layout=layout)
        return UniMessage.image(raw=image)

    @detail_templates("skland")
    async def render_overview(
        info: PMNPluginInfo,
        info_index: int,
        showing_hidden: bool,
        user_can_see_hidden: bool | None,
    ) -> UniMessage:
        return await render_menu(info, info_index, showing_hidden, user_can_see_hidden)

    @func_detail_templates("skland")
    async def render_detail(
        info: PMNPluginInfo,
        info_index: int,
        func: PMDataItem,
        func_index: int | None,
        showing_hidden: bool,
        user_can_see_hidden: bool | None,
    ) -> UniMessage:
        return await render_menu(
            info,
            info_index,
            showing_hidden,
            user_can_see_hidden,
            func=func,
            func_index=func_index,
        )

    @func_detail_templates("skland_roster")
    async def render_roster(
        info: PMNPluginInfo,
        info_index: int,
        func: PMDataItem,
        func_index: int | None,
        showing_hidden: bool,
        user_can_see_hidden: bool | None,
    ) -> UniMessage:
        return await render_menu(
            info,
            info_index,
            showing_hidden,
            user_can_see_hidden,
            func=func,
            func_index=func_index,
            roster=True,
        )

    _registered = True
    return True
