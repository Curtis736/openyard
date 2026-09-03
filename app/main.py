from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.responses import PlainTextResponse

from app import __version__
from app.cluster import (
    ClusterError,
    ClusterUnavailable,
    apply_workload,
    cluster_enabled,
    delete_from_cluster,
    read_workload_status,
)
from app.manifests import render_bundle
from app.models import Workload, WorkloadCreate, WorkloadStats
from app.store import WorkloadStore

store = WorkloadStore(namespace=os.getenv("OPENYARD_NAMESPACE", "openyard"))

app = FastAPI(
    title="OpenYard",
    version=__version__,
    description=(
        "Mini-cloud open source : on enregistre une image Docker, l’API produit "
        "le Deployment Kubernetes et peut l’appliquer sur le cluster pour faire "
        "tourner des pods."
    ),
)


def _cluster_http(exc: Exception) -> HTTPException:
    if isinstance(exc, ClusterUnavailable):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@app.get("/health", tags=["ops"])
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "version": __version__,
        "cluster": cluster_enabled(),
    }


@app.get("/metrics", include_in_schema=False)
def metrics() -> PlainTextResponse:
    stats = store.stats(cluster_mode=cluster_enabled())
    body = "\n".join(
        [
            "# HELP openyard_up 1 if the control plane is up",
            "# TYPE openyard_up gauge",
            "openyard_up 1",
            "# HELP openyard_workloads Registered workloads",
            "# TYPE openyard_workloads gauge",
            f"openyard_workloads {stats.workloads}",
            "# HELP openyard_pods_desired Desired pod replicas across workloads",
            "# TYPE openyard_pods_desired gauge",
            f"openyard_pods_desired {stats.pods_desired}",
            "# HELP openyard_pods_ready Ready pod replicas reported by the API",
            "# TYPE openyard_pods_ready gauge",
            f"openyard_pods_ready {stats.pods_ready}",
            "",
        ]
    )
    return PlainTextResponse(body, media_type="text/plain; version=0.0.4; charset=utf-8")


@app.get("/stats", response_model=WorkloadStats, tags=["ops"])
def stats() -> WorkloadStats:
    return store.stats(cluster_mode=cluster_enabled())


@app.post(
    "/workloads",
    response_model=Workload,
    status_code=status.HTTP_201_CREATED,
    tags=["workloads"],
)
def create_workload(payload: WorkloadCreate) -> Workload:
    try:
        workload = store.create(payload)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workload déjà enregistré : {payload.name}",
        ) from exc

    if payload.apply:
        try:
            runtime = apply_workload(workload)
        except (ClusterUnavailable, ClusterError) as exc:
            store.delete(workload.name)
            raise _cluster_http(exc) from exc
        updated = store.set_runtime(
            workload.name,
            status="ready" if runtime.available else "deploying",
            ready_replicas=runtime.ready_replicas,
            message=runtime.message,
        )
        assert updated is not None
        return updated
    return workload


@app.get("/workloads", response_model=list[Workload], tags=["workloads"])
def list_workloads() -> list[Workload]:
    return store.list()


@app.get("/workloads/{name}", response_model=Workload, tags=["workloads"])
def get_workload(name: str) -> Workload:
    workload = store.get(name)
    if workload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload introuvable")
    return workload


@app.post("/workloads/{name}/apply", response_model=Workload, tags=["workloads"])
def apply_named_workload(name: str) -> Workload:
    workload = store.get(name)
    if workload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload introuvable")
    try:
        runtime = apply_workload(workload)
    except (ClusterUnavailable, ClusterError) as exc:
        raise _cluster_http(exc) from exc
    updated = store.set_runtime(
        name,
        status="ready" if runtime.available else "deploying",
        ready_replicas=runtime.ready_replicas,
        message=runtime.message,
    )
    assert updated is not None
    return updated


@app.get("/workloads/{name}/status", response_model=Workload, tags=["workloads"])
def workload_status(name: str) -> Workload:
    workload = store.get(name)
    if workload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload introuvable")
    try:
        runtime = read_workload_status(workload)
    except (ClusterUnavailable, ClusterError) as exc:
        raise _cluster_http(exc) from exc
    updated = store.set_runtime(
        name,
        status="ready" if runtime.available else "deploying",
        ready_replicas=runtime.ready_replicas,
        message=runtime.message,
    )
    assert updated is not None
    return updated


@app.delete("/workloads/{name}", status_code=status.HTTP_204_NO_CONTENT, tags=["workloads"])
def delete_workload(name: str) -> Response:
    workload = store.delete(name)
    if workload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload introuvable")
    if cluster_enabled() and workload.status in {"ready", "deploying"}:
        try:
            delete_from_cluster(workload)
        except ClusterUnavailable:
            pass
        except ClusterError as exc:
            raise _cluster_http(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/workloads/{name}/manifest", tags=["workloads"])
def workload_manifest(name: str) -> PlainTextResponse:
    workload = store.get(name)
    if workload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload introuvable")
    return PlainTextResponse(render_bundle(workload), media_type="application/yaml")
