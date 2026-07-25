# Production Readiness and Security Audit

**Repository:** `anfixit/unpaywallbot`  
**Audit date:** 2026-07-25  
**Scope:** application code, outbound networking, Telegram handlers, Redis, authentication helpers, logging, Docker, GitHub Actions, secrets handling, and open-source project health.

## Executive summary

The original repository contained a useful extraction pipeline and a substantial unit-test suite, but it was not safe to expose as an unattended public bot or deploy as documented.

The highest-risk findings were:

1. user-controlled URLs could reach private networks, localhost, cloud metadata services, or internal Docker services
2. Redis was published on every host interface
3. production access was open when the allowlist was empty
4. rate limiting was vulnerable to concurrent check/increment races
5. the authenticated browser flow could follow a cross-domain login redirect and did not stop the Playwright driver
6. access logs stored raw Telegram identifiers by default
7. CI allowed type and dependency audit failures and mixed pull-request validation with production deployment
8. project documentation claimed support and deployment behavior that were not guaranteed by the code

The remediation branch addresses the critical and high-priority production risks without expanding access-control circumvention functionality. The default runtime remains focused on publicly delivered HTML and public archive snapshots.

## Audit method

The review combined:

- manual source review of configuration, handlers, middleware, fetchers, extraction, storage, authentication helpers, Docker, and workflows
- threat modeling for user-controlled URLs and redirects
- static checks through Ruff, mypy, Bandit, and pip-audit
- unit and integration tests through pytest
- reproducible Docker image build
- GitHub Actions validation on pull request `#1`

Live extraction against subscriber-only articles is intentionally excluded. Such tests are unstable, may require credentials, and are not appropriate for deterministic CI.

## Threat model

The production bot must assume that an untrusted Telegram user can submit arbitrary text and URLs repeatedly.

Protected assets include:

- the host operating system
- Docker services and networks
- cloud metadata endpoints
- Telegram bot credentials
- publisher account credentials in optional research environments
- Redis data and rate-limit state
- GitHub Actions production secrets
- user identifiers and access logs

Primary adversarial actions considered:

- SSRF, redirect abuse, and DNS time-of-check/time-of-use risks
- redirecting a safe URL to a private address
- resource exhaustion through large responses or long extraction chains
- rate-limit races
- credential exfiltration through login redirects
- secret exposure in CI logs or third-party actions
- direct Redis access
- accidental public deployment
- log-based privacy leakage

## Findings

| ID | Severity | Finding | Status |
| --- | --- | --- | --- |
| SEC-01 | Critical | Arbitrary URL and redirect SSRF | Fixed |
| OPS-01 | Critical | Redis published as `0.0.0.0:6379` | Fixed |
| AUTH-01 | High | Empty production allowlist opened the bot to everyone | Fixed |
| CICD-01 | High | CI and deployment shared one workflow and non-blocking security checks | Fixed |
| CICD-02 | High | Third-party SSH and notification actions received production context | Fixed |
| RATE-01 | High | Rate-limit check and increment were not atomic | Fixed |
| HEAD-01 | High | Cross-domain login redirect could receive credentials | Fixed |
| HEAD-02 | High | Playwright driver was not stopped | Fixed |
| PRIV-01 | High | Raw Telegram identifiers were logged by default | Fixed |
| DOCKER-01 | High | Browser installation path was not reliable for the non-root runtime user | Fixed |
| DOC-01 | High | README overclaimed publication support and deployment readiness | Fixed |
| NET-01 | Medium | No overall extraction timeout | Fixed |
| NET-02 | Medium | Redirect count and declared response size were unbounded | Fixed |
| NET-03 | High | Chunked or decompressed responses could exceed the memory limit | Fixed |
| HEAD-03 | High | Playwright requests bypassed the shared outbound URL guard | Fixed with documented residual DNS TOCTOU risk |
| PRIV-02 | Medium | Long article text was sent to Telegraph by default and HTML was not escaped | Fixed |
| REDIS-01 | Medium | Cache statistics used blocking Redis `KEYS` | Fixed |
| UX-01 | Medium | Processing messages could remain after errors | Fixed |
| UX-02 | Medium | User-controlled metadata could break Telegram Markdown | Fixed |
| OPS-02 | Medium | No container healthcheck, resource limits, or log rotation | Fixed |
| OPS-03 | Medium | Redis and bot shared an unnecessarily exposed network | Fixed |
| LOG-01 | Medium | Concurrent JSONL writes could interleave | Fixed |
| OSS-01 | Medium | Missing environment template and Docker ignore file | Fixed |
| OSS-02 | Medium | Missing security, contribution, conduct, support, and audit policies | Fixed |
| DEP-01 | Medium | Development dependency declarations are duplicated in `pyproject.toml` | Deferred |
| AUTHSTORE-01 | Medium | Optional account storage needs an atomic encrypted-file format and migration design | Deferred, disabled by default |
| INT-01 | Medium | Publication adapters have no stable live compatibility guarantee | Accepted limitation |
| EXT-01 | Low | Archive and publisher availability are external dependencies | Accepted limitation |

## Remediation details

### SEC-01: SSRF

Added `bot/security/url_guard.py` and a shared safe HTTP client.

The control rejects:

- non-HTTP schemes
- embedded username or password
- IP literals
- hostnames without a public domain form
- ports other than 80 and 443
- DNS results that are loopback, private, link-local, multicast, reserved, or otherwise non-global

DNS resolution is repeated for each outbound request. HTTPX request hooks validate redirect targets before they are contacted. This validation reduces common SSRF paths but does not claim cryptographic protection against every DNS time-of-check/time-of-use race because the transport performs its own connection-time resolution.

Tests cover loopback, RFC1918 networks, IPv6 loopback, and the common `169.254.169.254` metadata address.

### NET-03: actual response-size enforcement

The shared HTTP client now streams and counts decoded response bytes. It
rejects oversized responses even when `Content-Length` is absent,
incorrect, chunked, or smaller than the decompressed body.

### HEAD-03: Playwright outbound boundaries

The optional authenticated browser now validates its initial URL, routes
browser HTTP requests through the public-URL guard, blocks cross-domain
non-GET requests, blocks service workers, and verifies the domain after
login. It remains disabled in the default runtime. Because Chromium owns
the final socket resolution, deployments with hostile DNS assumptions
should keep this optional component disabled or isolate it at the network
layer.

### PRIV-02: explicit Telegraph consent

Publishing long text to Telegraph is disabled by default through
`TELEGRAPH_ENABLED=false`. When explicitly enabled, article text and
source URLs are HTML-escaped before submission. Documentation now states
that the content is transferred to a third-party service.

### REDIS-01: non-blocking cache statistics

Cache statistics now iterate keys with Redis `SCAN` instead of the
blocking `KEYS` command.

### OPS-01: Redis exposure

Removed the host port mapping. Redis now:

- uses only an internal Compose network
- exposes port 6379 only to attached containers
- persists data through a named volume
- runs with a read-only root filesystem
- has no Linux capabilities
- has a healthcheck and log rotation

### AUTH-01: production access

Production startup now requires one of:

- a non-empty `ALLOWED_USERS` JSON array
- `PUBLIC_ACCESS=true`

Development and testing can still run without an allowlist.

### RATE-01: atomic limiting

Minute, hour, and day limits are checked and incremented by one Redis Lua script. The script:

- performs the limit check and increment atomically
- sets TTL only when a counter is first created
- returns the blocked time window to the middleware
- fails closed when Redis is unavailable

### HEAD-01 and HEAD-02: authenticated browser safety

The experimental authenticated browser flow now:

- refuses cross-domain login redirects
- requires email, password, and submit elements before submitting
- closes page, context, browser, and Playwright driver
- remains disabled in the default runtime

### PRIV-01 and LOG-01: access logs

By default, logs contain a keyed HMAC pseudonym rather than raw Telegram identifiers.

Raw identifiers require `LOG_USER_IDENTIFIERS=true`.

Log directories and files are created with modes `0700` and `0600`. Writes are serialized with an asynchronous lock.

### CICD-01 and CICD-02: workflows

Pull-request CI has read-only repository permissions and no production environment.

Blocking jobs cover:

- Ruff
- mypy
- pytest and coverage
- pip-audit
- Bandit
- Docker image build

The release workflow:

- runs after successful CI on `main`
- publishes immutable commit-SHA and `latest` tags to GHCR
- uses native OpenSSH rather than third-party deployment actions
- requires a pinned `known_hosts` secret
- creates the production env file with mode `0600`
- deploys only when `DEPLOY_ENABLED=true`
- verifies the container healthcheck after activation

## Deferred items

### DEP-01: dependency declaration cleanup

`pyproject.toml` currently contains overlapping optional and dependency-group declarations. Changing these declarations requires regenerating and reviewing `uv.lock` in a controlled environment.

Recommended follow-up:

1. retain one `dependency-groups.dev` definition
2. remove the duplicate Playwright optional group if headless remains a core dependency
3. add project metadata and package build configuration if the project is to be distributed through PyPI
4. run `uv lock --upgrade` only in a dedicated dependency update PR

### AUTHSTORE-01: account storage format

The optional encrypted account manager is not connected to the default bot runtime. Before enabling it in production:

1. add atomic temporary-file replacement
2. add an explicit file-format version
3. store a random per-file KDF salt
4. provide migration and key-rotation procedures
5. add a process-level and cross-process write lock
6. define credential retention and deletion policy

## Accepted limitations

- A publication map entry is not a guarantee of extraction.
- Public archive services may be unavailable or rate limited.
- HTML extraction can return incomplete or noisy text when site markup changes.
- The bot does not establish legal entitlement to content.
- No deterministic CI can prove live compatibility with frequently changing publisher sites.

## Release criteria

The pull request can be considered production-ready when:

- all CI jobs pass
- the Docker image builds from the committed lock file
- a local or staging bot completes `/start`, `/help`, a public article request, an invalid URL request, and a timeout path
- production secrets are stored in a protected GitHub Environment
- the server has a dedicated deployment user and key-only SSH
- Redis has no host port
- `DEPLOY_ENABLED` remains disabled until server bootstrap is complete

## Follow-up review

Repeat the security review after any change to:

- URL validation or HTTP clients
- redirect behavior
- authenticated browser workflows
- account storage
- deployment credentials
- Docker network topology
- public access policy
