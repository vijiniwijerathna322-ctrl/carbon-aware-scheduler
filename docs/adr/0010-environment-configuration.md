# D10: Environment-based application configuration

## Context

Commands need typed configuration and optional EIA credentials. Their behavior should
remain predictable when invoked from another working directory, and credentials must
not appear in representations or logs.

## Decision

Use pydantic-settings with environment variables overriding a project-root `.env` file.
Store the EIA key as SecretStr and require it only in operations that use the live API.
Resolve default and relative data/model paths against the nearest pyproject.toml above
the package; if unavailable (for example an installed wheel), use the process working
directory. Absolute overrides are preserved. Validate log levels explicitly.

Region metadata remains assigned to config/regions.yaml in the ingestion plan; this
foundation implements the application-settings portion of spec decision D10.

## Consequences

Import, help and offline commands work without credentials. Environment overrides
remain portable, and development commands use stable paths. A wheel deployment should
set absolute directory overrides to avoid depending on its working directory.
