"""
gui/api/tokens.py

Per-project bearer tokens for the local HTTP API. A token is generated the
moment a project becomes reachable (opened, or via File -> API Access) and
discarded when it's closed, so the API can only ever address projects that
are currently open in the GUI.

One-Time Token Delivery over HTTP:
  - An external caller must first ask for the token via GET/POST
    /<project_id>/get_tokens, which shows an Allow/Deny popup in the GUI.
  - Once a caller has been handed the token this way, it's marked
    delivered - every later /get_tokens call for the same project is
    rejected with token_already_delivered, with no popup shown. Anyone who
    needs it again has to ask a human to copy it from File -> API Access.
  - Denying doesn't stick: it only fails that one request. A script that
    asks again later gets asked again - simpler than a persisted
    session-wide "denied forever" status, and avoids stale state from an
    earlier call silently deciding a much later one.
  - To stop a script from endlessly reopening the popup if it just keeps
    asking, each project caps how many times get_tokens is allowed to
    raise the popup at MAX_PROMPTS; past that, further calls are rejected
    outright (no popup) until the project is closed and reopened.
"""

import secrets
import threading

_lock = threading.Lock()
_tokens: dict[str, str] = {}
_delivered: dict[str, bool] = {}  # { project_id: True once handed out over HTTP }
_prompt_count: dict[str, int] = {}  # { project_id: number of popups shown so far }

MAX_PROMPTS = 3


def ensure_token(project_id: str) -> str:
    """Return the token for project_id, generating one on first call."""
    with _lock:
        token = _tokens.get(project_id)
        if token is None:
            token = secrets.token_urlsafe(24)
            _tokens[project_id] = token
        return token


def get_token(project_id: str) -> str | None:
    with _lock:
        return _tokens.get(project_id)


def check_token(project_id: str, provided: str | None) -> bool:
    if not provided:
        return False
    with _lock:
        expected = _tokens.get(project_id)
    return expected is not None and secrets.compare_digest(expected, provided)


def check_any(provided: str | None) -> bool:
    """True if `provided` matches ANY currently-issued project token. Used to
    gate endpoints that aren't project-scoped (the material catalog search)
    but still shouldn't be reachable with zero projects open - the API's
    contract stays "only usable while at least one project is open"."""
    if not provided:
        return False
    with _lock:
        candidates = list(_tokens.values())
    return any(secrets.compare_digest(t, provided) for t in candidates)


def regenerate(project_id: str) -> str:
    with _lock:
        token = secrets.token_urlsafe(24)
        _tokens[project_id] = token
        # A freshly (re)generated token hasn't gone out over HTTP yet -
        # re-arm one-time delivery so the next /get_tokens caller can pick
        # it up (after another Allow), rather than being told a token
        # that's actually different was "already delivered".
        _delivered[project_id] = False
        return token


def clear_token(project_id: str) -> None:
    """Clean up all of this project's API-access state - called both on
    Revoke Token and on project window close."""
    with _lock:
        _tokens.pop(project_id, None)
        _delivered.pop(project_id, None)
        _prompt_count.pop(project_id, None)


# ── One-time HTTP delivery ─────────────────────────────────────────────────

def is_delivered(project_id: str) -> bool:
    with _lock:
        return _delivered.get(project_id, False)


def mark_delivered(project_id: str) -> None:
    with _lock:
        _delivered[project_id] = True


def can_prompt(project_id: str) -> bool:
    """True (and counts against MAX_PROMPTS) if this project hasn't hit its
    popup cap yet - keeps a script that just keeps calling /get_tokens
    from reopening the Allow/Deny dialog indefinitely."""
    with _lock:
        count = _prompt_count.get(project_id, 0)
        if count >= MAX_PROMPTS:
            return False
        _prompt_count[project_id] = count + 1
        return True
