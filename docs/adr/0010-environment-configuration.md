# D10: Environment-based application configuration

## Context

Commands need typed configuration and optional EIA credentials. Their behavior should
remain predictable when invoked from another working directory, and credentials must
not appear in representations or logs.

## Decision

Use pydantic-settings with environment variables overriding a project-root `.env` file.
Explicit constructor arguments accept normal field names and take precedence over both
sources, including an explicit `None` credential for offline operation.
Store the EIA key as SecretStr and require it only in operations that use the live API.
Resolve default and relative data/model paths against the nearest pyproject.toml above
the package; if unavailable (for example an installed wheel), use the process working
directory. Absolute overrides are preserved. Validate log levels explicitly.

Region metadata is loaded from project-relative `config/regions.yaml`. The typed registry
validates safe codes, IANA timezones and coordinates. Unknown lookups list configured
choices. CISO uses America/Los_Angeles, latitude 36.7 and longitude -119.4; stored data
continues to use UTC.

## Consequences

Import, help and offline commands work without credentials. Environment overrides
remain portable, and development commands use stable paths. A wheel deployment should
set absolute directory overrides to avoid depending on its working directory.
