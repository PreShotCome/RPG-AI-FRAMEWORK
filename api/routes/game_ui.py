"""Serves the web game UI at the root URL."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse
from pathlib import Path

router = APIRouter(tags=["ui"])
_HTML_PATH = Path(__file__).parent.parent.parent / "game.html"


@router.get("/")
def index():
    if _HTML_PATH.exists():
        return HTMLResponse(_HTML_PATH.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>game.html not found</h1>", status_code=404)


@router.get("/game")
def game_redirect():
    return RedirectResponse("/")
