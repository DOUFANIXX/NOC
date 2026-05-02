from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from flask import current_app

from app.services import audit_service, jobs_service
from app.services.cambium_service import run_scan as run_cambium_scan
from app.services.inventory_service import upsert_devices
from app.services.scan_schedule_service import get_schedule, should_enqueue_scheduled_scan
from app.services.scan_target_service import load_target_records, load_targets
from app.services.sector_target_service import upsert_sector_targets
from app.services.ubiquiti_service import ScanAborted, run_scan as run_ubiquiti_scan


class JobManager:
    def __init__(self, app):
        self.app = app
        self.executor = ThreadPoolExecutor(max_workers=app.config["JOB_MAX_WORKERS"])
        self._vendor_condition = threading.Condition()
        self._active_vendor_jobs: dict[str, int] = {}

    def enqueue_scan(self, vendor: str, requested_by: int | None, trigger_source: str = "manual") -> tuple[bool, int]:
        with self.app.app_context():
            if jobs_service.is_scan_running(vendor):
                existing = jobs_service.list_recent_jobs(limit=1)
                return False, existing[0]["id"] if existing else 0
            job_id = jobs_service.create_job("scan", vendor, trigger_source, requested_by)
            self.app.logger.info(
                "Queued scan job #%s for vendor=%s trigger=%s requested_by=%s",
                job_id,
                vendor,
                trigger_source,
                requested_by or "system",
            )

        self.executor.submit(self._run_scan_job, job_id, vendor)
        return True, job_id

    def restart_scan(
        self,
        vendor: str,
        requested_by: int | None,
        trigger_source: str = "manual",
    ) -> tuple[int, list[int]]:
        with self.app.app_context():
            job_id = jobs_service.create_job("scan", vendor, trigger_source, requested_by)
            replaced_job_ids = jobs_service.cancel_scan_jobs(
                vendor,
                message=f"{vendor.title()} scan restart requested. A newer scan has been queued.",
                meta={"replacement_job_id": job_id, "outcome": "superseded"},
                exclude_job_id=job_id,
            )
            self.app.logger.info(
                "Queued replacement scan job #%s for vendor=%s trigger=%s requested_by=%s superseding=%s",
                job_id,
                vendor,
                trigger_source,
                requested_by or "system",
                replaced_job_ids,
            )

        self.executor.submit(self._run_scan_job, job_id, vendor)
        return job_id, replaced_job_ids

    def _run_scan_job(self, job_id: int, vendor: str) -> None:
        with self.app.app_context():
            if not self._claim_vendor_slot(vendor, job_id):
                if jobs_service.is_job_canceled(job_id):
                    jobs_service.finalize_canceled_job(job_id)
                self.app.logger.info(
                    "Skipping scan job #%s for vendor=%s because it is no longer active.",
                    job_id,
                    vendor,
                )
                return

            if not jobs_service.mark_job_running(job_id):
                self.app.logger.info(
                    "Skipping scan job #%s for vendor=%s because it never entered running state.",
                    job_id,
                    vendor,
                )
                self._release_vendor_slot(vendor, job_id)
                return

            target_records = load_target_records(self.app.config["SCAN_TARGETS_FILE"]).get(vendor, [])
            targets = [item["ip"] for item in target_records]
            self.app.logger.info(
                "Starting scan job #%s for vendor=%s target_count=%s",
                job_id,
                vendor,
                len(targets),
            )
            try:
                if vendor == "cambium":
                    scan_result = run_cambium_scan(self.app.config, target_records)
                else:
                    scan_result = run_ubiquiti_scan(
                        self.app.config,
                        targets,
                        should_abort=lambda: jobs_service.is_job_canceled(job_id),
                    )

                if jobs_service.is_job_canceled(job_id):
                    jobs_service.finalize_canceled_job(
                        job_id,
                        f"{vendor.title()} scan stopped before import because a replacement scan was requested.",
                    )
                    self.app.logger.info(
                        "Canceled scan job #%s for vendor=%s before import completed.",
                        job_id,
                        vendor,
                    )
                    return

                captured_sectors = upsert_sector_targets(vendor, scan_result.sector_targets)
                processed = upsert_devices(vendor, scan_result.devices)
                meta = {
                    "processed": processed,
                    "captured_sectors": captured_sectors,
                    "targets": len(targets),
                    "successful_targets": scan_result.successful_targets,
                    "failed_targets": len(scan_result.failed_targets),
                    "failure_samples": scan_result.failed_targets[: self.app.config["JOB_FAILURE_SAMPLE_LIMIT"]],
                }
                jobs_service.mark_job_finished(
                    job_id,
                    status="success",
                    message=_success_message(vendor, processed, scan_result.failed_targets),
                    meta=meta,
                )
                self.app.logger.info(
                    "Completed scan job #%s for vendor=%s processed=%s successful_targets=%s failed_targets=%s",
                    job_id,
                    vendor,
                    processed,
                    scan_result.successful_targets,
                    len(scan_result.failed_targets),
                )
                audit_service.log_event(
                    action="scan.completed",
                    resource_type="job",
                    resource_id=str(job_id),
                    details={
                        "vendor": vendor,
                        "processed": processed,
                        "captured_sectors": captured_sectors,
                        "targets": len(targets),
                        "successful_targets": scan_result.successful_targets,
                        "failed_targets": len(scan_result.failed_targets),
                        "summary": _success_message(vendor, processed, scan_result.failed_targets),
                        "outcome": "success",
                    },
                )
            except ScanAborted:
                jobs_service.finalize_canceled_job(
                    job_id,
                    f"{vendor.title()} scan stopped so a replacement scan could start.",
                )
                self.app.logger.info(
                    "Stopped scan job #%s for vendor=%s because a replacement was requested.",
                    job_id,
                    vendor,
                )
            except Exception as exc:
                current_app.logger.exception("Background scan failed for %s", vendor)
                failure_message = _failure_message(vendor, exc)
                jobs_service.mark_job_finished(
                    job_id,
                    status="failed",
                    message=failure_message,
                    meta={
                        "targets": len(targets),
                        "error_class": exc.__class__.__name__,
                    },
                )
                audit_service.log_event(
                    action="scan.failed",
                    resource_type="job",
                    resource_id=str(job_id),
                    details={
                        "vendor": vendor,
                        "targets": len(targets),
                        "outcome": "failed",
                        "summary": failure_message,
                        "error_class": exc.__class__.__name__,
                    },
                )
            finally:
                self._release_vendor_slot(vendor, job_id)

    def _claim_vendor_slot(self, vendor: str, job_id: int) -> bool:
        with self._vendor_condition:
            while True:
                if not jobs_service.is_job_active(job_id):
                    return False
                active_job_id = self._active_vendor_jobs.get(vendor)
                if active_job_id is None:
                    self._active_vendor_jobs[vendor] = job_id
                    return True
                if active_job_id == job_id:
                    return True
                self._vendor_condition.wait(timeout=0.25)

    def _release_vendor_slot(self, vendor: str, job_id: int) -> None:
        with self._vendor_condition:
            if self._active_vendor_jobs.get(vendor) == job_id:
                self._active_vendor_jobs.pop(vendor, None)
                self._vendor_condition.notify_all()


def scan_ready(app, vendor: str) -> bool:
    return scan_readiness(app, vendor)["ready"]


def scan_readiness(app, vendor: str) -> dict:
    targets = load_targets(app.config["SCAN_TARGETS_FILE"]).get(vendor, [])
    running = jobs_service.is_scan_running(vendor)
    if vendor == "cambium":
        credentials_configured = bool(app.config["CAMBIUM_USERNAME"] and app.config["CAMBIUM_PASSWORD"])
    else:
        credentials_configured = bool(app.config["UBIQUITI_USERNAME"] and app.config["UBIQUITI_PASSWORD"])

    ready = bool(targets) and credentials_configured and not running
    if running:
        reason = f"A {vendor} scan is already queued or running."
    elif not targets:
        reason = f"No {vendor} scan targets are configured."
    elif not credentials_configured:
        reason = f"{vendor.title()} scan credentials are missing from the runtime configuration."
    else:
        reason = f"{vendor.title()} manual scan is ready."

    return {
        "vendor": vendor,
        "ready": ready,
        "running": running,
        "restartable": running and bool(targets) and credentials_configured,
        "reason": reason,
        "targets": len(targets),
        "credentials_configured": credentials_configured,
    }


def _success_message(vendor: str, processed: int, failed_targets: list[dict]) -> str:
    if failed_targets:
        return (
            f"{vendor.title()} scan finished with partial coverage: {processed} rows imported and "
            f"{len(failed_targets)} target failures."
        )
    return f"{vendor.title()} scan completed successfully with {processed} imported rows."


def _failure_message(vendor: str, exc: Exception) -> str:
    return f"{vendor.title()} scan failed before import completed: {exc}"


class SchedulerThread(threading.Thread):
    def __init__(self, app, manager: JobManager):
        super().__init__(daemon=True)
        self.app = app
        self.manager = manager
        self.stop_event = threading.Event()

    def run(self) -> None:
        while not self.stop_event.is_set():
            with self.app.app_context():
                if self.app.config["SCHEDULER_ENABLED"]:
                    cambium_schedule = get_schedule("cambium")
                    ubiquiti_schedule = get_schedule("ubiquiti")

                    if scan_ready(self.app, "cambium") and (
                        should_enqueue_scheduled_scan("cambium")
                        if cambium_schedule["enabled"] and cambium_schedule["daily_time"]
                        else jobs_service.should_schedule("cambium", self.app.config["CAMBIUM_SCAN_INTERVAL_MINUTES"])
                    ):
                        self.manager.enqueue_scan("cambium", None, trigger_source="scheduler")
                    if scan_ready(self.app, "ubiquiti") and (
                        should_enqueue_scheduled_scan("ubiquiti")
                        if ubiquiti_schedule["enabled"] and ubiquiti_schedule["daily_time"]
                        else jobs_service.should_schedule("ubiquiti", self.app.config["UBIQUITI_SCAN_INTERVAL_MINUTES"])
                    ):
                        self.manager.enqueue_scan("ubiquiti", None, trigger_source="scheduler")
            self.stop_event.wait(self.app.config["SCHEDULER_TICK_SECONDS"])

    def stop(self) -> None:
        self.stop_event.set()
