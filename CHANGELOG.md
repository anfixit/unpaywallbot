# Changelog

All notable changes to this project are documented here.

The format follows Keep a Changelog principles. The project uses semantic versioning for tagged releases.

## [Unreleased]

### Added

- optional `ARCHIVE_PROXY_URL` for public-archive requests, with an
  `archive-proxy` Compose profile and deployment from a `vless://` secret
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
- security, contribution, conduct, support, audit, deployment, and account-storage documentation

### Changed

- `TELEGRAPH_ENABLED` publishes every article instead of only text longer
  than one Telegram message, and the production workflow reads the flag
  from a secret rather than hardcoding it off
- an article shorter than the partial-content threshold on a domain with a
  known paywall is reported as a public fragment instead of a full text
- the archive adapter uses a short connect timeout, so an unreachable
  archive no longer consumes the request budget
- the archive adapter recognises the anti-bot challenge and pauses for
  thirty minutes instead of repeating requests it cannot satisfy
- application logging is configured on the root logger, so every module
  reaches the rotating log file instead of only the entry point
- noisy third-party loggers are limited to `WARNING`
- crawler-view retries after `403` or `429` wait with exponential backoff
- extraction failures caused by network or configuration errors fall back
  to the public archive instead of failing the whole request
- `mypy` also checks `scripts/`
- container limits are sized for a 1 GB host, and Redis caps the article
  cache with `maxmemory` and an LRU policy instead of growing without bound
- deployment prunes untagged images older than a week, so repeated releases
  no longer fill the server disk
- Redis is no longer published to the host
- Docker runtime is non-root, read-only, resource-limited, and log-rotated
- Playwright browser installation is available to the runtime user
- Telegram output uses safe HTML escaping
- authenticated browser extraction refuses cross-domain login redirects
- optional browser requests are checked against outbound URL policy
- Telegraph publication is explicit opt-in and escapes article HTML
- archive relay reads existing public snapshots and never creates new ones
- Redis cache statistics use incremental scanning instead of `KEYS`
- cache writes complete before a successful request is returned
- production deployment uses immutable image tags
- account storage uses a salted versioned encryption envelope
- account storage writes are validated, serialized, and atomic

### Fixed

- log records from every module except `bot.main` were discarded
- article parts longer than the Telegram limit once the part header was
  added, which dropped the text of long articles
- access logs never recorded paywall or article metadata, because no
  handler published the processed request
- log-report script counted only raw `user_id` records, so pseudonymous
  logs produced empty user statistics
- diagnostic script `scripts/test_paywall.py` called `process_url` with an
  argument that does not exist
- German freemium platform logged full article URLs instead of domains
- cache reads raised instead of degrading when Redis was unavailable
- tests required manual environment variables to run locally
- deploy workflow ran the production job on every successful `main` build,
  although the documented `DEPLOY_ENABLED` gate was never implemented
- deployment guide listed `GHCR_USERNAME` and `GHCR_TOKEN` secrets that the
  workflow does not read
- deployment notification could be skipped entirely when the issue comment
  step failed first, and both workflows treated missing notification secrets
  as a silent success
- Playwright driver leak
- stale processing messages after failures
- URL parsing with trailing punctuation
- concurrent JSONL log writes
- rate-limit race and sliding TTL behavior
- extraction fallback being recorded as the proposed primary method
- cache writes being lost during process shutdown
- misleading documentation about guaranteed publication support

### Security

- pull-request workflows no longer receive production deployment context
- third-party SSH and notification actions were removed from deployment
- raw Telegram identifiers are no longer logged by default
- request models and rate-limit logs no longer expose raw user IDs or URLs
- production cannot start accidentally with an empty allowlist
- account passwords are no longer accepted as process arguments
- unreadable credential storage fails closed instead of resetting silently

## [0.1.0]

Initial research implementation with Telegram handlers, paywall classification, extraction strategies, Redis caching, tests, Docker, and early deployment automation.
