from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.cluster import ClusterUnavailable, WorkloadRuntime
from app.main import app, store

client = TestClient(app)


def setup_function() -> None:
    for item in list(store.list()):
        store.delete(item.name)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "cluster" in body


def test_create_list_manifest_and_delete() -> None:
    created = client.post(
        "/workloads",
        json={
            "name": "edge-api",
            "image": "ghcr.io/curtis736/openyard:latest",
            "replicas": 2,
            "port": 8000,
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "edge-api"
    assert body["replicas"] == 2
    assert body["status"] == "registered"

    listed = client.get("/workloads")
    assert listed.status_code == 200
    assert any(item["name"] == "edge-api" for item in listed.json())

    stats = client.get("/stats")
    assert stats.status_code == 200
    assert stats.json()["workloads"] >= 1
    assert stats.json()["pods_desired"] >= 2

    manifest = client.get("/workloads/edge-api/manifest")
    assert manifest.status_code == 200
    text = manifest.text
    assert "kind: Deployment" in text
    assert "kind: Service" in text
    assert "image: ghcr.io/curtis736/openyard:latest" in text
    assert "replicas: 2" in text
    assert "runAsNonRoot: true" in text

    conflict = client.post(
        "/workloads",
        json={"name": "edge-api", "image": "nginx:1.27-alpine", "replicas": 1},
    )
    assert conflict.status_code == 409

    deleted = client.delete("/workloads/edge-api")
    assert deleted.status_code == 204
    missing = client.get("/workloads/edge-api")
    assert missing.status_code == 404


def test_rejects_invalid_name() -> None:
    response = client.post(
        "/workloads",
        json={"name": "Bad_Name", "image": "nginx:1.27-alpine"},
    )
    assert response.status_code == 422


def test_metrics() -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "openyard_up 1" in response.text
    assert "openyard_pods_ready" in response.text


def test_apply_updates_status() -> None:
    created = client.post(
        "/workloads",
        json={
            "name": "demo-job",
            "image": "nginxinc/nginx-unprivileged:1.27-alpine",
            "replicas": 1,
            "port": 8080,
        },
    )
    assert created.status_code == 201

    runtime = WorkloadRuntime(
        ready_replicas=1,
        desired_replicas=1,
        available=True,
        message="MinimumReplicasAvailable",
    )
    with patch("app.main.apply_workload", return_value=runtime) as mocked:
        applied = client.post("/workloads/demo-job/apply")
    assert applied.status_code == 200
    body = applied.json()
    assert body["status"] == "ready"
    assert body["ready_replicas"] == 1
    mocked.assert_called_once()


def test_apply_without_cluster_returns_503() -> None:
    client.post(
        "/workloads",
        json={
            "name": "orphan",
            "image": "nginxinc/nginx-unprivileged:1.27-alpine",
            "port": 8080,
        },
    )
    with patch(
        "app.main.apply_workload",
        side_effect=ClusterUnavailable("aucun kubeconfig disponible"),
    ):
        response = client.post("/workloads/orphan/apply")
    assert response.status_code == 503


def test_create_with_apply_flag() -> None:
    runtime = WorkloadRuntime(
        ready_replicas=0,
        desired_replicas=1,
        available=False,
        message="waiting for pods",
    )
    with patch("app.main.apply_workload", return_value=runtime):
        response = client.post(
            "/workloads",
            json={
                "name": "auto-apply",
                "image": "hashicorp/http-echo:1.0",
                "port": 5678,
                "apply": True,
            },
        )
    assert response.status_code == 201
    assert response.json()["status"] == "deploying"
