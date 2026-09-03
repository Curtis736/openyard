from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


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
    assert 'runAsNonRoot: true' in text or "runAsNonRoot: true" in text

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
