"""资源同步命令"""

from nonebot import logger
from nonebot.params import Depends
from nonebot.permission import SuperUser
from nonebot_plugin_user import UserSession
from nonebot_plugin_alconna import Arparma, UniMessage

from ..utils.message import send_reaction
from ..download import download_img_resource
from ..services.resources import update_data_resources
from ..exception import RequestException, ResourceUpdateInProgress


async def sync_handler(
    user_session: UserSession,
    result: Arparma,
    is_superuser: bool = Depends(SuperUser()),
):
    """同步游戏资源"""
    if not is_superuser:
        send_reaction(user_session, "unmatch")
        await UniMessage.text("该指令仅超管可用").finish()

    force_update = result.find("sync.force")
    update_img = result.find("sync.img")
    update_data = result.find("sync.data")
    update_existing = result.find("sync.update")

    update_all = not update_img and not update_data

    send_reaction(user_session, "processing")
    messages = []
    has_error = False

    try:
        if update_img or update_all:
            logger.info("开始更新图片资源...")
            try:
                download_result = await download_img_resource(
                    force=force_update,
                    update=update_existing,
                )
                if download_result.version is None:
                    messages.append("📦 图片资源已是最新版本")
                else:
                    update_mode = "（覆盖更新）" if update_existing else ""
                    stats = f"成功: {download_result.success_count}个"
                    if download_result.failed_count > 0:
                        stats += f"，失败: {download_result.failed_count}个"
                    messages.append(f"✅ 图片资源更新成功{update_mode}，版本: {download_result.version}（{stats}）")
            except RequestException as e:
                logger.error(f"下载图片资源失败: {e}")
                messages.append(f"❌ 图片资源更新失败: {e.args[0]}")
                has_error = True

        if update_data or update_all:
            logger.info("开始更新数据资源...")
            try:
                data_result = await update_data_resources(force=bool(force_update), refresh_metadata=True)
                messages.extend(data_result.messages)
                has_error = has_error or data_result.failed
            except ResourceUpdateInProgress as error:
                messages.append(str(error))
                has_error = True

        if has_error:
            send_reaction(user_session, "fail")
        else:
            send_reaction(user_session, "done")

        result_msg = "\n".join(messages)
        if force_update:
            result_msg = "🔄 强制更新模式\n\n" + result_msg

        await UniMessage.text(result_msg).send()

    except Exception as e:
        logger.exception(f"同步资源时发生未知错误: {e}")
        send_reaction(user_session, "fail")
        await UniMessage.text(f"❌ 同步资源失败: {type(e).__name__}: {str(e)}").send()
