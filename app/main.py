from fastapi import FastAPI, HTTPException, Response, status
from fastapi.responses import PlainTextResponse

from app import __version__
from app.manifests import render_bundle
from app.models import Workload, WorkloadCreate, WorkloadStats
from app.store import WorkloadStore

store = WorkloadStore()

app = FastAPI(
    title="OpenYard",
    version=__version__,
    description=(
        "Mini-cloud open source : on enregistre une image Docker et un nombre "
        "de réplicas, l’API produit (et peut appliquer) le Deployment Kubernetes "
        "qui matérialise des pods."
    ),
)


@app.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/metrics", include_in_schema=False)
def metrics() -> PlainTextResponse:
    stats = store.stats()
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
            "",
        ]
    )
    return PlainTextResponse(body, media_type="text/plain; version=0.0.4; charset=utf-8")


@app.get("/stats", response_model=WorkloadStats, tags=["ops"])
def stats() -> WorkloadStats:
    return store.stats()


@app.post(
    "/workloads",
    response_model=Workload,
    status_code=status.HTTP_201_CREATED,
    tags=["workloads"],
)
def create_workload(payload: WorkloadCreate) -> Workload:
    try:
        return store.create(payload)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workload déjà enregistré : {payload.name}",
        ) from exc


@app.get("/workloads", response_model=list[Workload], tags=["workloads"])
def list_workloads() -> list[Workload]:
    return store.list()


@app.get("/workloads/{name}", response_model=Workload, tags=["workloads"])
def get_workload(name: str) -> Workload:
    workload = store.get(name)
    if workload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload introuvable")
    return workload


@app.delete("/workloads/{name}", status_code=status.HTTP_204_NO_CONTENT, tags=["workloads"])
def delete_workload(name: str) -> Response:
    if not store.delete(name):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload introuvable")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/workloads/{name}/manifest", tags=["workloads"])
def workload_manifest(name: str) -> PlainTextResponse:
    workload = store.get(name)
    if workload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload introuvable")
    return PlainTextResponse(render_bundle(workload), media_type="application/yaml")
