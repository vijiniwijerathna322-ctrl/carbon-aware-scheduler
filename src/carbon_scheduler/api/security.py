"""Optional API-key authentication; disabled when no keys are configured."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader

from carbon_scheduler.config import Settings

_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(request: Request, key: Annotated[str | None, Depends(_header)] = None) -> None:
    """No-op when `API_KEYS` is unset; otherwise require a matching `X-API-Key`."""
    settings: Settings = request.app.state.settings
    allowed = settings.api_key_set()
    if not allowed:
        return
    if key is None or key not in allowed:
        raise HTTPException(status_code=401, detail={"error": "invalid_api_key"})
