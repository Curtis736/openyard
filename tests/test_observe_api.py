from __future__ import annotations

from app.observe import WorkloadEvent


def test_workload_event_dataclass() -> None:
    ev = WorkloadEvent(
        type="Normal",
        reason="Created",
        message="Created pod",
        count=1,
        last_timestamp="2026-01-01T00:00:00Z",
        involved_kind="Pod",
        involved_name="demo-web-abc",
    )
    assert ev.reason == "Created"


from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.cluster import ClusterUnavailable
from app.main import app
from tests.test_app import client  # noqa: F401 — shared client pattern


def test_events_cluster_off(monkeypatch) -> None:
    from app import main as main_mod
    from app.models import Workload
    from datetime import datetime, timezone

    wl = Workload(
        name="demo",
        project="default",
        image="nginxinc/nginx-unprivileged:1.27-alpine",
        replicas=1,
        port=8080,
        cpu="50m",
        memory="64Mi",
        namespace="openyard",
        created_at=datetime.now(timezone.utc),
    )
    monkeypatch.setattr(main_mod.store, "get", lambda name, project=None: wl if name == "demo" else None)
    monkeypatch.setattr(main_mod, "list_workload_events", lambda *a, **k: (_ for _ in ()).throw(ClusterUnavailable("off")))
    local = TestClient(app)
    # ensure workload exists via store create path — use monkeypatch get_workload path
    monkeypatch.setattr(main_mod, "get_workload", lambda name, identity: wl)
    res = local.get("/workloads/demo/events")
    assert res.status_code == 503
