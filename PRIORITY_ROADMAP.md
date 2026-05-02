# Priority Roadmap

## Top 10 Highest-Priority Improvements
1. Remove hardcoded secrets from source and rotate every exposed credential.
2. Add environment/config management for server IPs, device credentials, and scan target lists.
3. Disable Flask debug mode everywhere and protect the apps behind authentication.
4. Add auth, authorization, and CSRF protection before keeping the switch write tool in service.
5. Replace absolute workstation paths in `run_apps.pyw` and `timer/scheduler.py`.
6. Add a root `.gitignore` and stop committing runtime artifacts, `__pycache__`, screenshots, and refreshable data dumps.
7. Move scans into background jobs or scheduled tasks rather than blocking request handlers.
8. Consolidate the separate Flask apps into one shared application with reusable layout/components.
9. Introduce structured logging, operator-visible error states, and audit logs for network changes.
10. Add documentation, smoke tests, and basic CI so the repo can be safely maintained by more than one person.

## Phase 1: Cleanup / fixes / foundation
- Add `.gitignore`
- Rotate leaked credentials
- Move secrets and server values into env/config
- Remove debug mode
- Fix launcher/scheduler portability
- Add basic login protection
- Protect write routes with stronger controls
- Add setup docs

## Phase 2: UI/UX improvements
- Create shared base template
- Standardize tables, buttons, spacing, and typography
- Add last-scan timestamps and service health on dashboard
- Add loading / empty / error states
- Add filter/sort/export on inventory tables
- Improve switch admin discoverability

## Phase 3: Feature upgrades
- Queue-based background scans
- Device inventory normalization
- Scan history and diff views
- Safer switch change workflow with confirmation and audit trail
- Full CRUD for switch inventory
- Better per-site and per-device filtering

## Phase 4: Polish / production readiness
- Automated tests
- CI/CD
- Container or service packaging
- Reverse proxy / HTTPS / health checks
- Observability
- RBAC
- Backup / restore process

## Recommended implementation posture
- Keep the useful device-specific logic.
- Refactor heavily around it.
- Selectively rebuild the orchestration, config, security, and data layers.
