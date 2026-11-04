"""Bounded HTTP protocol for the isolated, unprivileged MAA gateway."""

import json
import asyncio

from core import RemoteError
from fastapi import Request, HTTPException

MAX_BODY = 12 * 1024 * 1024
HEADER_LIMIT = 4096


def report_header(raw):
    """Parse MAA's user/device/status/task prefix without buffering its image.

    MAA serializes these fields before payload. JSON string decoding prevents an
    embedded credential string masquerading as a top-level authentication key.
    """
    try:
        text = raw.decode("utf-8")
        decoder = json.JSONDecoder()
        pos = 0

        def space():
            nonlocal pos
            while pos < len(text) and text[pos].isspace():
                pos += 1

        space()
        if pos >= len(text):
            return None
        if text[pos] != "{":
            raise HTTPException(403, "invalid report header")
        pos += 1
        fields = {}
        for _ in range(8):
            space()
            key, pos = decoder.raw_decode(text, pos)
            if not isinstance(key, str) or key in fields:
                raise HTTPException(403, "invalid report header")
            space()
            if pos >= len(text):
                return None
            if text[pos] != ":":
                raise HTTPException(403, "invalid report header")
            pos += 1
            if key == "payload":
                if set(fields) != {"user", "device", "task", "status"}:
                    raise HTTPException(403, "invalid report header")
                return fields
            space()
            value, pos = decoder.raw_decode(text, pos)
            if key not in {"user", "device", "task", "status"} or not isinstance(value, str) or len(value) > 128:
                raise HTTPException(403, "invalid report header")
            fields[key] = value
            space()
            if pos >= len(text):
                return None
            if text[pos] == "}" and set(fields) == {"user", "device", "task", "status"}:
                return fields
            if text[pos] != ",":
                raise HTTPException(403, "invalid report header")
            pos += 1
    except (UnicodeError, ValueError):
        return None
    return None


def install_routes(app, store, audit=lambda *args: None):
    reports = asyncio.Semaphore(2)

    async def read_body(request, limit, authenticate=False):
        raw = bytearray()
        verified = not authenticate
        async for part in request.stream():
            if len(raw) + len(part) > limit:
                raise HTTPException(413, "request too large")
            if not verified:
                prefix = bytes(raw[:HEADER_LIMIT]) + part[: max(0, HEADER_LIMIT - len(raw))]
                header = report_header(prefix)
                if header:
                    try:
                        await asyncio.to_thread(
                            store.authorize_report,
                            header["user"],
                            header["device"],
                            header["task"],
                            header["status"],
                        )
                    except RemoteError:
                        raise HTTPException(403, "invalid report") from None
                    verified = True
                elif len(raw) + len(part) >= HEADER_LIMIT:
                    raise HTTPException(403, "invalid report header")
            raw.extend(part)
        if not verified:
            raise HTTPException(403, "invalid report header")
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeError, RecursionError):
            raise HTTPException(400, "invalid JSON") from None
        if not isinstance(body, dict):
            raise HTTPException(400, "invalid JSON object")
        return body

    @app.post("/maa/getTask", include_in_schema=False)
    async def get_task(request: Request):
        try:
            body = await asyncio.wait_for(read_body(request, HEADER_LIMIT), timeout=10)
            return await asyncio.to_thread(store.poll, body.get("user"), body.get("device"))
        except TimeoutError:
            raise HTTPException(408, "request timeout") from None
        except RemoteError:
            raise HTTPException(403, "invalid binding") from None

    @app.post("/maa/reportStatus", include_in_schema=False)
    async def report_status(request: Request):
        if reports.locked():
            raise HTTPException(429, "upload capacity reached")
        async with reports:
            try:
                body = await asyncio.wait_for(read_body(request, MAX_BODY, authenticate=True), timeout=20)
                task_id = body.get("task")
                await asyncio.to_thread(
                    store.report,
                    body.get("user"),
                    body.get("device"),
                    task_id,
                    body.get("status"),
                    body.get("payload", ""),
                )
            except TimeoutError:
                raise HTTPException(408, "request timeout") from None
            except RemoteError:
                raise HTTPException(403, "invalid report") from None
        audit("report", task_id)
        return {"ok": True}
