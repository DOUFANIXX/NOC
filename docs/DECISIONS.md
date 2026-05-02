# Decisions

## 1. Unified Flask app instead of multiple mini-apps

Chosen because the original repo had duplicated templates, duplicated runtime config, fragile cross-port redirects, and no consistent security boundary.

## 2. SQLite instead of introducing a heavier database stack

Chosen because:

- the app is an internal tool
- the data model is moderate
- this keeps setup and maintenance simple
- it still provides much better durability and queryability than flat JSON files

## 3. In-process background jobs instead of Celery/RQ right now

Chosen because:

- the repo previously had no job system
- the immediate need was to stop blocking web requests
- a thread-backed job executor is enough for this milestone

If job volume grows, this can later be replaced with a dedicated worker queue.

## 4. Custom auth/session layer instead of adding a larger auth dependency stack

Chosen because:

- the app only needs straightforward session auth for now
- role-aware route protection is limited and explicit
- minimizing dependency growth made the refactor easier to land quickly

## 5. Seed tracked switch inventory into the database

Chosen because switch inventory is part of product configuration, not just transient runtime data.

## 6. Keep scan targets in config, not code

Chosen to remove operational assumptions from service modules and keep the scan layer reusable and testable.

## 7. Keep the Stitch design source in-repo

Chosen because:

- the refactor explicitly used Stitch exports as the UI handoff source of truth
- the implementation should stay traceable back to its approved design reference
- preserving screenshots plus generated code makes future UX iteration easier without reopening discovery work

## 8. Use workspace-local temp paths for tests

Chosen because:

- constrained local environments may not allow writes to the system temp directory
- CI and local development both benefit from deterministic temp-path behavior
- this fixes the unittest reliability issue without weakening app behavior
