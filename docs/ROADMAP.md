# Roadmap

## Completed in this refactor

- unified app entrypoint
- modular Flask structure
- env/config-driven secrets
- auth and role protection
- CSRF protection
- background scan jobs
- shared UI
- audit logging
- switch inventory admin surface
- docs and basic tests
- request-aware rotating logs
- readiness endpoint and production serving guidance
- tracked Stitch design source in-repo

## Next milestone

1. Add editable user management and password reset flow
2. Add richer switch inventory editing instead of add/delete only
3. Improve scan result normalization and stale-device lifecycle handling
4. Add export/download options for inventory views
5. Add deeper test coverage for route permissions and job execution
6. Move job execution to a dedicated worker if deployment scale requires it
