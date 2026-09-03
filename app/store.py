from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from app.linux_images import resolve_linux_image
from app.models import Instance, InstanceCreate, Workload, WorkloadCreate, WorkloadStats


def default_db_path() -> Path:
    return Path(os.getenv("OPENYARD_DB", "data/openyard.db"))


class WorkloadStore:
    """Registre persistant (SQLite) des workloads et VM Linux."""

    def __init__(self, namespace: str = "openyard", db_path: str | Path | None = None) -> None:
        self._namespace = namespace
        self._db_path = Path(db_path) if db_path is not None else default_db_path()
        self._lock = Lock()
        if str(self._db_path) != ":memory:":
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workloads (
                    name TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS instances (
                    name TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                )
                """
            )

    def create(self, payload: WorkloadCreate) -> Workload:
        with self._lock:
            if self._get_workload(payload.name) is not None:
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
            self._put_workload(workload)
            return workload

    def list(self) -> list[Workload]:
        with self._lock:
            rows = self._conn.execute("SELECT payload FROM workloads").fetchall()
            items = [Workload.model_validate_json(row["payload"]) for row in rows]
            return sorted(items, key=lambda item: item.name)

    def get(self, name: str) -> Workload | None:
        with self._lock:
            return self._get_workload(name)

    def delete(self, name: str) -> Workload | None:
        with self._lock:
            current = self._get_workload(name)
            if current is None:
                return None
            self._conn.execute("DELETE FROM workloads WHERE name = ?", (name,))
            self._conn.commit()
            return current

    def set_runtime(
        self,
        name: str,
        *,
        status: str,
        ready_replicas: int = 0,
        message: str = "",
        url: str | None = None,
    ) -> Workload | None:
        with self._lock:
            current = self._get_workload(name)
            if current is None:
                return None
            update: dict[str, object] = {
                "status": status,
                "ready_replicas": ready_replicas,
                "message": message,
            }
            if url is not None:
                update["url"] = url
            updated = current.model_copy(update=update)
            self._put_workload(updated)
            return updated

    def create_instance(self, payload: InstanceCreate, *, driver: str) -> Instance:
        with self._lock:
            if self._get_instance(payload.name) is not None:
                raise KeyError(payload.name)
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
            self._put_instance(instance)
            return instance

    def list_instances(self) -> list[Instance]:
        with self._lock:
            rows = self._conn.execute("SELECT payload FROM instances").fetchall()
            items = [Instance.model_validate_json(row["payload"]) for row in rows]
            return sorted(items, key=lambda item: item.name)

    def get_instance(self, name: str) -> Instance | None:
        with self._lock:
            return self._get_instance(name)

    def delete_instance(self, name: str) -> Instance | None:
        with self._lock:
            current = self._get_instance(name)
            if current is None:
                return None
            self._conn.execute("DELETE FROM instances WHERE name = ?", (name,))
            self._conn.commit()
            return current

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
            current = self._get_instance(name)
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
            self._put_instance(updated)
            return updated

    def stats(self, *, cluster_mode: bool = False, compute_driver: str = "sim") -> WorkloadStats:
        with self._lock:
            workloads = [
                Workload.model_validate_json(row["payload"])
                for row in self._conn.execute("SELECT payload FROM workloads").fetchall()
            ]
            instances = [
                Instance.model_validate_json(row["payload"])
                for row in self._conn.execute("SELECT payload FROM instances").fetchall()
            ]
            return WorkloadStats(
                workloads=len(workloads),
                pods_desired=sum(item.replicas for item in workloads),
                pods_ready=sum(item.ready_replicas for item in workloads),
                cluster_mode=cluster_mode,
                instances=len(instances),
                instances_running=sum(1 for item in instances if item.status == "running"),
                compute_driver=compute_driver,
            )

    def _get_workload(self, name: str) -> Workload | None:
        row = self._conn.execute(
            "SELECT payload FROM workloads WHERE name = ?", (name,)
        ).fetchone()
        return Workload.model_validate_json(row["payload"]) if row else None

    def _put_workload(self, workload: Workload) -> None:
        self._conn.execute(
            """
            INSERT INTO workloads(name, payload) VALUES(?, ?)
            ON CONFLICT(name) DO UPDATE SET payload = excluded.payload
            """,
            (workload.name, workload.model_dump_json()),
        )
        self._conn.commit()

    def _get_instance(self, name: str) -> Instance | None:
        row = self._conn.execute(
            "SELECT payload FROM instances WHERE name = ?", (name,)
        ).fetchone()
        return Instance.model_validate_json(row["payload"]) if row else None

    def _put_instance(self, instance: Instance) -> None:
        self._conn.execute(
            """
            INSERT INTO instances(name, payload) VALUES(?, ?)
            ON CONFLICT(name) DO UPDATE SET payload = excluded.payload
            """,
            (instance.name, instance.model_dump_json()),
        )
        self._conn.commit()
