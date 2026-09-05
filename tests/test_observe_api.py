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
