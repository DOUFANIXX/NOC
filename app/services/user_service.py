from __future__ import annotations

import secrets
from pathlib import Path

from app.db import get_db
from app.utils.auth import hash_password, verify_password
from app.utils.helpers import utcnow_iso
from app.utils.validation import VALID_ROLES, VALID_UI_PREFERENCES, normalize_ui_preference


def get_user_by_id(user_id: int | None) -> dict | None:
    if not user_id:
        return None
    row = get_db().execute(
        "SELECT id, username, password_hash, role, is_active, ui_preference, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    return _normalize_user_record(dict(row)) if row else None


def get_user_by_username(username: str) -> dict | None:
    row = get_db().execute(
        "SELECT id, username, password_hash, role, is_active, ui_preference, created_at FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    return _normalize_user_record(dict(row)) if row else None


def authenticate(username: str, password: str) -> dict | None:
    user = get_user_by_username(username.strip())
    if not user or not user["is_active"]:
        return None
    if not verify_password(user["password_hash"], password):
        return None
    return user


def list_users() -> list[dict]:
    rows = get_db().execute(
        """
        SELECT id, username, role, is_active, ui_preference, created_at
        FROM users
        ORDER BY
            is_active DESC,
            CASE role
                WHEN 'admin' THEN 3
                WHEN 'operator' THEN 2
                WHEN 'viewer' THEN 1
                ELSE 0
            END DESC,
            username ASC
        """
    ).fetchall()
    return [_normalize_user_record(dict(row)) for row in rows]


def create_user(username: str, password: str, role: str, ui_preference: str = "dark") -> int:
    normalized_role = (role or "").strip().lower()
    if normalized_role not in VALID_ROLES:
        raise ValueError("Unsupported role.")
    normalized_ui_preference = normalize_ui_preference(ui_preference, default="dark")
    if normalized_ui_preference not in VALID_UI_PREFERENCES:
        raise ValueError("Unsupported UI preference.")

    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE username = ?", (username.strip(),)).fetchone()
    if existing:
        raise ValueError("That username already exists.")

    db.execute(
        """
        INSERT INTO users (username, password_hash, role, is_active, ui_preference, created_at)
        VALUES (?, ?, ?, 1, ?, ?)
        """,
        (username.strip(), hash_password(password), normalized_role, normalized_ui_preference, utcnow_iso()),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def set_user_active(user_id: int, is_active: bool) -> dict | None:
    user = get_user_by_id(user_id)
    if not user:
        return None
    db = get_db()
    db.execute("UPDATE users SET is_active = ? WHERE id = ?", (1 if is_active else 0, user_id))
    db.commit()
    return get_user_by_id(user_id)


def delete_user(user_id: int) -> dict | None:
    user = get_user_by_id(user_id)
    if not user:
        return None
    db = get_db()
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    return user


def set_ui_preference(user_id: int, ui_preference: str) -> dict | None:
    user = get_user_by_id(user_id)
    if not user:
        return None

    normalized_ui_preference = normalize_ui_preference(ui_preference, default="dark")
    if normalized_ui_preference not in VALID_UI_PREFERENCES:
        raise ValueError("Unsupported UI preference.")

    db = get_db()
    db.execute("UPDATE users SET ui_preference = ? WHERE id = ?", (normalized_ui_preference, user_id))
    db.commit()
    return get_user_by_id(user_id)


def ensure_bootstrap_admin(app) -> None:
    db = get_db()
    count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count:
        return

    username = app.config["BOOTSTRAP_ADMIN_USERNAME"]
    password = app.config["BOOTSTRAP_ADMIN_PASSWORD"].strip()
    generated = False

    if not password:
        password = secrets.token_urlsafe(12)
        generated = True

    db.execute(
        """
        INSERT INTO users (username, password_hash, role, is_active, ui_preference, created_at)
        VALUES (?, ?, ?, 1, 'dark', ?)
        """,
        (username, hash_password(password), app.config["BOOTSTRAP_ADMIN_ROLE"], utcnow_iso()),
    )
    db.commit()

    if generated:
        bootstrap_file = Path(app.config["INSTANCE_PATH"]) / "bootstrap_admin.txt"
        bootstrap_file.write_text(
            (
                "A bootstrap admin user was generated because BOOTSTRAP_ADMIN_PASSWORD was not set.\n"
                f"Username: {username}\n"
                f"Password: {password}\n"
                "Rotate this password immediately and delete this file after first sign-in.\n"
            ),
            encoding="utf-8",
        )


def _normalize_user_record(user: dict) -> dict:
    if "ui_preference" in user:
        user["ui_preference"] = normalize_ui_preference(user.get("ui_preference"), default="dark")
    return user
