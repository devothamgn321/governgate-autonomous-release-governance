# Architecture documentation checkpoint — October 21, 2026

Base: GitHub main `cc4f876f6f2df6dc7688ad51e248a7d40486dc09` after PR #3.

## Changes

- Added root and standalone-controller ARCHITECTURE.md with six Mermaid diagrams: context, sequence, test matrix, credential boundary, source/evidence lifecycle and decision flow. Root README adds a short pipeline diagram.
- Replaced historical/pending-activation implementation guide with the current operator runbook: configuration, identity rules, four-run review, failure recovery, evidence retention and limitations.
- Refreshed all four project READMEs, removing obsolete bridge/activation instructions and caller-supplied IID/SHA claims.
- Clarified fixed-consumer source verification versus generic legacy discovery, SDK wheel evidence, optional AI/remediation and the active controller verdict.
- Preserved exact source revisions and dated live evidence. Documentation provenance distinguishes these updates from GitLab code deployments.

## Validation boundary

Documentation only. No Python, CI YAML, SDK behavior, credentials, Duo flow or project settings changed. Latest live positive/negative cases remain the October 21 runs linked in LIVE_VERIFICATION_2026-10-21.md; no new live controller run is claimed for documentation changes. Candidate-controlled JUnit, point-in-time freshness, optional disabled Nebius and the disabled legacy analyzer edge case remain documented.
