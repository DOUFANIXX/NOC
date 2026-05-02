# Security Notes

## Immediate secret rotation required

The original codebase contained hardcoded credentials in source for:

- Cambium device login
- Ubiquiti device login
- Ultra switch Huawei SSH access
- HT switch Huawei SSH access

Those secrets have been removed from source and replaced with environment-based configuration. They should be rotated immediately in the target environment.

## What changed

- Removed hardcoded secrets from application source
- Moved runtime-sensitive settings into environment-based configuration
- Removed Flask debug-mode startup pattern
- Added sign-in gate for the whole app
- Added role-aware protection:
  - `viewer`
  - `operator`
  - `admin`
- Added CSRF protection for POST actions
- Added audit logs for:
  - manual scan triggers
  - switch inventory add/delete
  - switch port change operations
  - sign-in / sign-out activity
- Added a generated local secret-key fallback stored under `instance/secret_key.txt`
- Added proxy- and cookie-related environment toggles for production deployments
- Added request-aware rotating application logs with no secret rendering
- Added `/readyz` so production probes can verify database and tracked config availability

## Remaining operational cautions

- `config/scan_targets.json` contains internal target IPs and should be treated as sensitive infrastructure metadata.
- The app still connects directly to real infrastructure over HTTP/SSH, so network segmentation and access control still matter.
- The current switch workflow is safer than before, but it still relies on live device state during inspection and confirmation.
- Background job execution is in-process. For larger scale or stronger resilience, move to a dedicated worker queue later.

## Recommended next hardening steps

- Put the app behind the corporate reverse proxy with TLS and IP restrictions
- Set `SESSION_COOKIE_SECURE=true`, `PREFERRED_URL_SCHEME=https`, and `TRUST_PROXY=true` when deployed behind the internal TLS-terminating proxy
- Move secrets from `.env` into the organization's secret manager
- Add password rotation workflow and user management UI
- Add stronger session controls and optional MFA
- Add structured central log shipping
- Add more granular RBAC if multiple operator groups exist
- Put retention and access controls around `instance/logs/`
