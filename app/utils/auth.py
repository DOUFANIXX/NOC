from __future__ import annotations

from functools import wraps
import time

from flask import abort, flash, g, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


ROLE_ORDER = {
    "viewer": 1,
    "operator": 2,
    "admin": 3,
}


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    return check_password_hash(password_hash, password)


def login_user(user: dict) -> None:
    session.permanent = True
    session["user_id"] = user["id"]
    session["role"] = user["role"]
    session["last_activity_at"] = int(time.time())


def logout_user() -> None:
    session.pop("user_id", None)
    session.pop("role", None)
    session.pop("last_activity_at", None)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.full_path))
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles: str):
    minimum = min(ROLE_ORDER[role] for role in roles)

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                flash("Please sign in to continue.", "warning")
                return redirect(url_for("auth.login", next=request.full_path))
            current_level = ROLE_ORDER.get(g.user["role"], 0)
            if current_level < minimum:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator
