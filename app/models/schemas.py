from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SwitchChangeDraft:
    inventory_type: str
    switch_id: int
    switch_name: str
    switch_ip: str
    port: str
    description: str
    enable_port: bool
    location: str = ""
    previewed_at: str = ""
    command_preview: list[str] = field(default_factory=list)
    summary: str = ""
    risk_level: str = "low"


@dataclass
class DashboardCard:
    label: str
    value: str
    status: str
    detail: str


@dataclass
class ScanExecutionResult:
    devices: list[dict] = field(default_factory=list)
    sector_targets: list[dict] = field(default_factory=list)
    attempted_targets: int = 0
    successful_targets: int = 0
    failed_targets: list[dict] = field(default_factory=list)
