## Problem

Describe the problem and why it matters.

## Changes

- 

## Security and privacy impact

- [ ] User-controlled URLs or redirects are affected
- [ ] Authentication, credentials, or secrets are affected
- [ ] Logging or personal data is affected
- [ ] Docker, networking, CI/CD, or deployment is affected
- [ ] No security or privacy boundary changes

Explain checked items:

## Validation

- [ ] `uv run ruff check bot tests scripts`
- [ ] `uv run mypy bot`
- [ ] `uv run pytest`
- [ ] `uvx bandit -r bot -q`
- [ ] Docker image builds
- [ ] Documentation and `.env.example` updated when required

Commands and results:

```text

```

## Migration and rollback

Describe configuration changes, compatibility impact, and rollback steps. Write `Not required` when none.

## Responsible-use checklist

- [ ] No credentials, cookies, tokens, or private data are included
- [ ] No subscriber-only article text is included
- [ ] Tests are deterministic and do not depend on unauthorized access
- [ ] Publication compatibility claims are evidence-based and limited
