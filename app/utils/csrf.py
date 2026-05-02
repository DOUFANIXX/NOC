from __future__ import annotations

import secrets

from flask import abort, request, session
from markupsafe import Markup


TOKEN_KEY = "_csrf_token"


def ensure_csrf_token() -> str:
    token = session.get(TOKEN_KEY)
    if not token:
        token = secrets.token_hex(16)
        session[TOKEN_KEY] = token
    return token


def validate_csrf() -> None:
    expected = ensure_csrf_token()
    received = request.form.get("_csrf_token") or request.headers.get("X-CSRF-Token")
    if not received or received != expected:
        abort(400, "Invalid CSRF token.")


def csrf_input() -> Markup:
    token = ensure_csrf_token()
    return Markup(f'<input type="hidden" name="_csrf_token" value="{token}">')
