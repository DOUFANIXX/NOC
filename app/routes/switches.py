from __future__ import annotations

from datetime import timedelta

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from app.models.schemas import SwitchChangeDraft
from app.services import audit_service
from app.services.switch_inventory_service import get_grouped_inventory, get_switch_record
from app.services.switch_service import (
    DeviceCommandError,
    DeviceConnectionError,
    apply_port_change,
    build_port_change_commands,
    inspect_described_ports,
    inspect_open_ports,
)
from app.utils.auth import login_required, role_required
from app.utils.helpers import paginate_items, parse_page, parse_timestamp, utcnow, utcnow_iso
from app.utils.validation import (
    FormValidationError,
    normalize_inventory_type,
    validate_description,
    validate_port_name,
    validate_positive_int,
)


bp = Blueprint("switches", __name__, url_prefix="/switches")
PREVIEW_MAX_AGE = timedelta(minutes=5)


@bp.route("/<inventory_type>", methods=["GET", "POST"])
@login_required
def inspect(inventory_type: str):
    normalized = normalize_inventory_type(inventory_type)
    grouped = get_grouped_inventory(normalized)
    selected_switch_id = request.form.get("switch_id") if request.method == "POST" else request.args.get("switch_id")
    selected_record = None
    form_errors: dict[str, str] = {}
    results = []

    if selected_switch_id:
        try:
            switch_id = validate_positive_int(selected_switch_id, "switch")
            selected_record = get_switch_record(switch_id)
            if not selected_record:
                raise FormValidationError("Choose a switch that still exists in the current inventory.", {"switch_id": "Select a valid switch."})
        except (ValueError, FormValidationError) as exc:
            form_errors["switch_id"] = exc.field_errors.get("switch_id", str(exc)) if isinstance(exc, FormValidationError) else str(exc)
            flash(f"Validation error: {form_errors['switch_id']}", "warning")

    if selected_record and (request.method == "POST" or request.args.get("switch_id")):
        try:
            results = inspect_described_ports(current_app.config, normalized, selected_record["ip"])
        except DeviceConnectionError as exc:
            flash(f"Connection failure: {exc}", "danger")
        except DeviceCommandError as exc:
            flash(f"Inspection command failed: {exc}", "danger")
        except Exception:
            current_app.logger.exception("Unexpected switch inspection failure for %s", selected_record["ip"])
            flash("Unexpected inspection failure. Check the switch and try again.", "danger")

    pager = paginate_items(results, parse_page(request.args.get("page")), per_page=20) if results else paginate_items([], 1, per_page=20)

    return render_template(
        "switches/inspect.html",
        inventory_type=normalized,
        grouped=grouped,
        selected_record=selected_record,
        results=pager["items"],
        form_errors=form_errors,
        pager=pager,
    )


@bp.route("/change", methods=["GET", "POST"])
@role_required("operator", "admin")
def change():
    inventory_type = normalize_inventory_type(request.values.get("inventory_type", "ultra"))
    grouped = get_grouped_inventory(inventory_type)
    available_ports = []
    form_errors: dict[str, str] = {}
    workflow_feedback = None
    form_data = {
        "inventory_type": inventory_type,
        "switch_id": request.form.get("switch_id") or request.args.get("switch_id") or "",
        "port": request.form.get("port", ""),
        "description": request.form.get("description", ""),
        "enable_port": request.form.get("enable_port") == "on" if request.method == "POST" else True,
    }

    pending = session.get("pending_switch_change")
    if pending and pending.get("inventory_type") != inventory_type:
        session.pop("pending_switch_change", None)
        pending = None

    record = _resolve_switch_record(form_data["switch_id"], form_errors)
    pending_context = _build_pending_context(pending)

    if request.method == "POST":
        action = request.form.get("action", "load")
        if action == "load":
            try:
                if not record:
                    raise FormValidationError("Choose a switch before loading ports.", {"switch_id": "Select a valid switch."})
                available_ports = inspect_open_ports(current_app.config, inventory_type, record["ip"])
                workflow_feedback = {
                    "tone": "success" if available_ports else "warning",
                    "title": "Port inventory loaded" if available_ports else "No eligible ports found",
                    "message": (
                        f"Loaded {len(available_ports)} undocumented ports from {record['name']}."
                        if available_ports
                        else "The switch responded, but no undocumented ports are currently available for this workflow."
                    ),
                }
            except FormValidationError as exc:
                form_errors.update(exc.field_errors)
                workflow_feedback = {"tone": "warning", "title": "Validation error", "message": str(exc)}
            except DeviceConnectionError as exc:
                workflow_feedback = {"tone": "danger", "title": "Connection failure", "message": str(exc)}
            except DeviceCommandError as exc:
                workflow_feedback = {"tone": "danger", "title": "Device command failure", "message": str(exc)}
            except Exception:
                current_app.logger.exception("Unexpected change workflow load failure")
                workflow_feedback = {"tone": "danger", "title": "Unexpected failure", "message": "The switch could not be queried for available ports."}

        elif action == "preview":
            try:
                if not record:
                    raise FormValidationError("Choose a switch before staging a change.", {"switch_id": "Select a valid switch."})
                available_ports = inspect_open_ports(current_app.config, inventory_type, record["ip"])
                port = validate_port_name(request.form.get("port", ""))
                if port not in available_ports:
                    raise FormValidationError(
                        "Selected port is no longer eligible. Refresh and choose another port.",
                        {"port": "Port availability changed. Load ports again."},
                    )
                description = validate_description(request.form.get("description", ""))
                commands = build_port_change_commands(port, description, request.form.get("enable_port") == "on")
                draft = SwitchChangeDraft(
                    inventory_type=inventory_type,
                    switch_id=record["id"],
                    switch_name=record["name"],
                    switch_ip=record["ip"],
                    port=port,
                    description=description,
                    enable_port=request.form.get("enable_port") == "on",
                    location=_switch_location(record),
                    previewed_at=utcnow_iso(),
                    command_preview=commands,
                    summary=_change_summary(record, port, description, request.form.get("enable_port") == "on"),
                    risk_level="moderate" if request.form.get("enable_port") == "on" else "low",
                )
                session["pending_switch_change"] = draft.__dict__
                pending = draft.__dict__
                pending_context = _build_pending_context(pending)
                form_data["port"] = port
                form_data["description"] = description
                form_data["enable_port"] = request.form.get("enable_port") == "on"
                workflow_feedback = {
                    "tone": "warning",
                    "title": "Preview ready",
                    "message": "Review the command preview, acknowledge the risk, and then confirm the change.",
                }
            except FormValidationError as exc:
                form_errors.update(exc.field_errors)
                workflow_feedback = {"tone": "warning", "title": "Validation error", "message": str(exc)}
            except ValueError as exc:
                message = str(exc)
                field = "description" if "Description" in message else "port"
                form_errors[field] = message
                workflow_feedback = {"tone": "warning", "title": "Validation error", "message": message}
            except DeviceConnectionError as exc:
                workflow_feedback = {"tone": "danger", "title": "Connection failure", "message": str(exc)}
            except DeviceCommandError as exc:
                workflow_feedback = {"tone": "danger", "title": "Device command failure", "message": str(exc)}
            except Exception:
                current_app.logger.exception("Unexpected preview generation failure")
                workflow_feedback = {"tone": "danger", "title": "Unexpected failure", "message": "The change preview could not be generated."}

        elif action == "confirm":
            if not pending:
                workflow_feedback = {
                    "tone": "warning",
                    "title": "No pending change",
                    "message": "No pending change was found. Generate a fresh preview before confirming.",
                }
            else:
                try:
                    _validate_confirmation_ack(request.form.get("confirm_ack"))
                    _validate_pending_age(pending)
                    record = get_switch_record(int(pending["switch_id"]))
                    if not record:
                        raise FormValidationError("The selected switch no longer exists in inventory.", {"switch_id": "Choose a valid switch."})
                    available_ports = inspect_open_ports(current_app.config, pending["inventory_type"], record["ip"])
                    if pending["port"] not in available_ports:
                        raise FormValidationError(
                            "Port state changed before confirmation. Load a fresh preview before applying.",
                            {"confirm_ack": "Preview is no longer safe to apply."},
                        )
                    commands = apply_port_change(
                        current_app.config,
                        pending["inventory_type"],
                        record["ip"],
                        pending["port"],
                        pending["description"],
                        bool(pending["enable_port"]),
                    )
                    audit_service.log_event(
                        action="switch.port_change",
                        resource_type="switch",
                        resource_id=str(record["id"]),
                        details={
                            "outcome": "success",
                            "summary": _change_summary(record, pending["port"], pending["description"], bool(pending["enable_port"])),
                            "inventory_type": pending["inventory_type"],
                            "switch": record["name"],
                            "location": _switch_location(record),
                            "ip": record["ip"],
                            "port": pending["port"],
                            "description": pending["description"],
                            "enable_port": bool(pending["enable_port"]),
                            "previewed_at": pending.get("previewed_at"),
                            "confirmed_at": utcnow_iso(),
                            "command_preview": commands,
                            "risk_level": pending.get("risk_level", "low"),
                        },
                    )
                    session.pop("pending_switch_change", None)
                    flash(f"Successful change: {record['name']} {pending['port']} updated.", "success")
                    return redirect(url_for("switches.change", inventory_type=inventory_type, switch_id=record["id"]))
                except FormValidationError as exc:
                    form_errors.update(exc.field_errors)
                    workflow_feedback = {"tone": "warning", "title": "Validation error", "message": str(exc)}
                    audit_service.log_event(
                        "switch.port_change_rejected",
                        "switch",
                        str(pending.get("switch_id")),
                        {
                            "outcome": "validation_error",
                            "summary": str(exc),
                            "switch": pending.get("switch_name"),
                            "location": pending.get("location"),
                            "ip": pending.get("switch_ip"),
                            "port": pending.get("port"),
                            "description": pending.get("description"),
                            "enable_port": pending.get("enable_port"),
                            "field_errors": form_errors,
                        },
                    )
                except DeviceConnectionError as exc:
                    workflow_feedback = {"tone": "danger", "title": "Connection failure", "message": str(exc)}
                    audit_service.log_event(
                        "switch.port_change_failed",
                        "switch",
                        str(pending.get("switch_id")),
                        {
                            "outcome": "connection_error",
                            "summary": str(exc),
                            "switch": pending.get("switch_name"),
                            "location": pending.get("location"),
                            "ip": pending.get("switch_ip"),
                            "port": pending.get("port"),
                            "description": pending.get("description"),
                            "enable_port": pending.get("enable_port"),
                        },
                    )
                except DeviceCommandError as exc:
                    workflow_feedback = {"tone": "danger", "title": "Device command failure", "message": str(exc)}
                    audit_service.log_event(
                        "switch.port_change_failed",
                        "switch",
                        str(pending.get("switch_id")),
                        {
                            "outcome": "device_error",
                            "summary": str(exc),
                            "switch": pending.get("switch_name"),
                            "location": pending.get("location"),
                            "ip": pending.get("switch_ip"),
                            "port": pending.get("port"),
                            "description": pending.get("description"),
                            "enable_port": pending.get("enable_port"),
                        },
                    )
                except Exception as exc:
                    current_app.logger.exception("Unexpected port change failure")
                    workflow_feedback = {"tone": "danger", "title": "Unexpected failure", "message": "The switch change did not complete."}
                    audit_service.log_event(
                        "switch.port_change_failed",
                        "switch",
                        str(pending.get("switch_id")),
                        {
                            "outcome": "unexpected_error",
                            "summary": str(exc),
                            "switch": pending.get("switch_name"),
                            "location": pending.get("location"),
                            "ip": pending.get("switch_ip"),
                            "port": pending.get("port"),
                            "description": pending.get("description"),
                            "enable_port": pending.get("enable_port"),
                        },
                    )

        elif action == "cancel":
            if pending:
                audit_service.log_event(
                    "switch.port_change_discarded",
                    "switch",
                    str(pending.get("switch_id")),
                    {
                        "outcome": "discarded",
                        "summary": f"Discarded pending change for {pending.get('switch_name')} {pending.get('port')}.",
                        "switch": pending.get("switch_name"),
                        "location": pending.get("location"),
                        "ip": pending.get("switch_ip"),
                        "port": pending.get("port"),
                        "description": pending.get("description"),
                        "enable_port": pending.get("enable_port"),
                    },
                )
            session.pop("pending_switch_change", None)
            pending = None
            pending_context = None
            flash("Pending change discarded.", "warning")

    return render_template(
        "switches/change.html",
        inventory_type=inventory_type,
        grouped=grouped,
        selected_record=record,
        available_ports=available_ports,
        pending=pending,
        pending_context=pending_context,
        form_errors=form_errors,
        workflow_feedback=workflow_feedback,
        form_data=form_data,
    )


def _resolve_switch_record(raw_switch_id: str, form_errors: dict[str, str]) -> dict | None:
    if not raw_switch_id:
        return None
    try:
        switch_id = validate_positive_int(raw_switch_id, "switch")
        record = get_switch_record(switch_id)
        if not record:
            raise FormValidationError("Choose a switch that still exists in the current inventory.", {"switch_id": "Select a valid switch."})
        return record
    except (ValueError, FormValidationError) as exc:
        form_errors["switch_id"] = exc.field_errors.get("switch_id", str(exc)) if isinstance(exc, FormValidationError) else str(exc)
        return None


def _switch_location(record: dict) -> str:
    return " / ".join(part for part in (record.get("city"), record.get("area"), record.get("site")) if part)


def _change_summary(record: dict, port: str, description: str, enable_port: bool) -> str:
    action = "updated description and enabled" if enable_port else "updated description on"
    return f"{action} {record['name']} {port} with description '{description}'."


def _build_pending_context(pending: dict | None) -> dict | None:
    if not pending:
        return None
    preview_dt = parse_timestamp(pending.get("previewed_at"))
    is_stale = preview_dt is None or utcnow() - preview_dt > PREVIEW_MAX_AGE
    return {
        "is_stale": is_stale,
        "expires_in_minutes": int(PREVIEW_MAX_AGE.total_seconds() // 60),
    }


def _validate_confirmation_ack(value: str | None) -> None:
    if value != "on":
        raise FormValidationError(
            "Acknowledge the change intent before confirming.",
            {"confirm_ack": "Tick the acknowledgement box before applying this change."},
        )


def _validate_pending_age(pending: dict) -> None:
    preview_dt = parse_timestamp(pending.get("previewed_at"))
    if preview_dt is None or utcnow() - preview_dt > PREVIEW_MAX_AGE:
        raise FormValidationError(
            f"The preview is stale. Generate a new preview within {int(PREVIEW_MAX_AGE.total_seconds() // 60)} minutes before applying changes.",
            {"confirm_ack": "The staged preview has expired and must be regenerated."},
        )
