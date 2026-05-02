from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.services import audit_service
from app.services import user_service
from app.services.switch_inventory_service import add_switch_record, delete_switch_record, list_inventory
from app.utils.auth import role_required
from app.utils.helpers import paginate_items, parse_page
from app.utils.validation import FormValidationError, validate_positive_int, validate_switch_inventory_payload, validate_user_payload


bp = Blueprint("admin", __name__, url_prefix="/admin")


def _default_form_data() -> dict:
    return {
        "inventory_type": "ultra",
        "city": "",
        "area": "",
        "site": "",
        "name": "",
        "ip": "",
        "notes": "",
    }


def _default_user_form_data() -> dict:
    return {
        "username": "",
        "role": "viewer",
        "ui_preference": "dark",
        "password": "",
    }


@bp.route("/switches", methods=["GET", "POST"])
@role_required("admin")
def switches():
    form_data = _default_form_data()
    form_errors: dict[str, str] = {}
    page_feedback = None

    if request.method == "POST":
        action = request.form.get("action", "add")
        if action == "add":
            form_data.update(
                {
                    "inventory_type": request.form.get("inventory_type", "ultra"),
                    "city": request.form.get("city", ""),
                    "area": request.form.get("area", ""),
                    "site": request.form.get("site", ""),
                    "name": request.form.get("name", ""),
                    "ip": request.form.get("ip", ""),
                    "notes": request.form.get("notes", ""),
                }
            )
            try:
                cleaned = validate_switch_inventory_payload(form_data)
                new_id = add_switch_record(cleaned)
                audit_service.log_event(
                    "inventory.switch_added",
                    "switch_inventory",
                    str(new_id),
                    {
                        "outcome": "success",
                        "summary": f"Added switch record {cleaned['name']} ({cleaned['ip']}).",
                        **cleaned,
                    },
                )
                flash("Switch record added.", "success")
                return redirect(url_for("admin.switches"))
            except FormValidationError as exc:
                form_errors = exc.field_errors
                page_feedback = {"tone": "warning", "title": "Validation error", "message": str(exc)}
                audit_service.log_event(
                    "inventory.switch_add_rejected",
                    "switch_inventory",
                    None,
                    {
                        "outcome": "validation_error",
                        "summary": str(exc),
                        "attempted": {key: form_data.get(key, "") for key in ("inventory_type", "city", "area", "site", "name", "ip")},
                        "field_errors": form_errors,
                    },
                )
            except Exception as exc:
                page_feedback = {
                    "tone": "danger",
                    "title": "Inventory update failed",
                    "message": "The switch record could not be saved. Check the entered values and try again.",
                }
                audit_service.log_event(
                    "inventory.switch_add_failed",
                    "switch_inventory",
                    None,
                    {
                        "outcome": "failed",
                        "summary": str(exc),
                        "attempted": {key: form_data.get(key, "") for key in ("inventory_type", "city", "area", "site", "name", "ip")},
                    },
                )
        elif action == "delete":
            try:
                switch_id = validate_positive_int(request.form.get("switch_id", ""), "switch record")
                record = delete_switch_record(switch_id)
                if not record:
                    raise ValueError("That switch record no longer exists.")
                audit_service.log_event(
                    "inventory.switch_deleted",
                    "switch_inventory",
                    str(record["id"]),
                    {
                        "outcome": "success",
                        "summary": f"Deleted switch record {record['name']} ({record['ip']}).",
                        "inventory_type": record["inventory_type"],
                        "name": record["name"],
                        "ip": record["ip"],
                        "city": record["city"],
                        "area": record["area"],
                        "site": record["site"],
                    },
                )
                flash("Switch record deleted.", "success")
                return redirect(url_for("admin.switches"))
            except Exception as exc:
                page_feedback = {
                    "tone": "danger",
                    "title": "Delete failed",
                    "message": str(exc),
                }
                audit_service.log_event(
                    "inventory.switch_delete_rejected",
                    "switch_inventory",
                    request.form.get("switch_id", "") or None,
                    {
                        "outcome": "failed",
                        "summary": str(exc),
                        "switch_id": request.form.get("switch_id", ""),
                    },
                )

    all_records = list_inventory()
    pager = paginate_items(all_records, parse_page(request.args.get("page")), per_page=20)
    inventory_summary = {
        "total": len(all_records),
        "ultra": sum(1 for item in all_records if item["inventory_type"] == "ultra"),
        "ht": sum(1 for item in all_records if item["inventory_type"] == "ht"),
    }
    return render_template(
        "admin/switches.html",
        records=pager["items"],
        form_data=form_data,
        form_errors=form_errors,
        page_feedback=page_feedback,
        pager=pager,
        inventory_summary=inventory_summary,
    )


@bp.route("/users", methods=["GET", "POST"])
@role_required("admin")
def users():
    form_data = _default_user_form_data()
    form_errors: dict[str, str] = {}
    page_feedback = None

    if request.method == "POST":
        action = request.form.get("action", "create")
        if action == "create":
            form_data.update(
                {
                    "username": request.form.get("username", ""),
                    "role": request.form.get("role", "viewer"),
                    "ui_preference": request.form.get("ui_preference", "dark"),
                    "password": request.form.get("password", ""),
                }
            )
            try:
                cleaned = validate_user_payload(form_data)
                new_id = user_service.create_user(
                    cleaned["username"],
                    cleaned["password"],
                    cleaned["role"],
                    cleaned["ui_preference"],
                )
                audit_service.log_event(
                    "auth.user_created",
                    "user",
                    str(new_id),
                    {
                        "outcome": "success",
                        "summary": f"Created {cleaned['role']} user {cleaned['username']}.",
                        "username": cleaned["username"],
                        "role": cleaned["role"],
                        "ui_preference": cleaned["ui_preference"],
                    },
                )
                flash("User created.", "success")
                return redirect(url_for("admin.users"))
            except FormValidationError as exc:
                form_errors = exc.field_errors
                page_feedback = {"tone": "warning", "title": "Validation error", "message": str(exc)}
                audit_service.log_event(
                    "auth.user_create_rejected",
                    "user",
                    None,
                    {
                        "outcome": "validation_error",
                        "summary": str(exc),
                        "attempted": {key: form_data.get(key, "") for key in ("username", "role", "ui_preference")},
                        "field_errors": form_errors,
                    },
                )
            except Exception as exc:
                page_feedback = {
                    "tone": "danger",
                    "title": "User creation failed",
                    "message": str(exc),
                }
                audit_service.log_event(
                    "auth.user_create_failed",
                    "user",
                    None,
                    {
                        "outcome": "failed",
                        "summary": str(exc),
                        "attempted": {key: form_data.get(key, "") for key in ("username", "role", "ui_preference")},
                    },
                )
        elif action in {"activate", "deactivate"}:
            try:
                user_id = validate_positive_int(request.form.get("user_id", ""), "user")
                if request.environ.get("current_user_id") == user_id and action == "deactivate":
                    raise ValueError("You cannot deactivate your own account.")
                user = user_service.set_user_active(user_id, action == "activate")
                if not user:
                    raise ValueError("That user no longer exists.")
                state_label = "activated" if action == "activate" else "deactivated"
                audit_service.log_event(
                    f"auth.user_{state_label}",
                    "user",
                    str(user["id"]),
                    {
                        "outcome": "success",
                        "summary": f"User {user['username']} was {state_label}.",
                        "username": user["username"],
                        "role": user["role"],
                        "is_active": user["is_active"],
                    },
                )
                flash(f"User {state_label}.", "success")
                return redirect(url_for("admin.users"))
            except Exception as exc:
                page_feedback = {
                    "tone": "danger",
                    "title": "User update failed",
                    "message": str(exc),
                }
                audit_service.log_event(
                    "auth.user_update_rejected",
                    "user",
                    request.form.get("user_id", "") or None,
                    {
                        "outcome": "failed",
                        "summary": str(exc),
                        "user_id": request.form.get("user_id", ""),
                        "action": action,
                    },
                )
        elif action == "delete":
            try:
                user_id = validate_positive_int(request.form.get("user_id", ""), "user")
                if request.environ.get("current_user_id") == user_id:
                    raise ValueError("You cannot delete your own account.")
                user = user_service.get_user_by_id(user_id)
                if not user:
                    raise ValueError("That user no longer exists.")
                if user["is_active"]:
                    raise ValueError("Disable the user before deleting the account.")
                deleted_user = user_service.delete_user(user_id)
                if not deleted_user:
                    raise ValueError("That user no longer exists.")
                audit_service.log_event(
                    "auth.user_deleted",
                    "user",
                    str(deleted_user["id"]),
                    {
                        "outcome": "success",
                        "summary": f"Deleted disabled user {deleted_user['username']}.",
                        "username": deleted_user["username"],
                        "role": deleted_user["role"],
                        "is_active": deleted_user["is_active"],
                    },
                )
                flash("User deleted.", "success")
                return redirect(url_for("admin.users"))
            except Exception as exc:
                page_feedback = {
                    "tone": "danger",
                    "title": "User delete failed",
                    "message": str(exc),
                }
                audit_service.log_event(
                    "auth.user_delete_rejected",
                    "user",
                    request.form.get("user_id", "") or None,
                    {
                        "outcome": "failed",
                        "summary": str(exc),
                        "user_id": request.form.get("user_id", ""),
                        "action": action,
                    },
                )

    all_users = user_service.list_users()
    pager = paginate_items(all_users, parse_page(request.args.get("page")), per_page=20)
    user_summary = {
        "total": len(all_users),
        "active": sum(1 for item in all_users if item["is_active"]),
        "viewers": sum(1 for item in all_users if item["role"] == "viewer"),
        "operators": sum(1 for item in all_users if item["role"] == "operator"),
        "admins": sum(1 for item in all_users if item["role"] == "admin"),
    }
    return render_template(
        "admin/users.html",
        users=pager["items"],
        form_data=form_data,
        form_errors=form_errors,
        page_feedback=page_feedback,
        pager=pager,
        user_summary=user_summary,
    )
