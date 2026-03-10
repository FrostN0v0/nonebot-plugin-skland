"""NoneBug 测试配置"""

import pytest
import nonebot
from pytest_asyncio import is_async_test
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter


def pytest_configure(config: pytest.Config):
    """NoneBug 初始化前配置：设置 ORM 数据库和禁用生命周期事件"""
    from nonebug import NONEBOT_INIT_KWARGS

    # 配置内存 SQLite 数据库供 nonebot-plugin-orm 使用
    config.stash[NONEBOT_INIT_KWARGS] = {
        "sqlalchemy_database_url": "sqlite+aiosqlite:///:memory:",
    }
    # 禁用 startup/shutdown 生命周期事件，避免 hook.py 中的数据下载
    try:
        from nonebug import NONEBOT_START_LIFESPAN

        config.stash[NONEBOT_START_LIFESPAN] = False
    except ImportError:
        pass


def pytest_collection_modifyitems(items):
    """统一将所有 async 测试标记为 session scope，共享事件循环"""
    pytest_asyncio_tests = (item for item in items if is_async_test(item))
    session_scope_marker = pytest.mark.asyncio(loop_scope="session")
    for async_test in pytest_asyncio_tests:
        async_test.add_marker(session_scope_marker, append=False)


@pytest.fixture(scope="session", autouse=True)
async def after_nonebot_init(after_nonebot_init: None):
    """NoneBug 初始化后注册适配器并加载插件"""

    driver = nonebot.get_driver()
    driver.register_adapter(OneBotV11Adapter)
    nonebot.load_from_toml("pyproject.toml")
