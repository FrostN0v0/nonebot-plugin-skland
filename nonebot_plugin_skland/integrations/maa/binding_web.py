"""Isolated public binding endpoints; only a narrow Unix-socket broker is accessible."""

import json
import secrets
from pathlib import Path

from binding_state import BindingError
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response, HTMLResponse, JSONResponse

PREFIX = "/maa/bind"
COOKIE = "__Host-maa-bind"


def create_app(broker, origin):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    directory = Path(__file__).parent

    @app.middleware("http")
    async def protect(request, call_next):
        response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": (
                    "default-src 'none'; script-src 'self'; style-src 'self'; "
                    "connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
                ),
            }
        )
        return response

    @app.exception_handler(BindingError)
    async def invalid(request, error):
        return JSONResponse({"error": str(error)}, status_code=400)

    @app.get(PREFIX, response_class=HTMLResponse)
    async def page():
        return HTMLResponse((directory / "binding.html").read_text(encoding="utf-8"))

    @app.get(PREFIX + "/binding.js")
    async def script():
        return Response((directory / "binding.js").read_text(encoding="utf-8"), media_type="text/javascript")

    @app.get(PREFIX + "/binding.css")
    async def style():
        return Response((directory / "binding.css").read_text(encoding="utf-8"), media_type="text/css")

    @app.post(PREFIX + "/api/submit")
    async def submit(request: Request):
        if request.headers.get("origin") != origin:
            raise HTTPException(403, "origin refused")
        raw = bytearray()
        async for part in request.stream():
            raw.extend(part)
            if len(raw) > 2048:
                raise HTTPException(413, "request too large")
        try:
            body = json.loads(raw)
            if not isinstance(body, dict) or not all(isinstance(body.get(k), str) for k in ("request", "device")):
                raise ValueError
        except (ValueError, UnicodeError):
            raise HTTPException(400, "invalid request") from None
        session = request.cookies.get(COOKIE)
        if not session or len(session) != 43:
            session = secrets.token_urlsafe(32)
        row = await broker("submit", entry=body["request"], session=session, device=body["device"])
        response = JSONResponse({"state": row["state"], "device": row["device"], "code": row["code"]})
        response.set_cookie(COOKIE, session, secure=True, httponly=True, samesite="strict", max_age=600, path="/")
        return response

    @app.get(PREFIX + "/api/status")
    async def status(request: Request, entry: str):
        return await broker("status", entry=entry, session=request.cookies.get(COOKIE, ""))

    @app.post(PREFIX + "/api/redeem")
    async def redeem(request: Request):
        if request.headers.get("origin") != origin:
            raise HTTPException(403, "origin refused")
        entry = request.query_params.get("entry", "")
        return await broker("redeem", entry=entry, session=request.cookies.get(COOKIE, ""))

    return app
