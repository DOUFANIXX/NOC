from __future__ import annotations

import re


PORT_PREFIXES = ["GigabitEthernet0/0", "GE1/0"]


class DeviceWorkflowError(RuntimeError):
    pass


class DeviceConnectionError(DeviceWorkflowError):
    pass


class DeviceCommandError(DeviceWorkflowError):
    pass


def _credentials_for(config: dict, inventory_type: str) -> tuple[str, str]:
    if inventory_type == "ultra":
        return config["ULTRA_SWITCH_USERNAME"], config["ULTRA_SWITCH_PASSWORD"]
    return config["HT_SWITCH_USERNAME"], config["HT_SWITCH_PASSWORD"]


def _connect(config: dict, inventory_type: str, ip: str):
    username, password = _credentials_for(config, inventory_type)
    if not username or not password:
        raise DeviceConnectionError(f"{inventory_type.upper()} switch credentials are not configured.")

    try:
        from netmiko import ConnectHandler

        return ConnectHandler(
            device_type="huawei",
            ip=ip,
            username=username,
            password=password,
            conn_timeout=40,
            fast_cli=False,
        )
    except Exception as exc:
        raise DeviceConnectionError(
            f"Unable to connect to switch {ip}. Verify reachability and the configured credentials."
        ) from exc


def build_port_change_commands(port: str, description: str, enable_port: bool) -> list[str]:
    commands = [f"interface {port}", f"description {description}"]
    if enable_port:
        commands.append("undo shutdown")
    commands.append("quit")
    return commands


def _normalized_port_status(output: str, port: str) -> str:
    state_match = re.search(rf"{re.escape(port)}\s+current state\s*:\s*(\w+)", output)
    return state_match.group(1) if state_match else "Unknown"


def _normalized_port_speed(output: str, status: str) -> str:
    if "down" in status.strip().lower():
        return "N/A"
    speed_match = re.search(r"Speed\s*:\s*(\d+)", output)
    return speed_match.group(1) if speed_match else "Unknown"


def inspect_described_ports(config: dict, inventory_type: str, ip: str) -> list[dict]:
    results = []
    with _connect(config, inventory_type, ip) as connection:
        try:
            for prefix in PORT_PREFIXES:
                for index in range(1, 50):
                    port = f"{prefix}/{index}"
                    output = str(connection.send_command(f"display interface {port}", use_textfsm=False))
                    description = ""
                    for line in output.splitlines():
                        match = re.search(r"Description\s*:\s*(.*)", line, re.IGNORECASE)
                        if match:
                            description = match.group(1).strip()
                            break
                    if not description or description.lower() in {"n/a", "-", "â€”", "--", "null"}:
                        continue
                    status = _normalized_port_status(output, port)
                    results.append(
                        {
                            "port": port,
                            "status": status,
                            "speed": _normalized_port_speed(output, status),
                            "description": description,
                        }
                    )
        except Exception as exc:
            raise DeviceCommandError(
                f"Connected to switch {ip}, but the inspection command failed before results could be collected."
            ) from exc
    return results


def inspect_open_ports(config: dict, inventory_type: str, ip: str) -> list[str]:
    open_ports = []
    with _connect(config, inventory_type, ip) as connection:
        try:
            output = str(connection.send_command("display interface brief", use_textfsm=False))
            lines = output.splitlines()
            start = 0
            for idx, line in enumerate(lines):
                if line.strip().startswith("Interface"):
                    start = idx + 1
                    break
            candidates = []
            for line in lines[start:]:
                parts = line.split()
                if not parts:
                    continue
                interface_name = parts[0]
                if interface_name.startswith("GigabitEthernet") or interface_name.startswith("GE"):
                    candidates.append(interface_name)

            for port in candidates:
                detail = str(connection.send_command(f"display interface {port}", use_textfsm=False))
                description = ""
                for line in detail.splitlines():
                    if "Description" in line:
                        description = line.split(":", 1)[1].strip() if ":" in line else ""
                        break
                if description == "" or description.lower() in {"--", "null", "n/a", "-", "â€”"}:
                    open_ports.append(port)
        except Exception as exc:
            raise DeviceCommandError(
                f"Connected to switch {ip}, but the available-port lookup failed before it could complete."
            ) from exc
    return open_ports


def apply_port_change(
    config: dict,
    inventory_type: str,
    ip: str,
    port: str,
    description: str,
    enable_port: bool,
) -> list[str]:
    commands = build_port_change_commands(port, description, enable_port)

    with _connect(config, inventory_type, ip) as connection:
        try:
            connection.send_config_set(commands)
        except Exception as exc:
            raise DeviceCommandError(
                f"Connected to switch {ip}, but the configuration change for port {port} did not complete."
            ) from exc
    return commands
