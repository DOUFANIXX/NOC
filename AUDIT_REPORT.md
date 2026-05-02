# Repository Audit Report

## 1. Executive Summary
- What this app currently is:
  `DOUFANIXX/automation` is a small internal network-operations toolkit made of several separate Flask apps. It provides:
  - a dashboard launcher/hub
  - a Cambium subscriber inventory scraper and table view
  - a Ubiquiti subscriber inventory scraper and table view
  - Huawei switch port inspection tools
  - a Huawei switch port description/enabling tool
  - a small switch inventory editor
- Overall maturity level:
  Early internal-tool / prototype maturity. The repo contains useful working logic, but it is not production-ready in its current form.
- Main strengths:
  - Clear practical purpose tied to real operational workflows
  - Simple UI that is easy for operators to understand
  - Real device integrations already exist for Cambium, Ubiquiti, and Huawei switches
  - Committed data snapshots show the tooling has been used in practice
- Main weaknesses:
  - Hardcoded credentials, IPs, and local filesystem paths
  - No authentication, authorization, audit trail, or CSRF protection
  - No tests, CI/CD, docs, or deployment packaging
  - Multi-process architecture is manually stitched together and fragile
  - UI is serviceable but very basic and inconsistent with a polished internal ops product
  - Significant security and maintainability risk for any environment beyond a trusted LAN

## 2. Repository Access Check
- Confirm whether you successfully pulled/read the repo:
  Yes. I cloned `https://github.com/DOUFANIXX/automation` successfully into the workspace and reviewed every tracked source file and template in the current `main` branch.
- Current branch / commit inspected:
  - Branch: `main`
  - HEAD: `ebd3e7d`
  - Recent history is effectively a single visible commit labeled `test`, which suggests very limited version history.
- Missing files / inaccessible parts / assumptions:
  - There is no `README`, no `.gitignore`, no `.github` workflow directory, and no visible deployment config.
  - I could not validate end-to-end runtime behavior against real devices because the app depends on private LAN equipment and credentials.
  - I also could not run Python-based validation from this shell because `python` was not usable in the current environment.
  - The audit therefore reflects the full checked-in codebase plus static analysis, not live device execution.

## 3. Tech Stack
- Frameworks:
  - Flask 3.1 (`requirements.txt`)
  - Jinja2 templates (bundled with Flask)
- Languages:
  - Python
  - HTML
  - CSS
  - small inline JavaScript
- Libraries:
  - `playwright` for web scraping Cambium and Ubiquiti device UIs
  - `netmiko` for Huawei switch SSH access
  - `pycron` for scheduling
  - `markupsafe` for rendered HTML links in Cambium view
- State management:
  - No client-side state library
  - State is server-rendered per request
  - Persisted data is flat JSON files on disk
- Styling:
  - Handwritten inline CSS inside each template
  - No design system, CSS framework, or component library
- Backend / database:
  - No real database
  - File-based persistence:
    - `Cambium Scrapper/data.json`
    - `Ubiquiti Scrapper/data.json`
    - `switches Ports/switches.json`
    - `switches Ports/HT Switch.json`
- Auth:
  - No application-level auth at all
  - Device auth is hardcoded directly in source files
- Tooling:
  - `requirements.txt`
  - `run_apps.pyw` local process launcher
  - `timer/scheduler.py` local polling scheduler
- Testing:
  - None present
- Deployment:
  - None formalized
  - Apps are started as standalone Flask dev servers on different ports
  - Dashboard hard-redirects to a fixed server IP instead of using a shared runtime or reverse proxy

## 4. Project Structure
- High-level folder tree:
  ```text
  .
  |- requirements.txt
  |- run_apps.pyw
  |- timer/
  |  |- scheduler.py
  |- Dashboard/
  |  |- app.py
  |  |- templates/index.html
  |  `- static/
  |- Cambium Scrapper/
  |  |- app.py
  |  |- Main.py
  |  |- data.json
  |  |- templates/table.html
  |  |- static/images/
  |  `- errors/
  |- Ubiquiti Scrapper/
  |  |- app.py
  |  |- main.py
  |  |- data.json
  |  |- templates/index.html
  |  |- static/images/
  |  `- __pycache__/
  `- switches Ports/
     |- app.py
     |- app_HT.py
     |- Description&Enabling.py
     |- add_switch.py
     |- switches.json
     |- HT Switch.json
     |- templates/
     `- static/
  ```
- Purpose of major folders/files:
  - `Dashboard/`: landing page and redirect hub to the other apps
  - `Cambium Scrapper/`: asynchronous Playwright scraper plus HTML table UI for Cambium devices
  - `Ubiquiti Scrapper/`: synchronous Playwright scraper plus HTML table UI for Ubiquiti devices
  - `switches Ports/`: Huawei switch read/write tools and switch inventory config
  - `timer/scheduler.py`: cron-like loop for running the scrapers
  - `run_apps.pyw`: Windows launcher that starts all Flask apps in the background
- Architectural pattern used:
  - Folder-per-tool micro-app pattern
  - Each tool is an independent Flask app on its own port
  - A simple dashboard redirects users across ports
  - Scrapers write JSON snapshots to disk
  - Switch tools read JSON inventories and directly SSH into network devices
  - No shared service layer, no package structure, no reusable common module

## 5. Current Features Inventory

### Dashboard / navigation
- Dashboard hub (`Dashboard/app.py`, `Dashboard/templates/index.html`) - Complete
  - Provides a central page linking to Cambium, Ubiquiti, Ultra Switch, Des & Enable, and HT Switch.
- Hidden switch inventory admin (`switches Ports/add_switch.py`) - Partial
  - Implemented and launchable on port `3001`, but not linked from the dashboard.

### Cambium workflow
- Cambium scrape across sector IP list (`Cambium Scrapper/Main.py`) - Partial
  - Real scraping logic exists and appears materially usable.
  - Depends on hardcoded credentials and a hardcoded IP list.
  - Captures failure screenshots in `Cambium Scrapper/errors/`, which implies known scrape failures.
- Cambium inventory persistence (`Cambium Scrapper/data.json`) - Complete
  - Stores latest merged inventory by MAC.
  - Current committed snapshot contains about `424` entries.
- Cambium inventory table UI (`Cambium Scrapper/app.py`, `Cambium Scrapper/templates/table.html`) - Complete
  - Search, pagination, and clickable IP links are present.
- Cambium historical views / refresh controls / exports - Missing

### Ubiquiti workflow
- Ubiquiti scrape across sector IP list (`Ubiquiti Scrapper/main.py`) - Partial
  - Real scraping logic exists and data is persisted.
  - It is sequential, slow, fragile, and depends on hardcoded credentials and IPs.
- Ubiquiti inventory persistence (`Ubiquiti Scrapper/data.json`) - Complete
  - Current committed snapshot contains about `214` entries.
- Ubiquiti inventory table UI (`Ubiquiti Scrapper/app.py`, `Ubiquiti Scrapper/templates/index.html`) - Complete
  - Search and pagination are implemented.
- Ubiquiti manual rescan API (`Ubiquiti Scrapper/app.py:13-16`) - Partial
  - `/scan` exists, but it is a blocking GET endpoint, not surfaced in the UI, and can take a long time.
- Ubiquiti historical views / exports / nonblocking jobs - Missing

### Switch port tools
- Ultra switch port inspection (`switches Ports/app.py`) - Partial
  - City -> area -> switch selection works.
  - Reads only interfaces 1..49 across two naming patterns and only returns ports with descriptions.
- HT switch port inspection (`switches Ports/app_HT.py`) - Partial
  - Similar basic inspection flow for a different switch inventory file.
- Port description + enable action (`switches Ports/Description&Enabling.py`) - Partial
  - Real write-path exists and sends `description` plus `undo shutdown`.
  - Functionally significant but operationally unsafe due to no auth, no confirmation, no validation, and no audit log.
- Switch inventory editor (`switches Ports/add_switch.py`) - Partial
  - Can add switches and areas to `switches.json`.
  - No delete/edit workflow, validation, duplicate-IP checks, or change tracking.
- Switch inventory data (`switches Ports/switches.json`, `HT Switch.json`) - Complete as config files
  - `switches.json` holds a large inventory with about `322` IP entries.
  - `HT Switch.json` holds about `7` IP entries.

### Automation / background execution
- Windows app launcher (`run_apps.pyw`) - Broken outside the original workstation
  - Uses absolute local paths under `C:\Users\ION\Desktop\automation\...`
- Polling scheduler (`timer/scheduler.py`) - Broken outside the original workstation
  - Also uses absolute local paths and relies on a forever loop.
  - One schedule comment does not match the actual cron expression.

### Security / user management / admin
- User login / logout - Missing
- Roles / permissions - Missing
- Audit trail - Missing
- Session security / CSRF protection - Missing

### Operations / observability
- Error screenshots for Cambium scraper - Partial
  - Helpful for local debugging, but this is not real observability.
- Structured application logging - Partial
  - Cambium uses `logging`; most other files rely on `print`.
- Monitoring / metrics / alerts - Missing

## 6. Screens / Pages Audit

### Dashboard
- Route / file location:
  - Route: `/`
  - Backend: `Dashboard/app.py:8-10`
  - Template: `Dashboard/templates/index.html`
- Purpose:
  - Entry point for internal tools and redirects to the other apps.
- Current state:
  - Works as a simple launcher if all other apps are already running on expected ports.
- UX quality:
  - Clean and understandable, but very basic.
- Missing parts:
  - No health indicators
  - No status badges
  - No "last updated" timestamps
  - No link to the switch inventory editor on port `3001`
- Bugs or polish issues:
  - Hardcoded `SERVER_IP` in `Dashboard/app.py:6`
  - Redirect-only architecture means the dashboard cannot gracefully handle unavailable child apps

### Cambium users page
- Route / file location:
  - Route: `/`
  - Backend: `Cambium Scrapper/app.py:8-44`
  - Template: `Cambium Scrapper/templates/table.html`
- Purpose:
  - Display the latest Cambium subscriber inventory snapshot.
- Current state:
  - Good read-only table with search and pagination.
- UX quality:
  - Reasonably usable for an internal table page.
- Missing parts:
  - No visible refresh action
  - No loading state
  - No empty-state messaging beyond raw missing-file text in backend
  - No sort controls or filters by sector / RSSI / device type
  - No export / CSV
- Bugs or polish issues:
  - Search is client-side only
  - Table depends on a large preloaded DOM
  - Layout and styling are duplicated rather than shared

### Ubiquiti users page
- Route / file location:
  - Route: `/`
  - Backend: `Ubiquiti Scrapper/app.py:8-16`
  - Template: `Ubiquiti Scrapper/templates/index.html`
- Purpose:
  - Display the latest Ubiquiti subscriber inventory snapshot.
- Current state:
  - Good read-only table with search and pagination.
- UX quality:
  - Comparable to the Cambium page, slightly less polished in information hierarchy.
- Missing parts:
  - No UI control for `/scan`
  - No visible last-refresh timestamp
  - No sort / filter / export
  - No error state for failed scans
- Bugs or polish issues:
  - The scan endpoint is hidden and implemented as a long-running GET
  - User may assume the page is live when it is actually a stale JSON snapshot

### Ultra switch ports page
- Route / file location:
  - Route: `/`
  - Backend: `switches Ports/app.py:62-93`
  - Template: `switches Ports/templates/Ultra Switch index.html`
- Purpose:
  - Inspect switch ports with descriptions for switches selected by city / area / switch.
- Current state:
  - Core flow exists and likely works in the intended LAN.
- UX quality:
  - Adequate, but clearly utilitarian.
- Missing parts:
  - No loading state during SSH calls
  - No pagination / search / sort in results
  - No display of selected switch IP in the UI
  - No distinction between successful empty result and connection failure without reading the error
- Bugs or polish issues:
  - Limited port range scanning
  - Results include only described ports, so it is not a full interface audit

### HT switch ports page
- Route / file location:
  - Route: `/`
  - Backend: `switches Ports/app_HT.py:93-113`
  - Template: `switches Ports/templates/HT switch index.html`
- Purpose:
  - Inspect ports on HT mall switches.
- Current state:
  - Same pattern as Ultra switch but with a flatter selector.
- UX quality:
  - Serviceable, but minimal.
- Missing parts:
  - Same missing states as Ultra switch
  - No extra context around the selected site or switch IP
- Bugs or polish issues:
  - Same range and parsing limitations as the Ultra switch tool

### Des & Enable page
- Route / file location:
  - Route: `/`
  - Backend: `switches Ports/Description&Enabling.py:92-139`
  - Template: `switches Ports/templates/Des&Enable.html`
- Purpose:
  - Find ports missing descriptions, then apply a description and enable them.
- Current state:
  - Functionally important and potentially powerful.
- UX quality:
  - Understandable but operationally risky.
- Missing parts:
  - No auth
  - No confirmation modal
  - No rollback
  - No dry-run preview
  - No port state diff before / after
  - No audit history
- Bugs or polish issues:
  - The action couples two side effects: setting description and issuing `undo shutdown`
  - This is exactly the kind of tool that should have stronger guardrails

### Switch & area management page
- Route / file location:
  - Route: `/`
  - Backend: `switches Ports/add_switch.py:20-64`
  - Template: `switches Ports/templates/add_switch.html`
- Purpose:
  - Add switch records or add new areas to the inventory JSON.
- Current state:
  - Basic CRUD-lite admin page.
- UX quality:
  - Acceptable for a hidden admin utility.
- Missing parts:
  - No edit or delete
  - No validation for IP format
  - No duplicate checks beyond area-name collision
  - No access control
  - No revision history
- Bugs or polish issues:
  - Hidden from the dashboard, which makes discovery inconsistent

## 7. UI/UX Audit
- Visual hierarchy:
  - Clear enough for internal tooling, but all pages share nearly the same visual weight and do not emphasize freshness, status, or critical actions well.
- Spacing:
  - Generally consistent and readable.
- Typography:
  - Simple system fonts are fine; styling is repetitive and not systematized.
- Consistency:
  - Moderate. Pages share a similar red / white style, but this is copy-paste consistency rather than a reusable design system.
- Navigation:
  - Dashboard hub is easy to understand.
  - Cross-app navigation depends on separate ports and hard redirects.
- Onboarding:
  - None. A new operator would need verbal knowledge of what each tool does and when to use it.
- Empty states:
  - Weak. Most pages show nothing or return raw backend text.
- Loading states:
  - Missing across the board.
- Error states:
  - Minimal. Errors are generally plain text near forms or hidden in logs / screenshots.
- Forms:
  - Straightforward, but operationally risky where write actions exist.
- Tables / lists:
  - Readable, but no sorting, sticky headers, filtering by field, export, or bulk workflows.
- Responsiveness:
  - Basic mobile tolerance exists because layouts are simple, but these are clearly desktop-first tools.
- Accessibility:
  - Weak.
  - No ARIA consideration
  - No keyboard workflow attention
  - Color contrast likely acceptable in places but not audited systematically
  - No semantic error summaries or screen-reader states
- Premium feel / professionalism:
  - Functional but not polished.
  - Feels like a useful internal utility rather than a mature operations platform.

## 8. Code Quality Audit
- Code organization:
  - Small files make the code easy to scan, but there is no shared core layer and a lot of duplicated patterns.
- Reuse:
  - Low.
  - Similar template CSS and pagination logic are duplicated across pages.
  - Similar Netmiko scraping logic is duplicated across switch apps.
- Naming consistency:
  - Inconsistent:
  - folder names with spaces
  - `Main.py` vs `main.py`
  - files like `Description&Enabling.py`
  - route names like `/Ultra switch`
- Typing quality:
  - Minimal to none.
  - Only one obvious function annotation appears (`scrape_device(ip: str, ...)` in Ubiquiti).
- Dead code:
  - `MAC_REGEX` in `Cambium Scrapper/Main.py:10` is defined but unused.
  - `os` in `Ubiquiti Scrapper/app.py` appears unused.
- Duplication:
  - High in templates and switch parsing logic.
- Tech debt:
  - High.
  - The code works by direct scripting rather than stable architecture.
- Maintainability:
  - Low to medium.
  - Small size helps, but hardcoded assumptions make changes risky.
- Scalability:
  - Low.
  - File-based storage, blocking requests, no queueing, no shared services, and per-device browser creation limit scale.
- Readability:
  - Generally readable.
  - However, many broad `except:` blocks and inline constants reduce confidence.

## 9. Backend / Data / Auth Audit
- API structure:
  - Very small Flask route surface.
  - No versioning, no JSON API design beyond one ad hoc `/scan` endpoint.
- Database structure:
  - None.
  - JSON files are acting as both config and persisted state.
- Schema quality:
  - Informal and not enforced.
  - Field names vary across datasets (`source_ip`, `sector_ip`, `sm-type`, `Firmware`).
- Auth flow:
  - No app login.
  - Device login credentials are embedded in source.
- Permissions / roles:
  - None.
  - Anyone who can reach the app can trigger scans or device writes.
- Validation:
  - Very light.
  - Form presence checks exist; structural validation is largely absent.
- Data fetching patterns:
  - Cambium:
    - asynchronous concurrent scraping, one shared browser, better design than Ubiquiti
  - Ubiquiti:
    - sequential scraping, one browser per IP, much slower
  - Switch tools:
    - synchronous SSH calls during requests
- Error handling:
  - Weak.
  - Too many broad `except:` and simple `print` statements.
  - Failures are often swallowed and turned into empty results.

## 10. Quality Gaps
- Tests:
  - None
- Accessibility:
  - No formal attention
- Observability:
  - No metrics, tracing, alerts, or centralized logs
- Audit logs:
  - None, including for config-changing switch operations
- Environment config:
  - Missing
- Docs:
  - Missing
- Seed / demo data:
  - Real operational data is committed instead
- CI/CD:
  - Missing
- Security basics:
  - Missing auth, secrets management, HTTPS strategy, CSRF protection, and role checks
- Analytics / usage telemetry:
  - Missing
- Performance optimization:
  - Minimal
- Packaging / deployment:
  - Missing Docker, Gunicorn/Waitress, reverse proxy, service definitions, and health checks

## 11. Bugs / Risks / Red Flags
- Hardcoded credentials are committed in source:
  - `Cambium Scrapper/Main.py:17-18`
  - `Ubiquiti Scrapper/main.py:35`
  - `switches Ports/app.py:24-25`
  - `switches Ports/app_HT.py:40-41`
  - `switches Ports/Description&Enabling.py:11-12`
- All Flask apps run in debug mode on `0.0.0.0`:
  - `Cambium Scrapper/app.py:48`
  - `Ubiquiti Scrapper/app.py:21`
  - `Dashboard/app.py:34`
  - `switches Ports/app.py:96`
  - `switches Ports/app_HT.py:116`
  - `switches Ports/add_switch.py:67`
  - `switches Ports/Description&Enabling.py:142`
- Direct device write operation is unauthenticated and unlogged:
  - `switches Ports/Description&Enabling.py:69-90`
  - Request handler: `switches Ports/Description&Enabling.py:103-125`
- Launcher and scheduler are environment-broken in this clone because they point to the original workstation paths:
  - `run_apps.pyw:7-13`
  - `timer/scheduler.py:8`
  - `timer/scheduler.py:13`
- Dashboard is pinned to one server IP and one fixed port layout:
  - `Dashboard/app.py:6`
  - `Dashboard/app.py:12-30`
- Ubiquiti scan is a side-effecting GET and likely very slow:
  - Route: `Ubiquiti Scrapper/app.py:13-16`
  - Implementation: `Ubiquiti Scrapper/main.py:102-127`
- Ubiquiti scraper creates a fresh browser per IP and sleeps `15` seconds per device:
  - `Ubiquiti Scrapper/main.py:35-39`
  - `Ubiquiti Scrapper/main.py:61`
- Broad `except:` blocks hide operational failures:
  - `Cambium Scrapper/Main.py:35-58`
  - `Cambium Scrapper/Main.py:82-86`
  - `Cambium Scrapper/Main.py:145-148`
  - `Cambium Scrapper/Main.py:197-201`
  - `Ubiquiti Scrapper/main.py:9-14`
  - `Ubiquiti Scrapper/main.py:49-55`
- Scheduler comment and cron do not match:
  - Comment says `22:30`, but cron is `45 15 * * *` in `timer/scheduler.py:11-13`
- Runtime artifacts and operational data are committed:
  - `Ubiquiti Scrapper/__pycache__/main.cpython-313.pyc`
  - `Cambium Scrapper/errors/*`
  - `Cambium Scrapper/data.json`
  - `Ubiquiti Scrapper/data.json`
  - No `.gitignore` is present at repo root
- Route naming and filesystem naming are fragile for tooling:
  - spaces in folders and routes such as `switches Ports`, `/Ultra switch`, `/HT switch`
  - punctuation-heavy filename `Description&Enabling.py`

## 12. Best Improvement Opportunities

### Quick wins
- Move all credentials, IPs, and server settings into environment/config files
- Add a root `.gitignore`
- Remove committed `__pycache__`, screenshot dumps, and refreshable runtime JSON from source control
- Turn off Flask debug mode
- Replace hardcoded absolute paths in `run_apps.pyw` and `timer/scheduler.py`
- Add a visible "last updated" timestamp to data pages
- Expose or intentionally remove the hidden switch inventory admin

### Medium effort / high impact
- Unify shared layout, styles, and table behaviors across all pages
- Add auth and role gating, especially for switch write operations
- Convert long-running scans into background jobs instead of blocking requests
- Standardize data models and naming (`sm_type` vs `sm-type`, `Firmware` casing, etc.)
- Add structured logging and better failure reporting
- Add edit/delete/validation to switch inventory management

### Large structural improvements
- Merge the separate Flask apps into one application with blueprints or modules
- Introduce a real database for device inventory, switch inventory, scan history, and audit logs
- Add a job queue / scheduler layer for scraping
- Add proper deployment packaging, health checks, and CI/CD
- Build a real internal operations console rather than several loosely connected pages

## 13. Recommended Product Direction
Based on the actual codebase, this product should evolve into a focused internal network operations console, not just a loose bundle of scripts.

The strongest direction is:
- one authenticated internal app
- a shared device inventory data model
- safe operator workflows around network changes
- background scan jobs
- clear freshness and status indicators
- searchable, filterable operational tables

The first improvement priority should not be visual redesign. It should be operational hardening:
- secrets management
- auth
- safer write workflows
- stable startup/deployment
- better data lifecycle

Once those foundations are in place, the UI can be upgraded into a cleaner NOC-style interface with richer tables, status badges, and history views.

## 14. Action Plan

### Phase 1: cleanup / fixes / foundation
- Add `.gitignore`
- Remove committed secrets and rotate every exposed credential
- Replace hardcoded IPs/paths with config/env
- Disable debug mode
- Fix launcher and scheduler pathing
- Add basic auth and protect write actions
- Add request validation and better error handling
- Document setup and runtime assumptions

### Phase 2: UI/UX improvements
- Create a shared base template and shared CSS
- Add status/freshness indicators on dashboard cards
- Add loading, empty, and error states
- Add richer search/filter/sort for tables
- Improve admin discoverability and information hierarchy
- Add safe confirmations for write actions

### Phase 3: feature upgrades
- Background queue for scans
- Unified device inventory schema
- Device history / change history
- Export options
- Editable switch inventory with full CRUD
- Better filtering by site, sector, device type, firmware, and status

### Phase 4: polish / production readiness
- Tests
- CI/CD
- Containerized or service-based deployment
- Audit logs
- Observability
- Backups / restore strategy
- RBAC
- HTTPS / reverse proxy / health endpoints

## 15. Final Verdict
- preserve with heavy refactor

Rationale:
- The repo already contains real domain-specific scraping and switch-management logic that is worth preserving.
- However, the security model, deployment model, and architectural seams are too weak to preserve as-is.
- This is not a clean candidate for a total rewrite from zero, but it is absolutely a candidate for aggressive hardening, consolidation, and selective rebuilding of orchestration, auth, and data layers.
