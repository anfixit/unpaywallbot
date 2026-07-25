# Security Policy

## Supported versions

Security fixes are applied to the latest revision of `main`. Older commits, forks, and private deployments are not maintained by this repository.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability.

Preferred reporting path:

1. Open the repository `Security` tab.
2. Choose `Advisories`.
3. Select `Report a vulnerability`.
4. Include the affected revision, impact, reproduction steps, and a proposed mitigation when available.

If private vulnerability reporting is unavailable, contact the maintainer through the GitHub profile without publishing exploit details. Wait for a private communication channel before sending secrets, tokens, or a complete proof of concept.

## Scope

High-priority reports include:

- SSRF, DNS rebinding, redirect validation, and private-network access
- Telegram bot token or GitHub Actions secret exposure
- authentication or account credential leakage
- container escape or unintended host access
- Redis exposure or unauthorized data access
- allowlist or rate-limit bypass
- arbitrary code execution
- unsafe deployment workflow behavior
- personal data exposure in logs

Publication layout breakage and inability to extract a specific article are normally compatibility bugs, not security vulnerabilities.

## Safe research

When validating a report:

- use infrastructure and accounts you own or are authorized to test
- do not access third-party private services
- do not collect or publish user data
- do not include real credentials or subscriber-only article copies
- minimize requests and avoid service disruption
- stop testing after demonstrating the minimum necessary impact

## Disclosure process

The maintainer will:

1. acknowledge the report privately
2. reproduce and assess severity
3. prepare a fix and regression tests
4. coordinate a release and disclosure
5. credit the reporter when requested and appropriate

Response times are best effort because this is a volunteer-maintained project.

## Secret exposure

If a secret appears in a commit, issue, pull request, CI log, or chat:

1. rotate it immediately
2. disable the affected key or token
3. remove it from current repository content
4. review audit logs for misuse
5. clean Git history when necessary
6. document the incident without republishing the secret

Deleting the visible text is not sufficient because copies may already exist.
