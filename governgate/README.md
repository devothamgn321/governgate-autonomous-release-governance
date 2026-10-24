# GovernGate controller

GovernGate checks whether a shared SDK change breaks its known consumers before a human merges it. Billing verifies tokens; Notification issues tokens and serves as a control. The protected controller compares both pinned consumer sources against the exact SDK MR candidate and current main baseline.

- [Architecture and all flow diagrams](ARCHITECTURE.md)
- [Implementation and operator guide](IMPLEMENTATION.md)
- [Public monorepo runbook](https://github.com/devothamgn321/governgate-autonomous-release-governance/blob/main/IMPLEMENTATION.md)
- [Latest dated live evidence](https://github.com/devothamgn321/governgate-autonomous-release-governance/blob/main/LIVE_VERIFICATION_2026-10-21.md)

## Deployed flow

SDK MR checks → credential-free bridge → protected controller → Billing/Notification baseline and candidate tests → trusted evidence → blocking human review → protected final freshness check → mirrored SDK pipeline result. There is no automatic merge.

GovernGate MR !6 merged at `84e6779625460fe29406a5a15c9949f4ee1b206c`. On October 21 the [compatible controller pipeline](https://gitlab.com/governgate2/governgate/-/pipelines/2972749377) passed through manual review and freshness; the [breaking controller pipeline](https://gitlab.com/governgate2/governgate/-/pipelines/2972749891) blocked a Billing candidate regression after one API-timeout retry. This replaces older pending-activation status.

## Security and scope

Only controller and final freshness jobs receive `GOVERNGATE_API_TOKEN`, protected/masked and scoped to `governgate-controller`. SDK jobs, bridge, workers and manual review receive no controller API credential. Source trees are paginated and archives bound to immutable commits and per-file SHA-256 metadata. Candidate tests run without network or credentials, with filesystem, privilege, resource, timeout and output restrictions.

Both consumers always run; Duo supplies advisory context. The existing six SDK jobs and Duo flow are preserved. Nebius is optional and disabled. Generic discovery, semantic analysis and remediation modules are not the active fixed-consumer approval path.

JUnit remains candidate-controlled, so human review is mandatory. The ledger digest is not an independent signature. Final freshness is point-in-time. This is a demonstrated two-consumer prototype, not a general enterprise deployment claim.

## Tests

```sh
python -m pip install '.[test]' pyyaml
pytest -q
```

109 controller tests passed at the verified snapshot; 128 across the public monorepo. Live API-backed verification and Docker smoke tests require trusted GitLab configuration and are distinct from unit tests.
