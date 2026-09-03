from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.cluster import (
    ClusterError,
    ClusterUnavailable,
    apply_workload,
    cluster_enabled,
    delete_from_cluster,
    read_workload_status,
)
from app.compute import (
    ComputeError,
    compute_driver_name,
    compute_enabled,
    delete_instance,
    launch_instance,
    read_instance,
    start_instance,
    stop_instance,
)
from app.manifests import render_bundle
from app.models import (
    Instance,
    InstanceCreate,
    LinuxImageInfo,
    Workload,
    WorkloadCreate,
    WorkloadStats,
    catalog_payload,
)
from app.store import WorkloadStore

store = WorkloadStore(namespace=os.getenv("OPENYARD_NAMESPACE", "openyard"))
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(
    title="OpenYard",
    version=__version__,
    description=(
        "Open cloud open source : site + console + API. Workloads Docker → pods "
        "Kubernetes, et VM Linux Ubuntu (sim ou Multipass)."
    ),
)

if WEB_DIR.is_dir():
    assets = WEB_DIR / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")


def _cluster_http(exc: Exception) -> HTTPException:
    if isinstance(exc, ClusterUnavailable):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


def _compute_http(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


def _stats() -> WorkloadStats:
    return store.stats(cluster_mode=cluster_enabled(), compute_driver=compute_driver_name())


@app.get("/", include_in_schema=False)
def landing() -> FileResponse:
    index = WEB_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UI absente")
    return FileResponse(index)


@app.get("/console", include_in_schema=False)
def console() -> FileResponse:
    page = WEB_DIR / "console.html"
    if not page.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UI absente")
    return FileResponse(page)


@app.get("/health", tags=["ops"])
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "version": __version__,
        "cluster": cluster_enabled(),
        "compute": compute_driver_name(),
    }


@app.get("/metrics", include_in_schema=False)
def metrics() -> PlainTextResponse:
    stats = _stats()
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
            "# HELP openyard_instances Registered compute instances",
            "# TYPE openyard_instances gauge",
            f"openyard_instances {stats.instances}",
            "# HELP openyard_instances_running Running compute instances",
            "# TYPE openyard_instances_running gauge",
            f"openyard_instances_running {stats.instances_running}",
            "",
        ]
    )
    return PlainTextResponse(body, media_type="text/plain; version=0.0.4; charset=utf-8")


@app.get("/stats", response_model=WorkloadStats, tags=["ops"])
def stats() -> WorkloadStats:
    return _stats()


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


@app.get("/compute/images", response_model=list[LinuxImageInfo], tags=["compute"])
def linux_images_catalog() -> list[LinuxImageInfo]:
    return catalog_payload()


@app.post(
    "/instances",
    response_model=Instance,
    status_code=status.HTTP_201_CREATED,
    tags=["compute"],
)
def create_instance(payload: InstanceCreate) -> Instance:
    if not compute_enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="compute off")
    driver = compute_driver_name()
    try:
        instance = store.create_instance(payload, driver=driver)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Instance déjà enregistrée : {payload.name}",
        ) from exc

    if not payload.launch:
        return instance

    try:
        runtime = launch_instance(payload)
    except ComputeError as exc:
        store.delete_instance(payload.name)
        raise _compute_http(exc) from exc

    updated = store.set_instance(
        payload.name,
        status=runtime.status,
        ipv4=runtime.ipv4,
        message=runtime.message,
        driver=driver,
    )
    assert updated is not None
    return updated


@app.get("/instances", response_model=list[Instance], tags=["compute"])
def list_instances() -> list[Instance]:
    return store.list_instances()


@app.get("/instances/{name}", response_model=Instance, tags=["compute"])
def get_instance(name: str) -> Instance:
    instance = store.get_instance(name)
    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instance introuvable")
    return instance


@app.get("/instances/{name}/status", response_model=Instance, tags=["compute"])
def instance_status(name: str) -> Instance:
    instance = store.get_instance(name)
    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instance introuvable")
    try:
        runtime = read_instance(name)
    except ComputeError as exc:
        raise _compute_http(exc) from exc
    updated = store.set_instance(
        name,
        status=runtime.status,
        ipv4=runtime.ipv4,
        message=runtime.message,
        driver=compute_driver_name(),
    )
    assert updated is not None
    return updated


@app.post("/instances/{name}/stop", response_model=Instance, tags=["compute"])
def instance_stop(name: str) -> Instance:
    instance = store.get_instance(name)
    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instance introuvable")
    try:
        runtime = stop_instance(name)
    except ComputeError as exc:
        raise _compute_http(exc) from exc
    updated = store.set_instance(
        name,
        status=runtime.status,
        ipv4=runtime.ipv4,
        message=runtime.message,
    )
    assert updated is not None
    return updated


@app.post("/instances/{name}/start", response_model=Instance, tags=["compute"])
def instance_start(name: str) -> Instance:
    instance = store.get_instance(name)
    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instance introuvable")
    try:
        runtime = start_instance(name)
    except ComputeError as exc:
        raise _compute_http(exc) from exc
    updated = store.set_instance(
        name,
        status=runtime.status,
        ipv4=runtime.ipv4,
        message=runtime.message,
    )
    assert updated is not None
    return updated


@app.delete("/instances/{name}", status_code=status.HTTP_204_NO_CONTENT, tags=["compute"])
def remove_instance(name: str) -> Response:
    instance = store.get_instance(name)
    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instance introuvable")
    try:
        delete_instance(name)
    except ComputeError as exc:
        raise _compute_http(exc) from exc
    store.delete_instance(name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
