"""Bounded local protocol. Only submit/status/redeem are exposed to the web UID."""

import os
import json
import asyncio
import sqlite3
from pathlib import Path

try:
    from .binding_state import BindingError
except ImportError:  # Standalone public worker, without importing the Skland package.
    from binding_state import BindingError

LIMIT = 4096


async def serve(store, path):
    path = Path(path)
    # The administrator creates this directory, owned by the bot and not web-writable.
    if path.exists():
        path.unlink()

    async def handle(reader, writer):
        response = {"error": "绑定服务暂不可用，请稍后重试。"}
        try:
            raw = await asyncio.wait_for(reader.readline(), 5)
            if not raw.endswith(b"\n") or len(raw) > LIMIT:
                raise ValueError
            request = json.loads(raw)
            if not isinstance(request, dict) or set(request) - {"op", "entry", "session", "device"}:
                raise ValueError
            op = request.get("op")
            keys = ("entry", "session", "device") if op == "submit" else ("entry", "session")
            if (
                not isinstance(op, str)
                or op not in {"submit", "status", "redeem"}
                or not all(isinstance(request.get(k), str) and len(request[k]) <= 128 for k in keys)
            ):
                raise ValueError
            response = {"result": await asyncio.to_thread(getattr(store, op), *(request[k] for k in keys))}
        except BindingError as error:
            response = {"error": str(error)}
        except (ValueError, OSError, sqlite3.Error, TimeoutError):
            pass  # Never log payloads, cookies or credentials.
        try:
            writer.write(json.dumps(response).encode() + b"\n")
            await asyncio.wait_for(writer.drain(), 5)
        except (OSError, TimeoutError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_unix_server(handle, path=str(path), limit=LIMIT)
    os.chmod(path, 0o660)
    os.chown(path, -1, path.parent.stat().st_gid)
    return server


def client(path):
    async def call(op, **kwargs):
        writer = None

        async def exchange():
            nonlocal writer
            reader, writer = await asyncio.open_unix_connection(str(path), limit=LIMIT)
            writer.write(json.dumps({"op": op, **kwargs}).encode() + b"\n")
            await writer.drain()
            response = json.loads(await reader.readline())
            if "error" in response:
                raise BindingError(response["error"])
            return response["result"]

        try:
            return await asyncio.wait_for(exchange(), 6)
        except BindingError:
            raise
        except (OSError, ValueError, TimeoutError, KeyError):
            raise BindingError("绑定服务暂不可用，请稍后重试。") from None
        finally:
            if writer:
                writer.close()
                await writer.wait_closed()

    return call
