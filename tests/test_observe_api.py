from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.cluster import ClusterUnavailable
from app.main import app
from app.models import Workload
from app.observe import WorkloadEvent


client = TestClient(app)


def _wl() -> Workload:
    return Workload(
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


def test_events_ok(monkeypatch) -> None:
    from app import main as main_mod

    monkeypatch.setattr(main_mod, "get_workload", lambda name, identity: _wl())
    monkeypatch.setattr(
        main_mod,
        "list_workload_events",
        lambda ns, name, limit=40: [
            WorkloadEvent("Normal", "Pulled", "ok", 1, "t", "Pod", "demo-x")
        ],
    )
    res = client.get("/workloads/demo/events")
    assert res.status_code == 200
    assert res.json()[0]["reason"] == "Pulled"


def test_logs_ok(monkeypatch) -> None:
    from app import main as main_mod

    monkeypatch.setattr(main_mod, "get_workload", lambda name, identity: _wl())
    monkeypatch.setattr(
        main_mod, "read_workload_logs", lambda ns, name, tail_lines=200: "# pod=x\nhello\n"
    )
    res = client.get("/workloads/demo/logs")
    assert res.status_code == 200
    assert "hello" in res.text


def test_events_unavailable(monkeypatch) -> None:
    from app import main as main_mod

    monkeypatch.setattr(main_mod, "get_workload", lambda name, identity: _wl())
    monkeypatch.setattr(
        main_mod,
        "list_workload_events",
        lambda *a, **k: (_ for _ in ()).throw(ClusterUnavailable("off")),
    )
    res = client.get("/workloads/demo/events")
    assert res.status_code == 503
