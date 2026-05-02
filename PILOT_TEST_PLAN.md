# Pilot Test Plan

## Goal

Validate that the refactored Network Operations Console is safe and usable for an internal pilot without weakening the hardened workflows introduced in the refactor.

## Scope

- authentication and roles
- dashboard visibility
- inventory refresh and stale-state behavior
- switch inspection
- safe switch write workflow
- admin switch inventory management
- audit logging
- jobs/status visibility
- health/readiness checks

## Preconditions

- app deployed internally
- `.env` configured with real credentials
- scan target files verified
- bootstrap admin account available
- at least one viewer, one operator, and one admin test identity available if possible
- access to a safe pilot subset of real infrastructure

## Test Roles

### Viewer

- verify read-only access
- confirm write/admin actions are unavailable or blocked

### Operator

- verify manual scan access
- verify switch change preview/apply flow

### Admin

- verify switch inventory admin access
- verify settings/audit visibility

## Test Cases

### 1. Liveness and readiness

- Open `/healthz`
- Open `/readyz`
- Confirm both return healthy state before pilot use

### 2. Authentication

- Load `/auth/login`
- Sign in with bootstrap admin
- Confirm redirect to dashboard
- Sign out successfully

### 3. Dashboard

- Confirm summary cards render
- Confirm scan readiness messages render
- Confirm quick actions show correct role-aware state
- Confirm recent jobs and audit activity appear

### 4. Cambium inventory

- Open `/inventory/cambium`
- Confirm page loads with filters and last-success visibility
- Trigger manual scan as operator/admin
- Confirm jobs page shows queued/running/completed states
- Confirm audit log records trigger

### 5. Ubiquiti inventory

- Open `/inventory/ubiquiti`
- Repeat the same validation as Cambium

### 6. Switch inspection

- Open Ultra inspection
- Select a valid switch
- Confirm read-only port results load
- Repeat with HT inspection

### 7. Safe switch change workflow

- Open `/switches/change`
- Select inventory and switch
- Load available ports
- Stage preview with description-only change
- Confirm preview summary is correct
- Confirm acknowledgement is required
- Confirm apply succeeds on approved pilot target
- Confirm audit log records outcome

Repeat with:

- enable-port checked
- stale-preview timeout path
- invalid/changed port path if practical

### 8. Admin switch inventory

- Open `/admin/switches`
- Add a safe test record
- Confirm validation works
- Confirm record appears
- Delete test record
- Confirm audit records both actions

### 9. Role enforcement

- Verify viewer cannot access:
  - manual scans
  - switch change workflow actions
  - admin switch inventory
- Verify operator cannot access admin-only switch inventory administration
- Verify admin can access all intended surfaces

### 10. Audit log

- Open `/audit/`
- Confirm recent events render
- Confirm selected-event detail works
- Confirm switch change and scan actions appear with useful summaries

### 11. Jobs page

- Open `/jobs/`
- Confirm:
  - queue/running/failed counts
  - vendor freshness
  - processed row counts
  - target failure samples where applicable

## Success Criteria

- No debug-mode behavior
- No hardcoded-secret usage in runtime config
- Auth and CSRF protections hold
- Role boundaries behave correctly
- Manual scans no longer block primary UI flows
- Jobs and audit pages explain operator actions clearly
- Switch write workflow requires preview + acknowledgement
- Health/readiness probes are usable for deployment checks

## Pilot Exit Criteria

- All critical tests above pass
- No unexplained 500s during pilot scenarios
- Logs and audit data are sufficient to explain failures
- Operators report the workflow as understandable and safe enough for limited internal use

## Follow-Up After Pilot

- capture operator feedback
- review logs and audit entries
- identify device-specific reliability gaps
- prioritize Phase 2 work:
  - user management
  - stronger inventory lifecycle handling
  - dedicated worker queue if needed
  - deeper tests
