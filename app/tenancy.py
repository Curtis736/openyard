from __future__ import annotations

import logging

from app.models import Project

logger = logging.getLogger("openyard.tenancy")


def project_namespace(name: str) -> str:
    if name == "default":
        import os

        return os.getenv("OPENYARD_NAMESPACE", "openyard")
    return f"oy-{name}"


def ensure_project_namespace(project: Project) -> str:
    """Crée namespace + ResourceQuota + RoleBinding pour le control plane."""
    from app.cluster import (
        ClusterError,
        ClusterUnavailable,
        cluster_enabled,
        get_clients,
    )

    if not cluster_enabled():
        return "cluster off"

    if project.name == "default":
        return f"namespace existant {project.namespace}"

    try:
        _apps, core, _net, client = get_clients()
    except ClusterUnavailable as exc:
        raise ClusterUnavailable(str(exc)) from exc

    ns_name = project.namespace
    ns_body = {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": ns_name,
            "labels": {
                "openyard.io/project": project.name,
                "openyard.io/managed": "true",
            },
        },
    }
    try:
        try:
            core.read_namespace(ns_name)
        except client.exceptions.ApiException as exc:
            if exc.status != 404:
                raise ClusterError(str(exc)) from exc
            core.create_namespace(ns_body)

        quota = {
            "apiVersion": "v1",
            "kind": "ResourceQuota",
            "metadata": {
                "name": "openyard-project",
                "namespace": ns_name,
                "labels": {"openyard.io/project": project.name},
            },
            "spec": {
                "hard": {
                    "pods": str(project.pods_quota),
                    "requests.cpu": project.cpu_quota,
                    "requests.memory": project.memory_quota,
                    "limits.cpu": project.cpu_quota,
                    "limits.memory": project.memory_quota,
                }
            },
        }
        try:
            core.read_namespaced_resource_quota("openyard-project", ns_name)
            core.replace_namespaced_resource_quota("openyard-project", ns_name, quota)
        except client.exceptions.ApiException as exc:
            if exc.status != 404:
                raise ClusterError(str(exc)) from exc
            core.create_namespaced_resource_quota(ns_name, quota)

        # Role + RoleBinding pour que le SA control plane gère ce namespace
        from kubernetes import client as k8s

        rbac = k8s.RbacAuthorizationV1Api()
        role = {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "Role",
            "metadata": {"name": "openyard-control", "namespace": ns_name},
            "rules": [
                {
                    "apiGroups": ["apps"],
                    "resources": ["deployments"],
                    "verbs": ["get", "list", "watch", "create", "update", "patch", "delete"],
                },
                {
                    "apiGroups": [""],
                    "resources": ["services", "pods", "resourcequotas"],
                    "verbs": ["get", "list", "watch", "create", "update", "patch", "delete"],
                },
                {
                    "apiGroups": ["networking.k8s.io"],
                    "resources": ["ingresses"],
                    "verbs": ["get", "list", "watch", "create", "update", "patch", "delete"],
                },
            ],
        }
        try:
            rbac.read_namespaced_role("openyard-control", ns_name)
            rbac.replace_namespaced_role("openyard-control", ns_name, role)
        except client.exceptions.ApiException as exc:
            if exc.status != 404:
                raise ClusterError(str(exc)) from exc
            rbac.create_namespaced_role(ns_name, role)

        binding = {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "RoleBinding",
            "metadata": {"name": "openyard-control", "namespace": ns_name},
            "roleRef": {
                "apiGroup": "rbac.authorization.k8s.io",
                "kind": "Role",
                "name": "openyard-control",
            },
            "subjects": [
                {
                    "kind": "ServiceAccount",
                    "name": "openyard-control",
                    "namespace": "openyard",
                }
            ],
        }
        try:
            rbac.read_namespaced_role_binding("openyard-control", ns_name)
            rbac.replace_namespaced_role_binding("openyard-control", ns_name, binding)
        except client.exceptions.ApiException as exc:
            if exc.status != 404:
                raise ClusterError(str(exc)) from exc
            rbac.create_namespaced_role_binding(ns_name, binding)

    except ClusterError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ClusterError(str(exc)) from exc

    return f"namespace prêt {ns_name}"


def delete_project_namespace(project: Project) -> None:
    from app.cluster import ClusterError, ClusterUnavailable, cluster_enabled, get_clients

    if not cluster_enabled() or project.name == "default":
        return
    try:
        _apps, core, _net, client = get_clients()
    except ClusterUnavailable:
        return
    try:
        core.delete_namespace(project.namespace)
    except client.exceptions.ApiException as exc:
        if exc.status == 404:
            return
        raise ClusterError(str(exc)) from exc
