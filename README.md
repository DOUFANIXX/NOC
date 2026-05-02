# Network Operations Console

This repository now runs as a unified internal Flask application for network operations workflows:

- Cambium subscriber inventory
- Ubiquiti subscriber inventory
- Huawei switch port inspection
- Huawei switch description/enabling workflows
- Switch inventory administration
- Background scan jobs
- Operational visibility and audit logging

## Handoff / Deployment Docs

- [FINAL_HANDOFF.md](FINAL_HANDOFF.md) - complete architecture, milestone recap, security changes, feature set, risks, and Phase 2 roadmap
- [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) - step-by-step internal pilot deployment checklist
- [PILOT_TEST_PLAN.md](PILOT_TEST_PLAN.md) - pilot validation plan for scans, switch workflows, audit trail, jobs, and readiness checks

## Quick Start for Internal Pilot

Start with [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md), then use [PILOT_TEST_PLAN.md](PILOT_TEST_PLAN.md) to validate the deployment before broader operator rollout.

## What changed

The original repository was a collection of disconnected Flask utilities and local launch scripts. It has been refactored into:

- one app entrypoint
- modular routes and services
- SQLite-backed operational state
- auth-protected access
- role-aware protection for operator and admin actions
- CSRF protection on forms
- audit logs
- background job execution for scans
- shared NOC-style UI

## Quick start

1. Create a virtual environment and install dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and set real credentials:

   ```powershell
   Copy-Item .env.example .env
   ```

3. Start the app:

   ```powershell
   python run.py
   ```

4. Open `http://127.0.0.1:8080` unless you changed `HOST`/`PORT`.

## Authentication

- The app requires sign-in.
- If `BOOTSTRAP_ADMIN_PASSWORD` is not set, the app generates a bootstrap password in `instance/bootstrap_admin.txt`.
- Rotate that password immediately.

## Configuration

Primary runtime values live in `.env`.

Tracked config files:

- `config/scan_targets.json`
- `config/switch_inventory.seed.json`
- `config/ht_switch_inventory.seed.json`

`config/scan_targets.json` supports either plain IP strings or named target objects:

```json
{
  "cambium": [
    "10.51.0.1",
    { "ip": "10.51.0.2", "name": "Cambium West Sector" }
  ],
  "ubiquiti": [
    { "ip": "10.51.0.69", "name": "Ubiquiti North Sector" }
  ]
}
```

Secrets must never be committed.

## Key paths

- `app/` - unified application code
- `config/` - tracked seed/config files
- `docs/` - architecture and decision notes
- `instance/` - runtime database, logs, secrets, and generated bootstrap files
- `stitch/` - committed design reference, exported screens, and Stitch-generated UI handoff code
- `tests/` - basic automated coverage

## Tests

```powershell
python -m unittest discover -s tests
```

The tests use a workspace-local `.tmp-tests/` area so they run reliably in constrained environments where the system temp directory is not writable.

## Production notes

- Runs with `waitress` from `run.py`
- Flask debug mode is not used
- Reverse proxy and TLS termination should be handled upstream
- `GET /healthz` is the liveness check
- `GET /readyz` validates database and required tracked config files for readiness
- Logs write to `instance/logs/noc-console.log` with request-aware context and rotating files
- Set `LOG_LEVEL`, `SESSION_COOKIE_SECURE=true`, `PREFERRED_URL_SCHEME=https`, and `TRUST_PROXY=true` for internal production deployment behind the proxy
- See `SECURITY_NOTES.md` and `docs/ARCHITECTURE.md`
