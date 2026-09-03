from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import yaml

from app.manifests import render_deployment, render_ingress, render_service, workload_url
from app.models import Workload

logger = logging.getLogger("openyard.cluster")


class ClusterUnavailable(RuntimeError):
    """Pas de kubeconfig / API Kubernetes injoignable."""


class ClusterError(RuntimeError):
    """Échec d’une opération sur le cluster."""


@dataclass(frozen=True)
class WorkloadRuntime:
    ready_replicas: int
    desired_replicas: int
    available: bool
    message: str
    url: str = ""


def cluster_enabled() -> bool:
    return os.getenv("OPENYARD_CLUSTER", "auto").lower() not in {"0", "false", "off", "no"}


def get_clients():
    try:
        from kubernetes import client, config
    except ImportError as exc:  # pragma: no cover
        raise ClusterUnavailable("paquet kubernetes non installé") from exc

    try:
        config.load_incluster_config()
    except config.ConfigException:
        try:
            config.load_kube_config()
        except config.ConfigException as exc:
            raise ClusterUnavailable("aucun kubeconfig disponible") from exc

    return client.AppsV1Api(), client.CoreV1Api(), client.NetworkingV1Api(), client


def _clients():
    return get_clients()


def apply_workload(workload: Workload) -> WorkloadRuntime:
    """Crée ou met à jour Deployment + Service + Ingress pour une charge."""
    if not cluster_enabled():
        raise ClusterUnavailable("OPENYARD_CLUSTER désactivé")

    apps, core, networking, client = _clients()
    dep = yaml.safe_load(render_deployment(workload))
    svc = yaml.safe_load(render_service(workload))
    ing = yaml.safe_load(render_ingress(workload))

    try:
        try:
            apps.read_namespaced_deployment(workload.name, workload.namespace)
            apps.replace_namespaced_deployment(workload.name, workload.namespace, dep)
        except client.exceptions.ApiException as exc:
            if exc.status != 404:
                raise ClusterError(str(exc)) from exc
            apps.create_namespaced_deployment(workload.namespace, dep)

        try:
            existing = core.read_namespaced_service(workload.name, workload.namespace)
            existing.spec.selector = {"app.kubernetes.io/name": workload.name}
            existing.spec.ports = [
                client.V1ServicePort(name="http", port=80, target_port="http")
            ]
            core.replace_namespaced_service(workload.name, workload.namespace, existing)
        except client.exceptions.ApiException as exc:
            if exc.status != 404:
                raise ClusterError(str(exc)) from exc
            core.create_namespaced_service(workload.namespace, svc)

        try:
            networking.read_namespaced_ingress(workload.name, workload.namespace)
            networking.replace_namespaced_ingress(workload.name, workload.namespace, ing)
        except client.exceptions.ApiException as exc:
            if exc.status != 404:
                raise ClusterError(str(exc)) from exc
            networking.create_namespaced_ingress(workload.namespace, ing)
    except ClusterError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ClusterError(str(exc)) from exc

    runtime = read_workload_status(workload)
    return WorkloadRuntime(
        ready_replicas=runtime.ready_replicas,
        desired_replicas=runtime.desired_replicas,
        available=runtime.available,
        message=runtime.message,
        url=workload_url(workload.name),
    )


def delete_from_cluster(workload: Workload) -> None:
    if not cluster_enabled():
        raise ClusterUnavailable("OPENYARD_CLUSTER désactivé")

    apps, core, networking, client = _clients()
    for reader, deleter, kind in (
        (networking.read_namespaced_ingress, networking.delete_namespaced_ingress, "Ingress"),
        (apps.read_namespaced_deployment, apps.delete_namespaced_deployment, "Deployment"),
        (core.read_namespaced_service, core.delete_namespaced_service, "Service"),
    ):
        try:
            reader(workload.name, workload.namespace)
            deleter(workload.name, workload.namespace)
        except client.exceptions.ApiException as exc:
            if exc.status == 404:
                continue
            raise ClusterError(f"{kind}: {exc}") from exc


def read_workload_status(workload: Workload) -> WorkloadRuntime:
    if not cluster_enabled():
        raise ClusterUnavailable("OPENYARD_CLUSTER désactivé")

    apps, _core, _networking, client = _clients()
    try:
        dep = apps.read_namespaced_deployment(workload.name, workload.namespace)
    except client.exceptions.ApiException as exc:
        if exc.status == 404:
            return WorkloadRuntime(
                ready_replicas=0,
                desired_replicas=workload.replicas,
                available=False,
                message="deployment absent du cluster",
                url=workload_url(workload.name),
            )
        raise ClusterError(str(exc)) from exc

    ready = dep.status.ready_replicas or 0
    desired = dep.spec.replicas or workload.replicas
    available = ready >= desired and desired > 0
    conditions = dep.status.conditions or []
    message = conditions[-1].message if conditions else "déployé"
    return WorkloadRuntime(
        ready_replicas=ready,
        desired_replicas=desired,
        available=available,
        message=message or "déployé",
        url=workload_url(workload.name),
    )
