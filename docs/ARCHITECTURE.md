# Architecture

## Overview

The application is now a single Flask service with an app-factory layout.

```text
app/
  __init__.py
  db.py
  routes/
  services/
  templates/
  static/
  models/
  utils/
config/
docs/
tests/
run.py
wsgi.py
```

## Major layers

### Routes

- `app/routes/dashboard.py`
- `app/routes/auth.py`
- `app/routes/inventory.py`
- `app/routes/switches.py`
- `app/routes/admin.py`
- `app/routes/jobs.py`
- `app/routes/health.py`

Routes are thin. They validate request intent, enforce auth/role policy, and delegate to services.

### Services

- scan services:
  - `cambium_service.py`
  - `ubiquiti_service.py`
- switch services:
  - `switch_service.py`
  - `switch_inventory_service.py`
- platform services:
  - `job_runner.py`
  - `jobs_service.py`
  - `inventory_service.py`
  - `user_service.py`
  - `audit_service.py`

### Data layer

SQLite is used for:

- users
- devices
- switch inventory
- jobs
- audit logs

This keeps the refactor lightweight while replacing the previous JSON-as-runtime-database pattern.

### Config

Environment-based runtime config comes from `.env` plus `config/settings.py`.

Tracked config files remain for:

- scan targets
- seed switch inventory

## Background jobs

Scan requests no longer block the main request-response cycle.

The app uses:

- an in-process `ThreadPoolExecutor`
- a `jobs` table for visibility
- a scheduler thread for periodic scan triggers
- target-level success/failure samples in stored job metadata
- request-aware structured logging around job queue/start/finish/failure

This is intentionally lightweight. It is appropriate for an internal deployment with modest concurrency.

## Security model

- authenticated access required
- role-aware route protection
- CSRF enforced on POST routes
- audited operator/admin actions
- request-scoped log context without exposing secrets

## Health and readiness

- `/healthz` provides a lightweight liveness response
- `/readyz` verifies database access and tracked config-file presence for production readiness probes

## Design source

The `stitch/` directory is committed as the design handoff source of truth for the shared shell and page-level UX direction. It remains in the repo intentionally so future implementation work can trace back to the approved design reference.

## Known tradeoffs

- SQLite is lightweight and maintainable here, but not a long-term multi-node solution
- background jobs are in-process, so they share process lifetime with the web app
- vendor/device integrations still depend on live UI/SSH behavior from real infrastructure
