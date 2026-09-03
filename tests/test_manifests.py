from datetime import UTC, datetime

from app.manifests import render_bundle
from app.models import Workload


def test_render_bundle_contains_security_defaults() -> None:
    workload = Workload(
        name="secure-app",
        image="ghcr.io/example/app:1",
        replicas=2,
        port=8080,
        cpu="50m",
        memory="64Mi",
        namespace="openyard",
        created_at=datetime.now(UTC),
    )
    text = render_bundle(workload)
    assert "kind: Deployment" in text
    assert "kind: Service" in text
    assert "runAsNonRoot: true" in text
    assert "drop:" in text
    assert "ALL" in text
    assert "openyard.io/managed" in text
    assert "replicas: 2" in text
