from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.image_policy import (
    clear_prefix_cache,
    matches_allowlist,
    rejects_latest,
    validate_workload_image,
)
from app.models import WorkloadCreate


def setup_function() -> None:
    clear_prefix_cache()


def test_rejects_latest_tag() -> None:
    assert rejects_latest("nginxinc/nginx-unprivileged:latest")


def test_rejects_untagged() -> None:
    assert rejects_latest("nginxinc/nginx-unprivileged")


def test_accepts_pinned() -> None:
    assert rejects_latest("nginxinc/nginx-unprivileged:1.27-alpine") is None


def test_allowlist_default_nginxinc() -> None:
    assert matches_allowlist("nginxinc/nginx-unprivileged:1.27-alpine")


def test_denies_random_registry() -> None:
    with pytest.raises(ValueError, match="allowlist"):
        validate_workload_image("evil.example/malware:1.0")


def test_workload_create_uses_policy() -> None:
    with pytest.raises(ValidationError):
        WorkloadCreate(name="x", image="nginxinc/nginx-unprivileged:latest")


def test_custom_prefixes(monkeypatch) -> None:
    monkeypatch.setenv("OPENYARD_ALLOWED_IMAGE_PREFIXES", "myreg.io/team/")
    clear_prefix_cache()
    assert validate_workload_image("myreg.io/team/app:1.2.3") == "myreg.io/team/app:1.2.3"
    with pytest.raises(ValueError):
        validate_workload_image("nginxinc/nginx-unprivileged:1.27-alpine")
    monkeypatch.delenv("OPENYARD_ALLOWED_IMAGE_PREFIXES", raising=False)
    clear_prefix_cache()
