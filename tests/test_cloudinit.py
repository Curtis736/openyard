from __future__ import annotations

from app.cloudinit import render_cloud_init, resolve_ssh_key


def test_resolve_explicit_key() -> None:
    assert resolve_ssh_key("ssh-ed25519 AAAA demo@host").startswith("ssh-ed25519")


def test_render_includes_key() -> None:
    body = render_cloud_init("ssh-ed25519 AAAA demo@host")
    assert "#cloud-config" in body
    assert "ssh-ed25519 AAAA demo@host" in body
    assert "ubuntu" in body


def test_render_empty_without_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENYARD_SSH_AUTHORIZED_KEY", raising=False)
    assert render_cloud_init("") == ""
