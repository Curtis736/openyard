from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock

from app.models import Workload, WorkloadCreate, WorkloadStats


class WorkloadStore:
    """Registre en mémoire des charges à matérialiser en pods."""

    def __init__(self, namespace: str = "openyard") -> None:
        self._namespace = namespace
        self._items: dict[str, Workload] = {}
        self._lock = Lock()

    def create(self, payload: WorkloadCreate) -> Workload:
        with self._lock:
            if payload.name in self._items:
                raise KeyError(payload.name)
            workload = Workload(
                name=payload.name,
                image=payload.image,
                replicas=payload.replicas,
                port=payload.port,
                cpu=payload.cpu,
                memory=payload.memory,
                namespace=self._namespace,
                created_at=datetime.now(UTC),
                status="registered",
            )
            self._items[payload.name] = workload
            return workload

    def list(self) -> list[Workload]:
        with self._lock:
            return sorted(self._items.values(), key=lambda item: item.name)

    def get(self, name: str) -> Workload | None:
        with self._lock:
            return self._items.get(name)

    def delete(self, name: str) -> bool:
        with self._lock:
            return self._items.pop(name, None) is not None

    def stats(self) -> WorkloadStats:
        with self._lock:
            return WorkloadStats(
                workloads=len(self._items),
                pods_desired=sum(item.replicas for item in self._items.values()),
            )
