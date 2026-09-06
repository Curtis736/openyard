"""cloud-init pour Multipass (injection SSH)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def resolve_ssh_key(explicit: str = "") -> str:
    key = (explicit or "").strip()
    if key:
        return key
    return os.getenv("OPENYARD_SSH_AUTHORIZED_KEY", "").strip()


def render_cloud_init(ssh_authorized_key: str) -> str:
    key = resolve_ssh_key(ssh_authorized_key)
    if not key:
        return ""
    # single-line key expected
    return (
        "#cloud-config\n"
        "users:\n"
        "  - default\n"
        "  - name: ubuntu\n"
        "    ssh_authorized_keys:\n"
        f"      - {key}\n"
        "ssh_pwauth: false\n"
    )


def write_cloud_init_file(ssh_authorized_key: str) -> Path | None:
    body = render_cloud_init(ssh_authorized_key)
    if not body:
        return None
    fd, name = tempfile.mkstemp(prefix="openyard-cloudinit-", suffix=".yaml")
    path = Path(name)
    os.close(fd)
    path.write_text(body)
    return path
