# Contributing

Thank you for improving Unpaywall Bot.

## Responsible scope

Contributions must preserve the project's research and defensive focus.

Do not submit:

- credentials, cookies, access tokens, or session files
- copies of copyrighted subscriber-only articles
- CAPTCHA, DRM, or server-side authorization bypasses
- code that targets private networks or weakens SSRF controls
- publication claims without tests and reproducible evidence

Security-sensitive changes should start with a private vulnerability report rather than a public issue.

## Development setup

```bash
git clone https://github.com/anfixit/unpaywallbot.git
cd unpaywallbot
cp .env.example .env.local
uv sync --locked --all-extras
```

Set test-safe values in `.env.local`, start Redis, and install Chromium when working on Playwright code:

```bash
docker run --rm -d \
  --name unpaywallbot-redis \
  -p 127.0.0.1:6379:6379 \
  redis:7-alpine

uv run playwright install chromium
```

## Before changing code

1. Search existing issues and pull requests.
2. Open an issue for large features or architecture changes.
3. Keep one pull request focused on one problem.
4. Add or update tests before changing production behavior.
5. Avoid unrelated formatting changes.

## Quality gates

Run:

```bash
uv run ruff check bot tests scripts
uv run mypy bot
uv run pytest
uvx bandit -r bot -q
docker build -t unpaywallbot:contrib .
```

Dependency changes also require:

```bash
uv lock
uv export --locked --no-dev \
  --format requirements-txt \
  --output-file requirements-audit.txt
uvx pip-audit -r requirements-audit.txt
```

Commit both `pyproject.toml` and `uv.lock` when dependencies change.

## Tests

Prefer deterministic tests using:

- synthetic HTML
- small stored fixtures that do not reproduce protected articles
- HTTPX `MockTransport`
- mocked Telegram and Redis clients
- explicit tests for error and timeout paths

Do not make normal CI depend on a live publisher, subscription account, CAPTCHA, or public archive response.

Network safety changes must test:

- loopback and private IPv4
- IPv6 loopback and local ranges
- cloud metadata targets
- DNS rebinding
- redirects to blocked targets
- response and timeout limits

## Style

- Python 3.12
- type annotations for public functions
- Ruff-compatible code
- line length 79
- docstrings for public modules, classes, and functions
- no broad exception swallowing without logging
- no secrets or personal data in logs

Use clear English identifiers. User-facing Telegram messages may remain Russian.

## Commit messages

Use concise imperative or Conventional Commit style, for example:

```text
fix: reject private redirect targets
test: cover rate-limit concurrency
docs: clarify production access policy
```

## Pull requests

A pull request should include:

- problem statement
- implementation summary
- security and privacy impact
- validation commands
- screenshots only when UI behavior changes
- migration or rollback notes when configuration changes

The PR must pass all GitHub Actions checks before review.

## Documentation

Update documentation when changing:

- environment variables
- Docker or deployment behavior
- publication configuration
- security boundaries
- user-facing commands
- operational limits

Keep `README.md`, `README.ru.md`, `.env.example`, and `docs/AUDIT.md` consistent.

## License

By contributing, you agree that your contribution is provided under the repository's AGPL-3.0 license.
