from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_instances_quota_enforced() -> None:
    created = client.post(
        "/projects",
        json={
            "name": "quotaia",
            "pods_quota": 5,
            "instances_quota": 1,
            "cpu_quota": "1",
            "memory_quota": "1Gi",
        },
    )
    assert created.status_code == 201
    key = created.json()["api_key"]
    headers = {"X-API-Key": key}
    ok = client.post(
        "/instances",
        headers=headers,
        json={"name": "vm1", "image": "ubuntu-22.04", "launch": True},
    )
    assert ok.status_code == 201
    denied = client.post(
        "/instances",
        headers=headers,
        json={"name": "vm2", "image": "ubuntu-22.04", "launch": True},
    )
    assert denied.status_code == 409
    assert "quota instances" in denied.json()["detail"]
