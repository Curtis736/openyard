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


def _split_tag(image: str) -> tuple[str, str | None]:
    # ignore digests for tag check: repo@sha256:...
    if "@" in image:
        return image.split("@", 1)[0], None
    if image.count(":") == 0:
        return image, None
    # registry:port/repo:tag → last colon is tag if no slash after it
    name, maybe_tag = image.rsplit(":", 1)
    if "/" in maybe_tag:
        return image, None
    return name, maybe_tag


def rejects_latest(image: str) -> str | None:
    _, tag = _split_tag(image)
    if tag is None:
        return "tag d’image requis (refuser l’implicite :latest)"
    if tag.lower() == "latest":
        return "tag :latest interdit"
    return None
