# Deployment Checklist

## Pre-Deploy

- [ ] Confirm target branch/commit to deploy
- [ ] Create Python virtual environment
- [ ] Install dependencies from `requirements.txt`
- [ ] Copy `.env.example` to `.env`
- [ ] Set strong `SECRET_KEY`
- [ ] Set real device credentials:
  - [ ] `CAMBIUM_USERNAME`
  - [ ] `CAMBIUM_PASSWORD`
  - [ ] `UBIQUITI_USERNAME`
  - [ ] `UBIQUITI_PASSWORD`
  - [ ] `ULTRA_SWITCH_USERNAME`
  - [ ] `ULTRA_SWITCH_PASSWORD`
  - [ ] `HT_SWITCH_USERNAME`
  - [ ] `HT_SWITCH_PASSWORD`
- [ ] Set bootstrap admin values
- [ ] Set production-safe deployment flags:
  - [ ] `SESSION_COOKIE_SECURE=true`
  - [ ] `PREFERRED_URL_SCHEME=https`
  - [ ] `TRUST_PROXY=true`
  - [ ] `LOG_LEVEL=INFO` or appropriate level

## Config Files

- [ ] Verify `config/scan_targets.json`
- [ ] Verify `config/switch_inventory.seed.json`
- [ ] Verify `config/ht_switch_inventory.seed.json`
- [ ] Treat `config/scan_targets.json` as sensitive

## Runtime Paths

- [ ] Confirm `INSTANCE_PATH`
- [ ] Confirm database path is writable
- [ ] Confirm log directory is writable
- [ ] Confirm Playwright/browser runtime is available if scan flows will be used

## Startup

- [ ] Start with `python run.py`
- [ ] Confirm app binds to expected host/port
- [ ] Place app behind internal reverse proxy
- [ ] Restrict access to internal network/operator audience

## Verification

- [ ] `GET /healthz` returns `200`
- [ ] `GET /readyz` returns `200`
- [ ] Login page loads
- [ ] Bootstrap admin login works
- [ ] Dashboard loads
- [ ] Jobs page loads
- [ ] Audit page loads
- [ ] Settings page loads

## Operational Checks

- [ ] Confirm scan readiness messages look correct
- [ ] Run one manual Cambium scan in pilot conditions
- [ ] Run one manual Ubiquiti scan in pilot conditions
- [ ] Confirm jobs page records the runs
- [ ] Confirm audit page records the actions
- [ ] Confirm stale/current indicators behave as expected

## Switch Workflow Checks

- [ ] Verify Ultra inspection works
- [ ] Verify HT inspection works
- [ ] Verify switch change preview works
- [ ] Verify confirmation gate works
- [ ] Verify stale preview rejection works
- [ ] Verify write action appears in audit log

## Post-Deploy Hardening

- [ ] Rotate bootstrap admin password
- [ ] Rotate any previously exposed credentials
- [ ] Back up DB/config after initial validation
- [ ] Set log retention/access policy
- [ ] Document pilot operators and admin owners
