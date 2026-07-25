# Production Readiness and Security Audit

**Repository:** `anfixit/unpaywallbot`  
**Audit date:** 2026-07-25  
**Scope:** application code, outbound networking, Telegram handlers,
Redis, optional account storage, logging, Docker, GitHub Actions,
secrets, dependencies, and open-source project health.

## Executive summary

The original repository contained a useful extraction pipeline and a
substantial unit-test suite, but it was not ready for unattended public
operation or the documented production deployment.

The most important original risks were:

1. arbitrary user URLs could reach private networks and internal services
2. Redis was published on every host interface
3. an empty production allowlist opened the bot to everyone
4. rate limiting was not atomic
5. optional browser credentials could cross a domain boundary
6. raw Telegram identifiers were logged by default
7. CI did not block all quality and security failures
8. Docker and deployment documentation did not match the runtime

The current default runtime is restricted to publicly delivered HTML and
existing public archive snapshots. Optional authenticated browser and
third-party Telegraph functionality remain disabled unless explicitly
configured.

## Audit method

The review combined:

- manual review of every application and infrastructure layer
- threat modeling for untrusted Telegram users and URLs
- Ruff and strict mypy checks
- pytest unit and integration tests
- pip-audit and Bandit
- reproducible production Docker builds
- GitHub Actions checks on each remediation pull request

Live tests against subscriber-only articles are excluded. They are unstable,
may require credentials, and are unsuitable for deterministic CI.

## Threat model

An untrusted user may submit arbitrary text and URLs repeatedly. Protected
assets include the host, Docker network, cloud metadata endpoints, Telegram
and publisher credentials, Redis data, GitHub secrets, and user privacy.

Primary attack and failure classes considered:

- SSRF, redirects, private addresses, and DNS resolution changes
- response decompression and memory exhaustion
- rate-limit races
- browser credential exfiltration
- third-party content disclosure
- direct Redis access
- secret exposure in CI
- partial or lost writes during shutdown
- misleading success metadata and operational logs

## Findings

| ID | Severity | Finding | Status |
| --- | --- | --- | --- |
| SEC-01 | Critical | Arbitrary URL and redirect SSRF | Fixed |
| OPS-01 | Critical | Redis published as `0.0.0.0:6379` | Fixed |
| AUTH-01 | High | Empty production allowlist opened the bot | Fixed |
| CICD-01 | High | CI and deploy shared unsafe context | Fixed |
| CICD-02 | High | Third-party actions received production context | Fixed |
| RATE-01 | High | Rate-limit check and increment were not atomic | Fixed |
| HEAD-01 | High | Login redirect could cross domains | Fixed |
| HEAD-02 | High | Playwright driver was not stopped | Fixed |
| HEAD-03 | High | Browser requests bypassed URL policy | Fixed with residual DNS TOCTOU limitation |
| NET-01 | Medium | No overall extraction timeout | Fixed |
| NET-02 | Medium | Redirect and declared size limits were missing | Fixed |
| NET-03 | High | Chunked or decoded responses could exceed limits | Fixed |
| PRIV-01 | High | Raw Telegram identifiers were logged | Fixed |
| PRIV-02 | Medium | Telegraph transfer was implicit and unescaped | Fixed |
| PRIV-03 | Medium | Runtime models and rate logs exposed IDs or URLs | Fixed |
| ARCHIVE-01 | Medium | Archive fallback created third-party snapshots | Fixed |
| CACHE-01 | Medium | Background cache writes could be lost | Fixed |
| METHOD-01 | Medium | Fallback results used the proposed method label | Fixed |
| REDIS-01 | Medium | Cache statistics used blocking Redis `KEYS` | Fixed |
| LOG-01 | Medium | Concurrent JSONL writes could interleave | Fixed |
| AUTHSTORE-01 | Medium | Credential file was weakly derived and non-atomic | Fixed for one writer process |
| DOCKER-01 | High | Browser files were unavailable to runtime user | Fixed |
| OPS-02 | Medium | Missing health, resource, and log limits | Fixed |
| OPS-03 | Medium | Redis network exposure was excessive | Fixed |
| UX-01 | Medium | Status messages remained after failures | Fixed |
| UX-02 | Medium | User metadata could break Telegram formatting | Fixed |
| DOC-01 | High | Documentation overclaimed compatibility | Fixed |
| OSS-01 | Medium | Missing env and Docker templates | Fixed |
| OSS-02 | Medium | Missing community and security policies | Fixed |
| DEP-01 | Medium | Direct dependency manifest contained unused entries | Fixed |
| INT-01 | Medium | Live publisher compatibility cannot be guaranteed | Accepted limitation |
| EXT-01 | Low | Archives and publishers are external dependencies | Accepted limitation |

## Remediation details

### Outbound network controls

`bot/security/url_guard.py` and the shared HTTP client reject:

- non-HTTP schemes
- embedded credentials
- IP literals
- hostnames without a public-domain form
- ports other than 80 and 443
- DNS results that are private, loopback, link-local, multicast,
  reserved, or otherwise non-global

Every HTTPX request and redirect is checked. Decoded response bytes are
streamed and counted, so chunked, compressed, missing, or incorrect
`Content-Length` headers cannot bypass the configured limit.

The optional Playwright flow validates the initial URL and browser requests,
blocks downloads, service workers, WebSockets, and cross-domain non-GET
requests, and verifies the domain after login. Chromium performs its own
final socket resolution, so hostile DNS environments still require network
isolation. The component remains disabled by default.

### Archive behavior

The archive adapter now performs one read-only request for an existing public
snapshot. It does not submit a URL, create a snapshot, or poll a capture job.
This removes an unexpected third-party side effect and reduces disclosure of
user browsing intent.

### Runtime correctness

Cache persistence is awaited before a successful uncached result is returned.
A cache hit is not written again. This prevents acknowledged results from
losing their cache entry during shutdown.

Each concrete extractor sets its actual method. The orchestrator only applies
the proposed method when the result has no method metadata. An archive
fallback can therefore no longer be recorded as crawler or JS-disabled
extraction.

### Production access and Redis

Production requires either:

- a non-empty `ALLOWED_USERS` JSON array
- `PUBLIC_ACCESS=true`

Rate limits for minute, hour, and day windows are checked and incremented by
one Redis Lua script. Redis failures deny the request rather than silently
removing protection.

Redis has no host port, lives on an internal Compose network, persists through
a named volume, runs read-only without Linux capabilities, and has health and
log-rotation settings. Cache statistics use incremental `SCAN`.

### Privacy and third-party services

Access logs use a keyed HMAC pseudonym unless
`LOG_USER_IDENTIFIERS=true`. Log files use directory mode `0700`, file mode
`0600`, and serialized appends.

Rate-limit logs and model representations use the same pseudonym and domain
metadata. They do not include usernames, raw user IDs, full URLs, article
titles, or article contents.

`TELEGRAPH_ENABLED=false` is the default. When explicitly enabled, article
text and source URLs are escaped before transfer, and the documentation
states that Telegraph is a third party.

### Optional account storage

The optional credential storage now:

- uses a versioned Fernet envelope
- derives each new key with PBKDF2-HMAC-SHA256 and a random salt
- reads the legacy fixed-salt format for migration
- validates every decrypted field
- fails closed for a wrong key or damaged file
- writes through a mode `0600` temporary file, `fsync`, and `os.replace`
- serializes writes within one process
- replaces duplicate records
- reads passwords through `getpass` or stdin, never process arguments

One file must have one writer process. The default runtime does not enable
this component. See `docs/ACCOUNT_STORAGE.md`.

### CI, image, and deployment

Pull-request CI has read-only repository permissions and no production
environment. Blocking checks cover:

- Ruff
- strict mypy
- pytest and coverage
- pip-audit
- Bandit
- production Docker build

The release workflow runs only after successful CI on `main`, publishes
immutable commit-SHA and `latest` tags to GHCR, uses native OpenSSH, requires
pinned `known_hosts`, writes the production environment with mode `0600`,
and deploys only when `DEPLOY_ENABLED=true`.

### Dependencies and open-source package

Unused direct dependency declarations were removed and `uv.lock` was
regenerated without upgrading resolved package versions. The repository now
includes bilingual README files, license, changelog, contribution guide,
security policy, support guide, code of conduct, issue templates, deployment
documentation, and this audit record.

## Accepted limitations

- A domain map entry is not a guarantee of extraction.
- Public archives can be unavailable or rate limited.
- Publisher markup and anti-bot controls change without notice.
- Extracted HTML can be incomplete or noisy.
- The bot does not establish legal entitlement to content.
- Deterministic CI cannot prove live publisher compatibility.
- Playwright has a residual DNS time-of-check/time-of-use limitation.
- Optional account storage supports one writer process per file.

## Production release criteria

Before enabling deployment:

- all CI jobs must pass
- the Docker image must build from committed `uv.lock`
- staging must verify `/start`, `/help`, one public article, an invalid URL,
  a timeout, Redis loss, and graceful shutdown
- production secrets must live in the protected GitHub Environment
- the server must use a dedicated deploy user and key-only SSH
- Redis must have no host port
- `DEPLOY_ENABLED` must remain false until server bootstrap is complete

## Follow-up review triggers

Repeat the security review after changes to:

- URL validation, redirects, DNS, or HTTP transports
- Playwright or account workflows
- Redis and cache lifecycle
- logging or user identifiers
- deployment credentials and workflow permissions
- Docker network topology
- public access policy
