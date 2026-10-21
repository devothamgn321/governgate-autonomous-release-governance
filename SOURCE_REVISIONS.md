# GitLab snapshot revisions

The GovernGate and SDK snapshots were checked against downloaded GitLab main archives on October 21, 2026. Consumer commits match the fresh controller evidence. Repository histories were not rewritten or combined; this file preserves the source identity for each snapshot.

| Project | GitLab repository | Source commit |
| --- | --- | --- |
| GovernGate | <https://gitlab.com/governgate2/governgate> | `84e6779625460fe29406a5a15c9949f4ee1b206c` |
| core-auth-sdk | <https://gitlab.com/governgate2/core-auth-sdk> | `bac25944d996acafd3a6fa3e4d2833164f3aaa3f` |
| billing-service | <https://gitlab.com/governgate2/billing-service> | `1c9cba0941a7e5c964177863defc4174710622d4` |
| notification-service | <https://gitlab.com/governgate2/notification-service> | `676cbdc7811cdf0af3490ebd6897b692e6ad7368` |

The SDK bridge is deployed on main and its six existing security/test/build jobs are preserved. GovernGate MR !6 is merged; its post-review freshness stage is deployed. See [the live execution log](LIVE_VERIFICATION_2026-10-21.md) for exact runs, retries and remaining limitations.

Snapshots preserve source files, not GitLab settings, secrets, memberships, runners or the complete upstream Git history. This repository never stores controller credentials.
