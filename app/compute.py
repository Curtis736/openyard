from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from threading import Lock

from app.cloudinit import write_cloud_init_file
from app.linux_images import multipass_alias, resolve_linux_image
from app.models import Instance, InstanceCreate

logger = logging.getLogger("openyard.compute")


class ComputeError(RuntimeError):
    """Échec d’une opération compute (VM Linux)."""


@dataclass(frozen=True)
class InstanceRuntime:
    status: str
    ipv4: str = ""
    message: str = ""


def compute_driver_name() -> str:
    raw = os.getenv("OPENYARD_COMPUTE", "auto").strip().lower()
    if raw in {"0", "false", "off", "no"}:
        return "off"
    if raw in {"multipass", "mp"}:
        return "multipass"
    if raw in {"sim", "simulate", "mock"}:
        return "sim"
    if shutil.which("multipass"):
        return "multipass"
    return "sim"


def compute_enabled() -> bool:
    return compute_driver_name() != "off"


class _SimDriver:
    """VM Linux simulées (Ubuntu) — CI / démo sans hyperviseur."""

    def __init__(self) -> None:
        self._state: dict[str, InstanceRuntime] = {}
        self._lock = Lock()
        self._ip_seq = 10

    def launch(self, payload: InstanceCreate) -> InstanceRuntime:
        meta = resolve_linux_image(payload.image)
        with self._lock:
            self._ip_seq += 1
            runtime = InstanceRuntime(
                status="running",
                ipv4=f"10.88.0.{self._ip_seq}",
                message=(
                    f"VM Linux simulée · {meta['name']} · "
                    f"{payload.vcpus} vCPU · {payload.memory_mb} MiB"
                ),
            )
            self._state[payload.name] = runtime
            return runtime

    def status(self, name: str) -> InstanceRuntime:
        with self._lock:
            return self._state.get(
                name,
                InstanceRuntime(status="unknown", message="VM Linux inconnue (sim)"),
            )

    def stop(self, name: str) -> InstanceRuntime:
        with self._lock:
            current = self._state.get(name)
            if current is None:
                raise ComputeError(f"VM Linux introuvable : {name}")
            runtime = InstanceRuntime(
                status="stopped",
                ipv4=current.ipv4,
                message="VM Linux arrêtée (sim)",
            )
            self._state[name] = runtime
            return runtime

    def start(self, name: str) -> InstanceRuntime:
        with self._lock:
            current = self._state.get(name)
            if current is None:
                raise ComputeError(f"VM Linux introuvable : {name}")
            runtime = InstanceRuntime(
                status="running",
                ipv4=current.ipv4,
                message="VM Linux démarrée (sim)",
            )
            self._state[name] = runtime
            return runtime

    def delete(self, name: str) -> None:
        with self._lock:
            self._state.pop(name, None)


class _MultipassDriver:
    """Vraies VM Linux Ubuntu via Canonical Multipass."""

    def launch(self, payload: InstanceCreate) -> InstanceRuntime:
        if not shutil.which("multipass"):
            raise ComputeError(
                "multipass n’est pas installé — brew install --cask multipass "
                "(mot de passe admin requis)"
            )
        alias = multipass_alias(payload.image)
        mem = f"{payload.memory_mb}M"
        cmd = [
            "multipass",
            "launch",
            alias,
            "--name",
            payload.name,
            "--cpus",
            str(payload.vcpus),
            "--memory",
            mem,
        ]
        cloudinit = write_cloud_init_file(payload.ssh_authorized_key)
        if cloudinit is not None:
            cmd.extend(["--cloud-init", str(cloudinit)])
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=600)
        except subprocess.CalledProcessError as exc:
            err = (exc.stderr or exc.stdout or str(exc)).strip()
            raise ComputeError(f"multipass launch échoué : {err}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ComputeError("multipass launch timeout") from exc
        finally:
            if cloudinit is not None:
                cloudinit.unlink(missing_ok=True)
        runtime = self.status(payload.name)
        meta = resolve_linux_image(payload.image)
        return InstanceRuntime(
            status=runtime.status,
            ipv4=runtime.ipv4,
            message=f"VM Linux Multipass · {meta['name']} · {runtime.message}",
        )

    def status(self, name: str) -> InstanceRuntime:
        try:
            proc = subprocess.run(
                ["multipass", "info", name, "--format", "csv"],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.CalledProcessError as exc:
            err = (exc.stderr or "").strip()
            raise ComputeError(f"multipass info échoué : {err}") from exc
        lines = [line for line in proc.stdout.splitlines() if line.strip()]
        if len(lines) < 2:
            return InstanceRuntime(status="unknown", message="réponse multipass vide")
        # CSV header + row — colonnes variables selon version
        headers = [h.strip().lower() for h in lines[0].split(",")]
        values = lines[1].split(",")
        row = dict(zip(headers, values, strict=False))
        state = (row.get("state") or row.get("status") or "unknown").strip().lower()
        ipv4 = (row.get("ipv4") or row.get("ip") or "").strip()
        if state in {"running"}:
            status = "running"
        elif state in {"stopped", "suspended"}:
            status = "stopped"
        elif state in {"starting"}:
            status = "pending"
        else:
            status = state or "unknown"
        return InstanceRuntime(status=status, ipv4=ipv4, message=f"multipass · {state}")

    def stop(self, name: str) -> InstanceRuntime:
        self._run(["multipass", "stop", name])
        return self.status(name)

    def start(self, name: str) -> InstanceRuntime:
        self._run(["multipass", "start", name])
        return self.status(name)

    def delete(self, name: str) -> None:
        self._run(["multipass", "delete", name, "--purge"])

    @staticmethod
    def _run(cmd: list[str]) -> None:
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
        except subprocess.CalledProcessError as exc:
            err = (exc.stderr or exc.stdout or str(exc)).strip()
            raise ComputeError(f"{' '.join(cmd[:2])} échoué : {err}") from exc


_sim = _SimDriver()
_multipass = _MultipassDriver()


def _driver():
    name = compute_driver_name()
    if name == "off":
        raise ComputeError("compute désactivé (OPENYARD_COMPUTE=off)")
    if name == "multipass":
        return _multipass
    return _sim


def launch_instance(payload: InstanceCreate) -> InstanceRuntime:
    logger.info("launch instance %s via %s", payload.name, compute_driver_name())
    return _driver().launch(payload)


def read_instance(name: str) -> InstanceRuntime:
    return _driver().status(name)


def stop_instance(name: str) -> InstanceRuntime:
    return _driver().stop(name)


def start_instance(name: str) -> InstanceRuntime:
    return _driver().start(name)


def delete_instance(name: str) -> None:
    _driver().delete(name)


def apply_runtime(instance: Instance, runtime: InstanceRuntime) -> dict[str, str]:
    return {
        "status": runtime.status,
        "ipv4": runtime.ipv4,
        "message": runtime.message,
        "driver": compute_driver_name(),
    }
