"""Politique d’images workloads (allowlist + refus :latest)."""

from __future__ import annotations

import os
from functools import lru_cache

DEFAULT_ALLOWED_PREFIXES = (
    "nginxinc/",
    "nginx:",
    "hashicorp/",
    "ghcr.io/curtis736/",
    "registry.k8s.io/",
)


class ImagePolicyError(ValueError):
    """Image refusée par la politique OpenYard."""


@lru_cache(maxsize=1)
def allowed_prefixes() -> tuple[str, ...]:
    raw = os.getenv("OPENYARD_ALLOWED_IMAGE_PREFIXES", "").strip()
    if not raw:
        return DEFAULT_ALLOWED_PREFIXES
    parts = tuple(p.strip() for p in raw.split(",") if p.strip())
    return parts or DEFAULT_ALLOWED_PREFIXES


def clear_prefix_cache() -> None:
    allowed_prefixes.cache_clear()
