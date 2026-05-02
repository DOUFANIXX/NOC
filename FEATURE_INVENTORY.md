# Feature Inventory

## Dashboard
- Dashboard hub - Complete
  - File: `Dashboard/app.py`
  - Notes: Links to five running tools via redirects.
- Hidden switch inventory admin link - Partial
  - File: `switches Ports/add_switch.py`
  - Notes: Implemented on port `3001` but not linked from dashboard.

## Cambium
- Multi-device Cambium scrape - Partial
  - File: `Cambium Scrapper/Main.py`
  - Notes: Real async scrape logic exists; depends on hardcoded credentials/IPs and private network access.
- Cambium data snapshot persistence - Complete
  - File: `Cambium Scrapper/data.json`
  - Notes: Committed snapshot contains about `424` records.
- Cambium table page - Complete
  - Files: `Cambium Scrapper/app.py`, `Cambium Scrapper/templates/table.html`
  - Notes: Search and pagination included.
- Cambium scan controls in UI - Placeholder
  - Notes: Data view exists, but there is no visible refresh action in the page UI.
- Cambium history / trend views - Missing

## Ubiquiti
- Multi-device Ubiquiti scrape - Partial
  - File: `Ubiquiti Scrapper/main.py`
  - Notes: Real scrape logic exists but is sequential and slow.
- Ubiquiti data snapshot persistence - Complete
  - File: `Ubiquiti Scrapper/data.json`
  - Notes: Committed snapshot contains about `214` records.
- Ubiquiti table page - Complete
  - Files: `Ubiquiti Scrapper/app.py`, `Ubiquiti Scrapper/templates/index.html`
  - Notes: Search and pagination included.
- Ubiquiti rescan endpoint - Partial
  - File: `Ubiquiti Scrapper/app.py`
  - Notes: `/scan` exists, but it is a blocking GET and not surfaced in the UI.
- Ubiquiti history / trend views - Missing

## Switches - read-only
- Ultra switch port lookup - Partial
  - Files: `switches Ports/app.py`, `switches Ports/templates/Ultra Switch index.html`
  - Notes: Good basic flow, but only scans a bounded port range and only returns described ports.
- HT switch port lookup - Partial
  - Files: `switches Ports/app_HT.py`, `switches Ports/templates/HT switch index.html`
  - Notes: Same limitations as Ultra switch view.

## Switches - write/admin
- Port description + enable tool - Partial
  - Files: `switches Ports/Description&Enabling.py`, `switches Ports/templates/Des&Enable.html`
  - Notes: Real write path exists; missing auth, validation, confirmations, and audit logging.
- Add switch inventory records - Partial
  - Files: `switches Ports/add_switch.py`, `switches Ports/templates/add_switch.html`
  - Notes: Can add switches and areas; no edit/delete/history.
- Large switch inventory config - Complete
  - File: `switches Ports/switches.json`
  - Notes: About `322` IP entries, covering multiple cities/areas.
- HT switch inventory config - Complete
  - File: `switches Ports/HT Switch.json`
  - Notes: About `7` IP entries.

## Automation / orchestration
- Windows process launcher - Broken
  - File: `run_apps.pyw`
  - Notes: Uses hardcoded absolute paths from the original workstation.
- Cron-like scheduler - Broken
  - File: `timer/scheduler.py`
  - Notes: Same path issue; one schedule comment does not match the expression.

## Platform / product gaps
- App authentication - Missing
- Roles / permissions - Missing
- CSRF protection - Missing
- Audit logs - Missing
- Notifications - Missing
- Exports - Missing
- Observability - Missing
- Tests - Missing
- CI/CD - Missing
- Deployment packaging - Missing
- Documentation - Missing

## Overall status summary
- Complete:
  - Static dashboard hub
  - Read-only Cambium and Ubiquiti inventory pages
  - JSON-backed switch inventories
- Partial:
  - All real operational workflows
  - All switch inspection/write tools
  - Scrapers and admin tooling
- Broken:
  - Launcher and scheduler portability
- Placeholder / missing:
  - Production platform features
  - Safe admin workflows
  - Background job architecture
  - Security and governance layers
