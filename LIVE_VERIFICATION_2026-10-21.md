# GovernGate live verification — October 21, 2026

GovernGate MR !6 is merged at 84e6779625460fe29406a5a15c9949f4ee1b206c. Fresh detached SDK MR pipelines were triggered today; no SDK MR was merged and no live credentials or protection settings were changed.

## Passing case — verified

- SDK MR !6 candidate: ede363a918e52250057135142ca6df797c2d05a3.
- SDK pipeline: https://gitlab.com/governgate2/core-auth-sdk/-/pipelines/2972745264 — Passed.
- Controller pipeline: https://gitlab.com/governgate2/governgate/-/pipelines/2972749377 — Passed.
- Trusted controller: https://gitlab.com/governgate2/governgate/-/jobs/17354948613 — Billing and Notification both baseline PASS / candidate PASS.
- Downloaded evidence inspected; deployed credential-free validator accepted it locally. Explicitly started manual review under user authorization.
- Manual review: https://gitlab.com/governgate2/governgate/-/jobs/17354948614 — Passed.
- Post-review freshness: https://gitlab.com/governgate2/governgate/-/jobs/17354948615 — Passed; executed --check-freshness and accepted unchanged refs.

## Breaking case — verified after one retry

- SDK MR !1 candidate: a498bcf754a93d7cbcd58a89c8e44314bc872142.
- SDK pipeline: https://gitlab.com/governgate2/core-auth-sdk/-/pipelines/2972745921 — Failed as mirrored from BLOCKED controller.
- Controller pipeline: https://gitlab.com/governgate2/governgate/-/pipelines/2972749891 — Failed, BLOCKED.
- First controller job https://gitlab.com/governgate2/governgate/-/jobs/17354952853 failed closed with INCOMPLETE_EVIDENCE / ReadTimeout. This API availability failure was not counted as a regression demonstration.
- Retried once: https://gitlab.com/governgate2/governgate/-/jobs/17355045278 — Billing baseline PASS / candidate FAIL, Notification both PASS, verdict BLOCKED. Evidence downloaded and inspected.
- Manual review and freshness jobs were skipped. No negative-case manual override was run.

## Pinned identities and validation

SDK baseline: bac25944d996acafd3a6fa3e4d2833164f3aaa3f.
Billing: 1c9cba0941a7e5c964177863defc4174710622d4.
Notification: 676cbdc7811cdf0af3490ebd6897b692e6ad7368.

Current GovernGate and SDK main archives were downloaded and their embedded commit SHAs checked before comparing with GitHub main 359c4ce315276c36d4c2a3ba6160560dd6b21f61. The mirror update preserves all newer operational changes. SDK CI already matched; only its README differed. Consumer identities match the existing snapshot. No source histories, server settings or secrets are backed up by copying files.

Complete local Python 3.12 monorepo suite: 128 passed (SDK 11, Billing 5, Notification 3, GovernGate 109). Both fresh controllers ran 109 tests and passed sandbox-smoke, SAST and secret-detection jobs. Successful security jobs do not constitute a complete audit or zero-findings claim.

## Remaining limits

Freshness is point-in-time at pipeline completion, not atomic at merge. No live ref-movement experiment was performed; rejection paths have unit coverage. Candidate code can forge its JUnit report, so human review remains required; independent attestation is future work. Duo identified an unresolved disabled-legacy-analyzer edge case: optional parameter insertion can hide simultaneous reorder/kind/default changes. This does not drive the fixed-consumer controller, but should be fixed before generic discovery is enabled. Nebius remains optional and disabled pending API approval. Private GitLab URLs require access. Runner host and protection/variable settings were not fully re-audited.

The GitHub connector refused writes (403); the signed-in browser upload workflow was used instead. User enabled Chrome local-file upload access. No credential token was requested or copied. Mirror/docs changes belong on review branches; no new merge is claimed in this log.
