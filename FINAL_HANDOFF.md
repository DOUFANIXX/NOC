# Final Project Handoff Report

## 1. Executive Summary

This repository has been refactored from a loose collection of Flask utilities into a unified internal Network Operations Console for:

- Cambium subscriber inventory
- Ubiquiti subscriber inventory
- Huawei switch port inspection
- Safe switch description and enable workflows
- Switch inventory administration
- Background scan scheduling and visibility
- Auditability and operational traceability

The app is now suitable for a controlled internal pilot as a single-instance deployment behind an internal reverse proxy. The core domain logic was preserved where it was useful, while the platform around it was heavily rebuilt for security, maintainability, and operator confidence.

Current maturity:

- good for internal pilot
- good for single-node internal deployment
- not yet a high-availability or multi-node production platform

## 2. Final Architecture Overview

### Application shape

- Unified Flask app with app factory: [app/__init__.py](</c:/Users/Mohamed/Flutter/doufani/app/__init__.py>)
- Main runtime entrypoint: [run.py](</c:/Users/Mohamed/Flutter/doufani/run.py>)
- Alternative WSGI entrypoint: [wsgi.py](</c:/Users/Mohamed/Flutter/doufani/wsgi.py>)

### Main layers

- Routes: `app/routes/`
- Services: `app/services/`
- Templates: `app/templates/`
- Static assets: `app/static/`
- Schemas/models: `app/models/`
- Utilities: `app/utils/`
- Config: `config/`
- Docs: `docs/`
- Tests: `tests/`

### Runtime/data choices

- SQLite for:
  - users
  - devices
  - switch inventory
  - jobs
  - audit logs
- In-process job execution via `ThreadPoolExecutor`
- Scheduler thread for recurring scans
- Environment-driven runtime configuration from `.env`
- Tracked configuration files under `config/`

### UI/design source

- Shared Stitch-based shell and page direction preserved in [stitch/](</c:/Users/Mohamed/Flutter/doufani/stitch>)

## 3. What Changed Across Milestones 1-5

### Milestone 1: Security and Config Foundation

- Removed hardcoded secrets from source
- Moved runtime settings to environment/config
- Added `.env.example`
- Added `.gitignore`
- Disabled Flask debug usage in startup
- Added proxy/cookie/deployment safety toggles
- Wrote security notes and secret rotation guidance

### Milestone 2: Unified App Structure

- Consolidated into one unified Flask app
- Standardized shared shell/layout around the Stitch direction
- Added shared UI macros/components
- Added missing audit and settings surfaces
- Preserved route behavior and device logic

### Milestone 3: Safe Operations

- Hardened `/switches/change`
- Added staged preview + confirmation flow
- Improved form validation and inline feedback
- Improved permission-aware UX
- Enriched audit data for switch changes, inventory edits, and manual scans

### Milestone 4: Page-Level UX Refinement

- Polished:
  - dashboard
  - inventory pages
  - switch inspection
  - switch write workflow
  - switch admin
  - audit log
  - settings
- Added stronger state presentation:
  - stale/current signals
  - workflow stepper
  - action tiles
  - denser operator tables
  - clearer context rails

### Milestone 5: Production Readiness

- Improved jobs/status visibility
- Added structured request-aware logging
- Added readiness endpoint
- Fixed full unittest temp-directory reliability
- Improved docs and CI readiness
- Preserved and committed `stitch/` as design source

## 4. Security Changes Made

- Removed hardcoded device and switch credentials from source
- Moved secrets into env/config
- Added authenticated access requirement
- Added role-aware access:
  - `viewer`
  - `operator`
  - `admin`
- Added CSRF protection for POST actions
- Protected write/admin routes
- Added audit logging for:
  - sign-in/sign-out
  - manual scans
  - switch inventory edits
  - switch port changes
  - permission denials
- Added request-aware logging without rendering secrets
- Added readiness probe for deployment checks

See also: [SECURITY_NOTES.md](</c:/Users/Mohamed/Flutter/doufani/SECURITY_NOTES.md>)

## 5. Current Feature Set

### Inventory

- Cambium subscriber inventory
- Ubiquiti subscriber inventory
- searchable/filterable tables
- last-success visibility
- stale-state visibility
- manual scan triggers for operator/admin

### Switch operations

- Ultra switch inspection
- HT switch inspection
- safe write workflow for:
  - port description
  - optional `undo shutdown`
- preview before apply
- acknowledgement before apply
- stale-preview rejection

### Administration

- switch inventory add/delete
- role-gated admin access
- audited inventory edits

### Operational visibility

- dashboard with summary cards and quick actions
- jobs page with queue/running/failure visibility
- audit log
- settings/config visibility page

## 6. Deployment Steps for Internal Pilot

1. Clone the branch you intend to deploy.
2. Create a Python virtual environment.
3. Install dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env`.
5. Fill in real credentials and production-safe settings.
6. Verify tracked config files:
   - `config/scan_targets.json`
   - `config/switch_inventory.seed.json`
   - `config/ht_switch_inventory.seed.json`
7. Start the app:

   ```powershell
   python run.py
   ```

8. Put it behind the internal reverse proxy.
9. Verify:
   - `/healthz`
   - `/readyz`
10. Sign in with the bootstrap admin.
11. Rotate bootstrap credentials.
12. Run a controlled pilot using the test plan in [PILOT_TEST_PLAN.md](</c:/Users/Mohamed/Flutter/doufani/PILOT_TEST_PLAN.md>)

## 7. Required Environment Variables and Config Notes

Primary variables from [.env.example](</c:/Users/Mohamed/Flutter/doufani/.env.example>):

- `APP_NAME`
- `HOST`
- `PORT`
- `SECRET_KEY`
- `PREFERRED_URL_SCHEME`
- `SESSION_COOKIE_SAMESITE`
- `SESSION_COOKIE_SECURE`
- `TRUST_PROXY`
- `APP_CONFIG_DIR`
- `INSTANCE_PATH`
- `LOG_LEVEL`
- `CAMBIUM_USERNAME`
- `CAMBIUM_PASSWORD`
- `UBIQUITI_USERNAME`
- `UBIQUITI_PASSWORD`
- `ULTRA_SWITCH_USERNAME`
- `ULTRA_SWITCH_PASSWORD`
- `HT_SWITCH_USERNAME`
- `HT_SWITCH_PASSWORD`
- `BOOTSTRAP_ADMIN_USERNAME`
- `BOOTSTRAP_ADMIN_PASSWORD`
- `BOOTSTRAP_ADMIN_ROLE`
- `PLAYWRIGHT_HEADLESS`
- `SCHEDULER_ENABLED`
- `CAMBIUM_SCAN_INTERVAL_MINUTES`
- `UBIQUITI_SCAN_INTERVAL_MINUTES`
- `SCHEDULER_TICK_SECONDS`
- `JOB_MAX_WORKERS`
- `JOB_FAILURE_SAMPLE_LIMIT`
- `STALE_SCAN_THRESHOLD_MINUTES`

Config notes:

- `config/scan_targets.json` is sensitive infrastructure metadata
- switch inventory seed files are tracked config, not secrets
- `INSTANCE_PATH` contains runtime DB, logs, and generated local secrets/bootstrap artifacts

## 8. Admin/Bootstrap Steps

1. Set `BOOTSTRAP_ADMIN_PASSWORD` in `.env`, or let the app generate one.
2. Start the app.
3. If generated automatically, read the bootstrap password from:
   - `instance/bootstrap_admin.txt`
4. Sign in as the bootstrap admin.
5. Confirm admin-only surfaces load:
   - `/admin/switches`
   - `/settings/`
   - `/audit/`
6. Rotate bootstrap credentials immediately for pilot use.

## 9. Health/Readiness Endpoints and How to Verify Them

### Liveness

- `GET /healthz`
- Expected response:

  ```json
  {"status":"ok"}
  ```

### Readiness

- `GET /readyz`
- Checks:
  - database connectivity
  - scan target file presence
  - Ultra seed file presence
  - HT seed file presence

Expected healthy response:

```json
{
  "status": "ready",
  "checks": {
    "database": true,
    "scan_targets": true,
    "switch_inventory_seed": true,
    "ht_switch_inventory_seed": true
  }
}
```

Verification example:

```powershell
Invoke-WebRequest http://127.0.0.1:8080/healthz
Invoke-WebRequest http://127.0.0.1:8080/readyz
```

## 10. Logging/Audit Behavior Summary

### Application logging

- Rotating file log:
  - `instance/logs/noc-console.log`
- Request-aware fields include:
  - request id
  - actor
  - method/path
  - remote address
- Job queue/start/success/failure now log more clearly
- 500 errors get a request reference id for operator support

### Audit behavior

Audit logs capture:

- sign-in/sign-out
- permission denials
- manual scan triggers/rejections/completions/failures
- switch inventory add/delete
- switch write preview rejection/discard/apply/failure

Audit data includes useful context such as:

- actor
- action
- outcome
- summary
- target/switch/site
- changed values where practical

## 11. Test/CI Summary

### Local test command

```powershell
python -m unittest discover -s tests -v
```

### Current state

- Full test suite passes
- Tests now use workspace-local `.tmp-tests/`
- CI workflow exists at [.github/workflows/ci.yml](</c:/Users/Mohamed/Flutter/doufani/.github/workflows/ci.yml>)

Current automated coverage includes:

- app creation
- health endpoint
- readiness endpoint
- login page
- jobs page
- audit page
- settings page
- validation helpers

## 12. Backup/Recovery Recommendations

For pilot operations, back up:

- `instance/noc_console.sqlite3` or configured database path
- `config/scan_targets.json`
- `config/switch_inventory.seed.json`
- `config/ht_switch_inventory.seed.json`
- `.env` or the external secret source equivalent
- `instance/logs/`

Recovery recommendations:

1. Stop the app
2. Restore DB/config/env
3. Verify `/readyz`
4. Sign in with admin account
5. Run a controlled manual scan
6. Confirm jobs/audit pages show normal behavior

## 13. Known Limitations / Remaining Risks

- SQLite is not a multi-node datastore
- Jobs are still in-process, not separate workers
- No high-availability or failover design yet
- No user-management UI or password reset UI yet
- No MFA
- Real device integrations still depend on live infrastructure behavior
- No end-to-end device integration test harness
- Switch inventory admin is still add/delete, not full lifecycle editing/versioning

## 14. Recommended Phase 2 Roadmap

1. Add user management, password rotation, and optional MFA
2. Move background jobs to a dedicated worker queue if scale/reliability demands it
3. Expand switch inventory administration to full edit/version/history
4. Add richer inventory lifecycle handling:
   - stale device aging
   - exports
   - better normalization
5. Add deeper automated coverage:
   - route permission tests
   - job execution tests
   - service-layer fault handling tests
6. Add centralized logging/shipping and retention controls
7. Plan for stronger deployment topology if the pilot expands

## Reference Commits

- Milestone 1: `87e24b2`
- Milestone 2: `ab9d590`
- Milestone 3: `910791b`
- Milestone 4: `99d4410`
- Milestone 5: `7605b96`
