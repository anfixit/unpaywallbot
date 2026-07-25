# Changelog

All notable changes to this project are documented here.

The format follows Keep a Changelog principles. The project uses semantic versioning for tagged releases.

## [Unreleased]

### Added

- SSRF guard for URLs, redirects, DNS rebinding, private networks, IP literals, credentials, and non-standard ports
- shared safe HTTP client with redirect and decoded response-size limits
- production request timeout and controlled error handling
- private-by-default production access policy
- atomic Redis rate limiting
- privacy-preserving access logs
- container healthcheck
- `.env.example` and `.dockerignore`
- blocking CI for lint, types, tests, dependency audit, security scan, and Docker build
- GHCR release and native OpenSSH deployment workflow
- English and Russian README files
- security, contribution, conduct, support, audit, and deployment documentation

### Changed

- Redis is no longer published to the host
- Docker runtime is non-root, read-only, resource-limited, and log-rotated
- Playwright browser installation is available to the runtime user
- Telegram output uses safe HTML escaping
- authenticated browser extraction refuses cross-domain login redirects
- optional browser requests are checked against outbound URL policy
- Telegraph publication is explicit opt-in and escapes article HTML
- Redis cache statistics use incremental scanning instead of `KEYS`
- production deployment uses immutable image tags

### Fixed

- Playwright driver leak
- stale processing messages after failures
- URL parsing with trailing punctuation
- concurrent JSONL log writes
- rate-limit race and sliding TTL behavior
- misleading documentation about guaranteed publication support

### Security

- pull-request workflows no longer receive production deployment context
- third-party SSH and notification actions were removed from deployment
- raw Telegram identifiers are no longer logged by default
- production cannot start accidentally with an empty allowlist

## [0.1.0]

Initial research implementation with Telegram handlers, paywall classification, extraction strategies, Redis caching, tests, Docker, and early deployment automation.
