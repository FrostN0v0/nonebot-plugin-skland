from pathlib import Path

import pytest
import nonebot
from pytest_mock import MockerFixture
from pytest_asyncio import is_async_test
from sqlalchemy import StaticPool, delete
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter
from nonebug import NONEBOT_INIT_KWARGS, NONEBOT_START_LIFESPAN, App


def pytest_configure(config: pytest.Config):
    config.stash[NONEBOT_INIT_KWARGS] = {
        "sqlalchemy_database_url": "sqlite+aiosqlite://",
        "sqlalchemy_engine_options": {"poolclass": StaticPool},
        "driver": "~fastapi+~httpx",
        "alembic_startup_check": False,
        "command_start": {"/", ""},
    }
    config.stash[NONEBOT_START_LIFESPAN] = False


def pytest_collection_modifyitems(items):
    pytest_asyncio_tests = (item for item in items if is_async_test(item))
    session_scope_marker = pytest.mark.asyncio(loop_scope="session")
    for async_test in pytest_asyncio_tests:
        async_test.add_marker(session_scope_marker, append=False)


@pytest.fixture(scope="session", autouse=True)
async def after_nonebot_init(after_nonebot_init: None):
    """NoneBug 初始化后注册适配器并加载插件"""

    driver = nonebot.get_driver()
    driver.register_adapter(OneBotV11Adapter)
    await driver._lifespan.startup()
    nonebot.load_from_toml("pyproject.toml")


@pytest.fixture
async def app(app: App, tmp_path: Path, mocker: MockerFixture):
    skland_dir = tmp_path / "skland"
    skland_dir.mkdir()
    mocker.patch("nonebot_plugin_skland.config.DATA_DIR", skland_dir)
    mocker.patch("nonebot_plugin_orm._data_dir", tmp_path / "orm")
    from nonebot_plugin_orm import init_orm, get_session

    await init_orm()
    yield app

    from nonebot_plugin_skland.model import SkUser, Character, GachaRecord, CharacterDefault

    async with get_session() as session, session.begin():
        await session.execute(delete(CharacterDefault))
        await session.execute(delete(GachaRecord))
        await session.execute(delete(Character))
        await session.execute(delete(SkUser))

    from nonebot_plugin_apscheduler import scheduler

    scheduler.remove_all_jobs()


@pytest.fixture
async def make_user_session(app):
    from nonebot_plugin_orm import get_session
    from nonebot_plugin_user import UserSession
    from nonebot_plugin_user.models import User
    from nonebot_plugin_uninfo import User as PlatformUser
    from nonebot_plugin_uninfo import Scene, Session, SceneType

    created_ids: list[int] = []

    async def create(session, owner_id: int, *, private: bool = False) -> UserSession:
        user = User(id=owner_id, name=f"test-user-{owner_id}")
        session.add(user)
        created_ids.append(owner_id)
        await session.commit()
        await session.refresh(user)
        return UserSession(
            user=user,
            session=Session(
                self_id="bot",
                adapter="OneBot V11",
                scope="QQClient",
                scene=Scene(
                    id=str(owner_id) if private else "group", type=SceneType.PRIVATE if private else SceneType.GROUP
                ),
                user=PlatformUser(id=str(owner_id)),
            ),
        )

    yield create

    async with get_session() as session, session.begin():
        await session.execute(delete(User).where(User.id.in_(created_ids)))
