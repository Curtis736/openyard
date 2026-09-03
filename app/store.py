from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock

from app.models import Instance, InstanceCreate, Workload, WorkloadCreate, WorkloadStats


class WorkloadStore:
    """Registre en mémoire des charges à matérialiser en pods."""

    def __init__(self, namespace: str = "openyard") -> None:
        self._namespace = namespace
        self._items: dict[str, Workload] = {}
        self._instances: dict[str, Instance] = {}
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

    def delete(self, name: str) -> Workload | None:
        with self._lock:
            return self._items.pop(name, None)

    def set_runtime(
        self,
        name: str,
        *,
        status: str,
        ready_replicas: int = 0,
        message: str = "",
    ) -> Workload | None:
        with self._lock:
            current = self._items.get(name)
            if current is None:
                return None
            updated = current.model_copy(
                update={
                    "status": status,
                    "ready_replicas": ready_replicas,
                    "message": message,
                }
            )
            self._items[name] = updated
            return updated

    def create_instance(self, payload: InstanceCreate, *, driver: str) -> Instance:
        with self._lock:
            if payload.name in self._instances:
                raise KeyError(payload.name)
            from app.linux_images import resolve_linux_image

            meta = resolve_linux_image(payload.image)
            instance = Instance(
                name=payload.name,
                image=meta["id"],
                os="linux",
                distro=meta["distro"],
                vcpus=payload.vcpus,
                memory_mb=payload.memory_mb,
                created_at=datetime.now(UTC),
                status="pending",
                driver=driver,
                message=f"VM Linux {meta['name']}",
            )
            self._instances[payload.name] = instance
            return instance

    def list_instances(self) -> list[Instance]:
        with self._lock:
            return sorted(self._instances.values(), key=lambda item: item.name)

    def get_instance(self, name: str) -> Instance | None:
        with self._lock:
            return self._instances.get(name)

    def delete_instance(self, name: str) -> Instance | None:
        with self._lock:
            return self._instances.pop(name, None)

    def set_instance(
        self,
        name: str,
        *,
        status: str,
        ipv4: str = "",
        message: str = "",
        driver: str | None = None,
    ) -> Instance | None:
        with self._lock:
            current = self._instances.get(name)
            if current is None:
                return None
            update: dict[str, str] = {
                "status": status,
                "ipv4": ipv4,
                "message": message,
            }
            if driver is not None:
                update["driver"] = driver
            updated = current.model_copy(update=update)
            self._instances[name] = updated
            return updated

    def stats(self, *, cluster_mode: bool = False, compute_driver: str = "sim") -> WorkloadStats:
        with self._lock:
            return WorkloadStats(
                workloads=len(self._items),
                pods_desired=sum(item.replicas for item in self._items.values()),
                pods_ready=sum(item.ready_replicas for item in self._items.values()),
                cluster_mode=cluster_mode,
                instances=len(self._instances),
                instances_running=sum(
                    1 for item in self._instances.values() if item.status == "running"
                ),
                compute_driver=compute_driver,
            )
