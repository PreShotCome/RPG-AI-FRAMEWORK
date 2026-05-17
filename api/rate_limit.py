from fastapi import HTTPException
from core import session as sessions
from core.session import RATE_LIMIT_CALLS, RATE_LIMIT_WINDOW


def check_rate_limit(session_id: str) -> None:
    """
    Raise 429 if this session has exceeded the Claude call rate limit.
    Call this before any route that invokes the Anthropic API.
    """
    if not sessions.exists(session_id):
        return  # 404 will be raised by the route itself
    game_session = sessions.get(session_id)
    if game_session.is_rate_limited():
        window_minutes = int(RATE_LIMIT_WINDOW.total_seconds() / 60)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit reached ({RATE_LIMIT_CALLS} AI calls per {window_minutes} minutes). Try again shortly.",
        )


def record_api_call(session_id: str) -> None:
    """Increment the Claude call counter for this session."""
    if sessions.exists(session_id):
        sessions.get(session_id).record_api_call()
