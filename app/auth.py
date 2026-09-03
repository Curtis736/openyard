from __future__ import annotations

import os
import secrets
from dataclasses import dataclass

from app.models import Project


def admin_api_key() -> str:
    return os.getenv("OPENYARD_API_KEY", "").strip()


def api_key_configured() -> bool:
    """Auth admin globale activée."""
    return bool(admin_api_key())


def is_public_path(path: str) -> bool:
    if path in {
        "/",
        "/console",
        "/health",
        "/metrics",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/compute/images",
    }:
        return True
    if path.startswith("/assets/") or path.startswith("/docs/") or path.startswith("/redoc/"):
        return True
    return False


def is_open_signup_path(method: str, path: str) -> bool:
    return method.upper() == "POST" and path == "/projects"


def generate_api_key() -> str:
    return f"oy_{secrets.token_urlsafe(24)}"


def keys_equal(provided: str, expected: str) -> bool:
    if not expected or not provided:
        return False
    if len(provided) != len(expected):
        return False
    return secrets.compare_digest(provided, expected)


@dataclass(frozen=True)
class Identity:
    """Contexte d’appel : admin, projet, ou anonyme → projet default."""

    kind: str  # admin | project | anonymous
    project: Project | None = None

    @property
    def project_name(self) -> str:
        if self.project is None:
            return "default"
        return self.project.name

    @property
    def namespace(self) -> str:
        if self.project is None:
            return os.getenv("OPENYARD_NAMESPACE", "openyard")
        return self.project.namespace


def resolve_identity(api_key: str | None, *, find_by_key, default_project) -> Identity | None:
    """
    Résout l’identité.
    - clé admin → admin (vue globale, projet default pour writes sans header projet)
    - clé projet → scopé
    - pas de clé → anonymous sur default si default.api_key vide et pas d’admin key obligatoire
    - sinon None (401)
    """
    provided = (api_key or "").strip()
    admin = admin_api_key()

    if provided and admin and keys_equal(provided, admin):
        return Identity(kind="admin", project=default_project)

    if provided:
        project = find_by_key(provided)
        if project is not None:
            return Identity(kind="project", project=project)
        if admin:
            return None
        return None

    # Sans clé
    if admin:
        return None
    default = default_project
    if default is not None and not default.api_key:
        return Identity(kind="anonymous", project=default)
    return None
