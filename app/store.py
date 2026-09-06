from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from app.auth import generate_api_key, keys_equal
from app.linux_images import resolve_linux_image
from app.models import (
    Instance,
    InstanceCreate,
    Project,
    ProjectCreate,
    Workload,
    WorkloadCreate,
    WorkloadStats,
)
from app.tenancy import project_namespace


def default_db_path() -> Path:
    return Path(os.getenv("OPENYARD_DB", "data/openyard.db"))


class QuotaExceeded(RuntimeError):
    """Quota projet dépassé."""


class WorkloadStore:
    """Registre persistant multi-tenant (projets, workloads, VM)."""

    def __init__(self, namespace: str = "openyard", db_path: str | Path | None = None) -> None:
        self._default_namespace = namespace
        self._db_path = Path(db_path) if db_path is not None else default_db_path()
        self._lock = Lock()
        if str(self._db_path) != ":memory:":
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        self.ensure_default_project()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    name TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workloads (
                    project TEXT NOT NULL,
                    name TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (project, name)
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS instances (
                    project TEXT NOT NULL,
                    name TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (project, name)
                )
                """
            )
            # Migration ancienne table workloads(name, payload)
            cols = {
                row["name"]
                for row in self._conn.execute("PRAGMA table_info(workloads)").fetchall()
            }
            if cols == {"name", "payload"}:
                rows = self._conn.execute("SELECT name, payload FROM workloads").fetchall()
                self._conn.execute("ALTER TABLE workloads RENAME TO workloads_legacy")
                self._conn.execute(
                    """
                    CREATE TABLE workloads (
                        project TEXT NOT NULL,
                        name TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        PRIMARY KEY (project, name)
                    )
                    """
                )
                for row in rows:
                    wl = Workload.model_validate_json(row["payload"])
                    updated = wl.model_copy(
                        update={"project": "default", "namespace": self._default_namespace}
                    )
                    self._conn.execute(
                        "INSERT INTO workloads(project, name, payload) VALUES(?,?,?)",
                        ("default", updated.name, updated.model_dump_json()),
                    )
                self._conn.execute("DROP TABLE workloads_legacy")

    def ensure_default_project(self) -> Project:
        with self._lock:
            existing = self._get_project("default")
            if existing is not None:
                return existing
            project = Project(
                name="default",
                namespace=self._default_namespace,
                api_key="",
                pods_quota=20,
                instances_quota=10,
                cpu_quota="2",
                memory_quota="2Gi",
                created_at=datetime.now(UTC),
                message="projet bootstrap (clé vide = accès anonyme si pas d’admin key)",
            )
            self._put_project(project)
            return project

    def create_project(self, payload: ProjectCreate) -> Project:
        with self._lock:
            if payload.name == "default":
                raise ValueError("le projet default est réservé")
            if self._get_project(payload.name) is not None:
                raise KeyError(payload.name)
            project = Project(
                name=payload.name,
                namespace=project_namespace(payload.name),
                api_key=generate_api_key(),
                pods_quota=payload.pods_quota,
                instances_quota=payload.instances_quota,
                cpu_quota=payload.cpu_quota,
                memory_quota=payload.memory_quota,
                created_at=datetime.now(UTC),
                message="projet créé",
            )
            self._put_project(project)
            return project

    def list_projects(self) -> list[Project]:
        with self._lock:
            rows = self._conn.execute("SELECT payload FROM projects").fetchall()
            items = [Project.model_validate_json(row["payload"]) for row in rows]
            return sorted(items, key=lambda item: item.name)

    def get_project(self, name: str) -> Project | None:
        with self._lock:
            return self._get_project(name)

    def find_project_by_key(self, api_key: str) -> Project | None:
        with self._lock:
            for project in (
                Project.model_validate_json(row["payload"])
                for row in self._conn.execute("SELECT payload FROM projects").fetchall()
            ):
                if project.api_key and keys_equal(api_key, project.api_key):
                    return project
            return None

    def delete_project(self, name: str) -> Project | None:
        with self._lock:
            if name == "default":
                raise ValueError("impossible de supprimer default")
            current = self._get_project(name)
            if current is None:
                return None
            self._conn.execute("DELETE FROM workloads WHERE project = ?", (name,))
            self._conn.execute("DELETE FROM instances WHERE project = ?", (name,))
            self._conn.execute("DELETE FROM projects WHERE name = ?", (name,))
            self._conn.commit()
            return current

    def update_project(self, project: Project) -> Project:
        with self._lock:
            self._put_project(project)
            return project

    def pods_used(self, project: str) -> int:
        with self._lock:
            return sum(
                Workload.model_validate_json(row["payload"]).replicas
                for row in self._conn.execute(
                    "SELECT payload FROM workloads WHERE project = ?", (project,)
                ).fetchall()
            )

    def instances_used(self, project: str) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS c FROM instances WHERE project = ?", (project,)
            ).fetchone()
            return int(row["c"] if row else 0)

    def create(self, payload: WorkloadCreate, *, project: Project) -> Workload:
        with self._lock:
            if self._get_workload(project.name, payload.name) is not None:
                raise KeyError(payload.name)
            used = sum(
                Workload.model_validate_json(row["payload"]).replicas
                for row in self._conn.execute(
                    "SELECT payload FROM workloads WHERE project = ?", (project.name,)
                ).fetchall()
            )
            if used + payload.replicas > project.pods_quota:
                raise QuotaExceeded(
                    f"quota pods dépassé ({used}+{payload.replicas}/{project.pods_quota})"
                )
            workload = Workload(
                name=payload.name,
                project=project.name,
                image=payload.image,
                replicas=payload.replicas,
                port=payload.port,
                cpu=payload.cpu,
                memory=payload.memory,
                namespace=project.namespace,
                created_at=datetime.now(UTC),
                status="registered",
            )
            self._put_workload(workload)
            return workload

    def list(self, *, project: str | None = None) -> list[Workload]:
        with self._lock:
            if project is None:
                rows = self._conn.execute("SELECT payload FROM workloads").fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT payload FROM workloads WHERE project = ?", (project,)
                ).fetchall()
            items = [Workload.model_validate_json(row["payload"]) for row in rows]
            return sorted(items, key=lambda item: (item.project, item.name))

    def get(self, name: str, *, project: str) -> Workload | None:
        with self._lock:
            return self._get_workload(project, name)

    def delete(self, name: str, *, project: str) -> Workload | None:
        with self._lock:
            current = self._get_workload(project, name)
            if current is None:
                return None
            self._conn.execute(
                "DELETE FROM workloads WHERE project = ? AND name = ?", (project, name)
            )
            self._conn.commit()
            return current

    def set_runtime(
        self,
        name: str,
        *,
        project: str,
        status: str,
        ready_replicas: int = 0,
        message: str = "",
        url: str | None = None,
    ) -> Workload | None:
        with self._lock:
            current = self._get_workload(project, name)
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

    def create_instance(
        self, payload: InstanceCreate, *, project: Project, driver: str
    ) -> Instance:
        with self._lock:
            if self._get_instance(project.name, payload.name) is not None:
                raise KeyError(payload.name)
            meta = resolve_linux_image(payload.image)
            instance = Instance(
                name=payload.name,
                project=project.name,
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

    def list_instances(self, *, project: str | None = None) -> list[Instance]:
        with self._lock:
            if project is None:
                rows = self._conn.execute("SELECT payload FROM instances").fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT payload FROM instances WHERE project = ?", (project,)
                ).fetchall()
            items = [Instance.model_validate_json(row["payload"]) for row in rows]
            return sorted(items, key=lambda item: (item.project, item.name))

    def get_instance(self, name: str, *, project: str) -> Instance | None:
        with self._lock:
            return self._get_instance(project, name)

    def delete_instance(self, name: str, *, project: str) -> Instance | None:
        with self._lock:
            current = self._get_instance(project, name)
            if current is None:
                return None
            self._conn.execute(
                "DELETE FROM instances WHERE project = ? AND name = ?", (project, name)
            )
            self._conn.commit()
            return current

    def set_instance(
        self,
        name: str,
        *,
        project: str,
        status: str,
        ipv4: str = "",
        message: str = "",
        driver: str | None = None,
    ) -> Instance | None:
        with self._lock:
            current = self._get_instance(project, name)
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

    def stats(
        self,
        *,
        cluster_mode: bool = False,
        compute_driver: str = "sim",
        project: str | None = None,
    ) -> WorkloadStats:
        with self._lock:
            if project is None:
                workloads = [
                    Workload.model_validate_json(row["payload"])
                    for row in self._conn.execute("SELECT payload FROM workloads").fetchall()
                ]
                instances = [
                    Instance.model_validate_json(row["payload"])
                    for row in self._conn.execute("SELECT payload FROM instances").fetchall()
                ]
            else:
                workloads = [
                    Workload.model_validate_json(row["payload"])
                    for row in self._conn.execute(
                        "SELECT payload FROM workloads WHERE project = ?", (project,)
                    ).fetchall()
                ]
                instances = [
                    Instance.model_validate_json(row["payload"])
                    for row in self._conn.execute(
                        "SELECT payload FROM instances WHERE project = ?", (project,)
                    ).fetchall()
                ]
            projects = self._conn.execute("SELECT COUNT(*) AS c FROM projects").fetchone()["c"]
            return WorkloadStats(
                workloads=len(workloads),
                pods_desired=sum(item.replicas for item in workloads),
                pods_ready=sum(item.ready_replicas for item in workloads),
                cluster_mode=cluster_mode,
                instances=len(instances),
                instances_running=sum(1 for item in instances if item.status == "running"),
                compute_driver=compute_driver,
                projects=projects,
                project=project,
            )

    def _get_project(self, name: str) -> Project | None:
        row = self._conn.execute(
            "SELECT payload FROM projects WHERE name = ?", (name,)
        ).fetchone()
        return Project.model_validate_json(row["payload"]) if row else None

    def _put_project(self, project: Project) -> None:
        self._conn.execute(
            """
            INSERT INTO projects(name, payload) VALUES(?, ?)
            ON CONFLICT(name) DO UPDATE SET payload = excluded.payload
            """,
            (project.name, project.model_dump_json()),
        )
        self._conn.commit()

    def _get_workload(self, project: str, name: str) -> Workload | None:
        row = self._conn.execute(
            "SELECT payload FROM workloads WHERE project = ? AND name = ?",
            (project, name),
        ).fetchone()
        return Workload.model_validate_json(row["payload"]) if row else None

    def _put_workload(self, workload: Workload) -> None:
        self._conn.execute(
            """
            INSERT INTO workloads(project, name, payload) VALUES(?, ?, ?)
            ON CONFLICT(project, name) DO UPDATE SET payload = excluded.payload
            """,
            (workload.project, workload.name, workload.model_dump_json()),
        )
        self._conn.commit()

    def _get_instance(self, project: str, name: str) -> Instance | None:
        row = self._conn.execute(
            "SELECT payload FROM instances WHERE project = ? AND name = ?",
            (project, name),
        ).fetchone()
        return Instance.model_validate_json(row["payload"]) if row else None

    def _put_instance(self, instance: Instance) -> None:
        self._conn.execute(
            """
            INSERT INTO instances(project, name, payload) VALUES(?, ?, ?)
            ON CONFLICT(project, name) DO UPDATE SET payload = excluded.payload
            """,
            (instance.project, instance.name, instance.model_dump_json()),
        )
        self._conn.commit()
