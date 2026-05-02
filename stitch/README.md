# Stitch Design Handoff

This folder contains the UI/design reference for the refactor.

Contents:
- PNG screens exported from Stitch
- code files for each screen/component generated from Stitch

Instructions:
- Use this folder as the visual/design source of truth.
- Do not blindly copy the design if it weakens operational safety.
- Preserve the real network-operations logic from the repo.
- Improve the design where needed for:
  - confirmations
  - validation
  - permissions
  - audit logs
  - stale-data warnings
  - last-refresh indicators
  - job status / scan status
  - safer admin workflows

Target product:
A polished internal Network Operations Console for:
- Cambium subscriber inventory
- Ubiquiti subscriber inventory
- Huawei switch inspection
- Huawei switch description/enabling workflows
- switch inventory administration
- scan/job visibility
- auditability