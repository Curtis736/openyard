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
