# Security policy

This is a research/portfolio project, not a production service handling real
user data. The deployed demo serves a frozen historical snapshot and accepts
no user-submitted data beyond job-scheduling parameters (duration, power,
deadline) that are never persisted.

## Supported versions

Only the latest commit on `main` and the latest tagged release receive
security fixes.

## Reporting a vulnerability

Please open a GitHub issue, or if the report involves a genuinely sensitive
disclosure (e.g. a credential leak), contact the maintainer directly through
their GitHub profile rather than filing a public issue. Include:

- A description of the issue and its potential impact.
- Steps to reproduce, if applicable.
- Whether it affects the deployed demo, the API server code, or tooling only.

## Scope notes

- The offline Docker demo runs as a non-root user with a read-only
  filesystem (`Dockerfile`), verified in CI (`.github/workflows/ci.yml`,
  `scripts/smoke_docker.sh`).
- API authentication (`X-API-Key`) and rate limiting are optional and
  disabled by default for the keyless demo — see
  [ADR 0019](docs/adr/0019-api-authentication-rate-limiting-and-observability.md)
  for what they do and do not cover (in particular: the in-memory rate
  limiter is not safe across multiple process instances).
- No secrets should ever be committed; `.env` is gitignored and
  `.env.example` documents the expected variables without real values.
