from __future__ import annotations

import os
import secrets


def api_key_configured() -> bool:
    return bool(os.getenv("OPENYARD_API_KEY", "").strip())


def expected_api_key() -> str:
    return os.getenv("OPENYARD_API_KEY", "").strip()


def is_public_path(path: str) -> bool:
    if path in {"/", "/console", "/health", "/metrics", "/docs", "/openapi.json", "/redoc"}:
        return True
    if path.startswith("/assets/") or path.startswith("/docs/") or path.startswith("/redoc/"):
        return True
    return False


def api_key_valid(provided: str | None) -> bool:
    expected = expected_api_key()
    if not expected:
        return True
    if not provided:
        return False
    if len(provided) != len(expected):
        return False
    return secrets.compare_digest(provided, expected)
