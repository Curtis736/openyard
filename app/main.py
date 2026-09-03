from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.auth import (
    Identity,
    api_key_configured,
    is_open_signup_path,
    is_public_path,
    resolve_identity,
)
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
    Project,
    ProjectCreate,
    ProjectPublic,
    Workload,
    WorkloadCreate,
    WorkloadStats,
    catalog_payload,
)
from app.store import QuotaExceeded, WorkloadStore
from app.tenancy import delete_project_namespace, ensure_project_namespace

store = WorkloadStore(namespace=os.getenv("OPENYARD_NAMESPACE", "openyard"))
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(
    title="OpenYard",
    version=__version__,
    description=(
        "Open cloud multi-tenant : projets (namespace + quotas + API key), "
        "workloads Kubernetes, VM Linux, console web."
    ),
)

if WEB_DIR.is_dir():
    assets = WEB_DIR / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")


def _identity_from_request(request: Request) -> Identity | None:
    return resolve_identity(
        request.headers.get("x-api-key"),
        find_by_key=store.find_project_by_key,
        default_project=store.ensure_default_project(),
    )


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if is_public_path(path) or is_open_signup_path(request.method, path):
        return await call_next(request)

    # GET /projects : listage public (sans secrets)
    if request.method.upper() == "GET" and path == "/projects":
        return await call_next(request)

    identity = _identity_from_request(request)
    if identity is None:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "API key invalide ou manquante (header X-API-Key)"},
            headers={"WWW-Authenticate": "ApiKey"},
        )
    request.state.identity = identity
    return await call_next(request)


def current_identity(request: Request) -> Identity:
    identity = getattr(request.state, "identity", None)
    if identity is None:
        # chemins publics / signup : identité soft default
        resolved = _identity_from_request(request)
        if resolved is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key invalide ou manquante (header X-API-Key)",
            )
        return resolved
    return identity


IdentityDep = Annotated[Identity, Depends(current_identity)]

def _cluster_http(exc: Exception) -> HTTPException:
    if isinstance(exc, ClusterUnavailable):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


def _compute_http(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


def _scope_project(identity: Identity) -> str | None:
    """None = vue admin globale."""
    if identity.kind == "admin":
        return None
    return identity.project_name


def _require_project(identity: Identity) -> Project:
    project = identity.project
    if project is None:
        project = store.ensure_default_project()
    return project


def _to_public(project: Project) -> ProjectPublic:
    return ProjectPublic(
        name=project.name,
        namespace=project.namespace,
        pods_quota=project.pods_quota,
        cpu_quota=project.cpu_quota,
        memory_quota=project.memory_quota,
        created_at=project.created_at,
        message=project.message,
        api_key_set=bool(project.api_key),
        pods_used=store.pods_used(project.name),
    )


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
        "auth_required": api_key_configured(),
        "projects": len(store.list_projects()),
    }


@app.get("/metrics", include_in_schema=False)
def metrics() -> PlainTextResponse:
    stats = store.stats(cluster_mode=cluster_enabled(), compute_driver=compute_driver_name())
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
            "# HELP openyard_projects Tenant projects",
            "# TYPE openyard_projects gauge",
            f"openyard_projects {stats.projects}",
            "",
        ]
    )
    return PlainTextResponse(body, media_type="text/plain; version=0.0.4; charset=utf-8")


@app.get("/stats", response_model=WorkloadStats, tags=["ops"])
def stats(identity: IdentityDep) -> WorkloadStats:
    return store.stats(
        cluster_mode=cluster_enabled(),
        compute_driver=compute_driver_name(),
        project=_scope_project(identity),
    )


@app.post(
    "/projects",
    response_model=Project,
    status_code=status.HTTP_201_CREATED,
    tags=["projects"],
)
def create_project(payload: ProjectCreate) -> Project:
    try:
        project = store.create_project(payload)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Projet déjà existant : {payload.name}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if cluster_enabled():
        try:
            msg = ensure_project_namespace(project)
            project = project.model_copy(update={"message": msg})
            store.update_project(project)
        except (ClusterUnavailable, ClusterError) as exc:
            store.delete_project(project.name)
            raise _cluster_http(exc) from exc
    return project


@app.get("/projects", response_model=list[ProjectPublic], tags=["projects"])
def list_projects() -> list[ProjectPublic]:
    return [_to_public(item) for item in store.list_projects()]


@app.get("/projects/{name}", response_model=Project, tags=["projects"])
def get_project(name: str, identity: IdentityDep) -> Project:
    project = store.get_project(name)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projet introuvable")
    if identity.kind == "project" and identity.project_name != name:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")
    if identity.kind == "anonymous" and name != "default":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")
    return project


@app.delete("/projects/{name}", status_code=status.HTTP_204_NO_CONTENT, tags=["projects"])
def remove_project(name: str, identity: IdentityDep) -> Response:
    if identity.kind not in {"admin", "anonymous"} and identity.project_name != name:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")
    if identity.kind == "project" and identity.project_name == name:
        pass  # owner can delete
    elif identity.kind == "anonymous" and name != "default":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clé admin ou clé projet requise",
        )
    try:
        project = store.delete_project(name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projet introuvable")
    try:
        delete_project_namespace(project)
    except ClusterError as exc:
        raise _cluster_http(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post(
    "/workloads",
    response_model=Workload,
    status_code=status.HTTP_201_CREATED,
    tags=["workloads"],
)
def create_workload(
    payload: WorkloadCreate,
    identity: IdentityDep,
) -> Workload:
    project = _require_project(identity)
    try:
        workload = store.create(payload, project=project)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workload déjà enregistré : {payload.name}",
        ) from exc
    except QuotaExceeded as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if payload.apply:
        try:
            runtime = apply_workload(workload)
        except (ClusterUnavailable, ClusterError) as exc:
            store.delete(workload.name, project=project.name)
            raise _cluster_http(exc) from exc
        updated = store.set_runtime(
            workload.name,
            project=project.name,
            status="ready" if runtime.available else "deploying",
            ready_replicas=runtime.ready_replicas,
            message=runtime.message,
            url=runtime.url,
        )
        assert updated is not None
        return updated
    return workload


@app.get("/workloads", response_model=list[Workload], tags=["workloads"])
def list_workloads(identity: IdentityDep) -> list[Workload]:
    return store.list(project=_scope_project(identity))


@app.get("/workloads/{name}", response_model=Workload, tags=["workloads"])
def get_workload(name: str, identity: IdentityDep) -> Workload:
    project = _require_project(identity)
    # admin: search all
    if identity.kind == "admin":
        for item in store.list():
            if item.name == name:
                return item
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload introuvable")
    workload = store.get(name, project=project.name)
    if workload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload introuvable")
    return workload


@app.post("/workloads/{name}/apply", response_model=Workload, tags=["workloads"])
def apply_named_workload(
    name: str, identity: IdentityDep
) -> Workload:
    project = _require_project(identity)
    workload = store.get(name, project=project.name)
    if workload is None and identity.kind == "admin":
        for item in store.list():
            if item.name == name:
                workload = item
                break
    if workload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload introuvable")
    try:
        runtime = apply_workload(workload)
    except (ClusterUnavailable, ClusterError) as exc:
        raise _cluster_http(exc) from exc
    updated = store.set_runtime(
        name,
        project=workload.project,
        status="ready" if runtime.available else "deploying",
        ready_replicas=runtime.ready_replicas,
        message=runtime.message,
        url=runtime.url,
    )
    assert updated is not None
    return updated


@app.get("/workloads/{name}/status", response_model=Workload, tags=["workloads"])
def workload_status(name: str, identity: IdentityDep) -> Workload:
    project = _require_project(identity)
    workload = store.get(name, project=project.name)
    if workload is None and identity.kind == "admin":
        for item in store.list():
            if item.name == name:
                workload = item
                break
    if workload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload introuvable")
    try:
        runtime = read_workload_status(workload)
    except (ClusterUnavailable, ClusterError) as exc:
        raise _cluster_http(exc) from exc
    updated = store.set_runtime(
        name,
        project=workload.project,
        status="ready" if runtime.available else "deploying",
        ready_replicas=runtime.ready_replicas,
        message=runtime.message,
        url=runtime.url,
    )
    assert updated is not None
    return updated


@app.delete("/workloads/{name}", status_code=status.HTTP_204_NO_CONTENT, tags=["workloads"])
def delete_workload(name: str, identity: IdentityDep) -> Response:
    project = _require_project(identity)
    workload = store.get(name, project=project.name)
    if workload is None and identity.kind == "admin":
        for item in store.list():
            if item.name == name:
                workload = item
                break
    if workload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload introuvable")
    store.delete(name, project=workload.project)
    if cluster_enabled() and workload.status in {"ready", "deploying"}:
        try:
            delete_from_cluster(workload)
        except ClusterUnavailable:
            pass
        except ClusterError as exc:
            raise _cluster_http(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/workloads/{name}/manifest", tags=["workloads"])
def workload_manifest(
    name: str, identity: IdentityDep
) -> PlainTextResponse:
    project = _require_project(identity)
    workload = store.get(name, project=project.name)
    if workload is None and identity.kind == "admin":
        for item in store.list():
            if item.name == name:
                workload = item
                break
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
def create_instance(
    payload: InstanceCreate,
    identity: IdentityDep,
) -> Instance:
    if not compute_enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="compute off")
    project = _require_project(identity)
    driver = compute_driver_name()
    try:
        instance = store.create_instance(payload, project=project, driver=driver)
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
        store.delete_instance(payload.name, project=project.name)
        raise _compute_http(exc) from exc

    updated = store.set_instance(
        payload.name,
        project=project.name,
        status=runtime.status,
        ipv4=runtime.ipv4,
        message=runtime.message,
        driver=driver,
    )
    assert updated is not None
    return updated


@app.get("/instances", response_model=list[Instance], tags=["compute"])
def list_instances(identity: IdentityDep) -> list[Instance]:
    return store.list_instances(project=_scope_project(identity))


@app.get("/instances/{name}", response_model=Instance, tags=["compute"])
def get_instance(name: str, identity: IdentityDep) -> Instance:
    project = _require_project(identity)
    instance = store.get_instance(name, project=project.name)
    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instance introuvable")
    return instance


@app.get("/instances/{name}/status", response_model=Instance, tags=["compute"])
def instance_status(name: str, identity: IdentityDep) -> Instance:
    project = _require_project(identity)
    instance = store.get_instance(name, project=project.name)
    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instance introuvable")
    try:
        runtime = read_instance(name)
    except ComputeError as exc:
        raise _compute_http(exc) from exc
    updated = store.set_instance(
        name,
        project=project.name,
        status=runtime.status,
        ipv4=runtime.ipv4,
        message=runtime.message,
        driver=compute_driver_name(),
    )
    assert updated is not None
    return updated


@app.post("/instances/{name}/stop", response_model=Instance, tags=["compute"])
def instance_stop(name: str, identity: IdentityDep) -> Instance:
    project = _require_project(identity)
    instance = store.get_instance(name, project=project.name)
    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instance introuvable")
    try:
        runtime = stop_instance(name)
    except ComputeError as exc:
        raise _compute_http(exc) from exc
    updated = store.set_instance(
        name,
        project=project.name,
        status=runtime.status,
        ipv4=runtime.ipv4,
        message=runtime.message,
    )
    assert updated is not None
    return updated


@app.post("/instances/{name}/start", response_model=Instance, tags=["compute"])
def instance_start(name: str, identity: IdentityDep) -> Instance:
    project = _require_project(identity)
    instance = store.get_instance(name, project=project.name)
    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instance introuvable")
    try:
        runtime = start_instance(name)
    except ComputeError as exc:
        raise _compute_http(exc) from exc
    updated = store.set_instance(
        name,
        project=project.name,
        status=runtime.status,
        ipv4=runtime.ipv4,
        message=runtime.message,
    )
    assert updated is not None
    return updated


@app.delete("/instances/{name}", status_code=status.HTTP_204_NO_CONTENT, tags=["compute"])
def remove_instance(name: str, identity: IdentityDep) -> Response:
    project = _require_project(identity)
    instance = store.get_instance(name, project=project.name)
    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instance introuvable")
    try:
        delete_instance(name)
    except ComputeError as exc:
        raise _compute_http(exc) from exc
    store.delete_instance(name, project=project.name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
