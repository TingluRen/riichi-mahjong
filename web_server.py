"""Public demo entry point: run with uvicorn web_server:app."""
import inspect
import logging
import os
import sqlite3
from functools import wraps

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.routing import APIRoute

import server
from game_store import InvalidSaveError
from visitor_store import SESSION_SECONDS, VisitorStore

logger = logging.getLogger(__name__)
COOKIE_NAME = "mahjong_visitor"
visitor_store = VisitorStore(os.environ.get(
    "MAHJONG_VISITOR_DB", str(server.base_dir / "data" / "visitors.sqlite3")))
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def protect_actions(request, call_next):
    # Browser actions must originate on this site; no extra login is needed.
    if request.method == "POST":
        origin = request.headers.get("origin")
        own_origin = str(request.base_url).rstrip("/")
        if (request.headers.get("sec-fetch-site") == "cross-site"
                or origin is not None and origin != own_origin):
            return JSONResponse({"detail": "Please play from the game page."}, status_code=403)
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def home():
    # Keep the same artwork and layout; hide local development tools online.
    page = (server.base_dir / "static" / "index.html").read_text(encoding="utf-8")
    page = page.replace('<details class="developer-tools">',
                        '<details class="developer-tools" hidden>')
    page = page.replace("Progress is saved automatically on this computer.",
                        "Progress is saved for this browser for up to 30 days of inactivity.")
    return HTMLResponse(page, headers={"Cache-Control": "no-store"})


@app.get("/health")
def health():
    # Hosting checks must not create visitor games.
    return {"status": "ok"}


def visitor_endpoint(function):
    """Reuse the existing rules and view with a request-local visitor state."""
    @wraps(function)
    def wrapped(**kwargs):
        request = kwargs.pop("visitor_request")
        try:
            with visitor_store.session(request.cookies.get(COOKIE_NAME)) as (token, state):
                state_token = server.request_state.set(state)
                action_token = server.http_action.set(request.method == "POST")
                try:
                    result = function(**kwargs)
                    response = JSONResponse(result)
                finally:
                    server.http_action.reset(action_token)
                    server.request_state.reset(state_token)
            # Return success only after the database commit has completed.
            response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS,
                                httponly=True, samesite="lax", path="/",
                                secure=request.url.scheme == "https")
            return response
        except (sqlite3.Error, OSError, InvalidSaveError) as error:
            logger.warning("Visitor game could not be saved or restored: %s", error)
            raise HTTPException(status_code=503, detail=
                                "Could not load or save your game. Please retry shortly.") from error

    # Add FastAPI's Request argument while preserving each action's body validation.
    signature = inspect.signature(function)
    wrapped.__signature__ = signature.replace(parameters=[
        *signature.parameters.values(),
        inspect.Parameter("visitor_request", inspect.Parameter.KEYWORD_ONLY,
                          annotation=Request),
    ])
    return wrapped


# Only game routes are public. Debug endpoints are never registered here.
for route in server.app.routes:
    if (isinstance(route, APIRoute) and route.path.startswith("/api/")
            and not route.path.startswith("/api/debug/")):
        app.add_api_route(route.path, visitor_endpoint(route.endpoint),
                          methods=sorted(route.methods), name=route.name)
