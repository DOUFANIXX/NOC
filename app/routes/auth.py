from __future__ import annotations

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from app.services import audit_service, user_service
from app.utils.auth import login_required, login_user, logout_user
from app.utils.validation import validate_ui_preference


bp = Blueprint("auth", __name__, url_prefix="/auth")


def _default_landing_endpoint(role: str | None) -> str:
    if role == "viewer":
        return "monitoring.index"
    return "dashboard.index"


def _theme_label(value: str) -> str:
    return "White + Red" if value == "light" else "Black + Blue"


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for(_default_landing_endpoint(g.user["role"])))

    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = user_service.authenticate(username, password)
        if user is None:
            error = "Invalid username or password."
        else:
            login_user(user)
            audit_service.log_event("auth.login", "user", str(user["id"]), {"username": user["username"]})
            next_url = request.args.get("next")
            return redirect(next_url or url_for(_default_landing_endpoint(user["role"])))
    return render_template("auth/login.html", error=error)


@bp.post("/logout")
def logout():
    if g.user:
        audit_service.log_event("auth.logout", "user", str(g.user["id"]), {"username": g.user["username"]})
    logout_user()
    return redirect(url_for("auth.login"))


@bp.post("/ui-mode")
@login_required
def update_ui_mode():
    next_path = (request.form.get("next_path") or "").strip()
    redirect_target = next_path if next_path.startswith("/") else url_for(_default_landing_endpoint(g.user["role"]))

    try:
        ui_preference = validate_ui_preference(request.form.get("ui_preference", "dark"))
        updated = user_service.set_ui_preference(g.user["id"], ui_preference)
        if not updated:
            raise ValueError("Your account could not be updated.")
        audit_service.log_event(
            "auth.ui_preference_updated",
            "user",
            str(g.user["id"]),
            {
                "outcome": "success",
                "summary": f"Theme changed to {_theme_label(ui_preference)}.",
                "username": g.user["username"],
                "ui_preference": ui_preference,
            },
        )
        flash(f"{_theme_label(ui_preference)} theme selected for your account.", "success")
    except Exception as exc:
        flash(str(exc), "danger")

    return redirect(redirect_target)
