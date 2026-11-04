"""Isolated public worker: no NoneBot import, QQ secret, or Skland access."""

import os
import asyncio
import logging
from contextlib import asynccontextmanager

from core import Store
from fastapi import FastAPI
from protocol import install_routes

store = Store(os.environ["MAA_REMOTE_DATA_DIR"])
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("maa_gateway")


async def cleanup():
    while True:
        try:
            await asyncio.to_thread(store.cleanup)
        except Exception as error:  # noqa: BLE001 -- Never log request data.
            log.error("MAA cleanup failure type=%s", type(error).__name__)
        await asyncio.sleep(3600)


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(cleanup())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
install_routes(app, store, lambda action, task: log.info("MAA %s task=%s", action, task))
