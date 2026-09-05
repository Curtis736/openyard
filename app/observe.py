"""Lecture Events / logs pods pour la console OpenYard."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkloadEvent:
    type: str
    reason: str
    message: str
    count: int
    last_timestamp: str
    involved_kind: str
    involved_name: str


def _require_cluster():
    from app.cluster import ClusterUnavailable, cluster_enabled, get_clients

    if not cluster_enabled():
        raise ClusterUnavailable("OPENYARD_CLUSTER désactivé")
    return get_clients()


def list_workload_events(namespace: str, name: str, limit: int = 40) -> list[WorkloadEvent]:
    from app.cluster import ClusterError

    _apps, core, _net, client = _require_cluster()
    items: list[WorkloadEvent] = []
    try:
        for field in (
            f"involvedObject.name={name}",
        ):
            try:
                bundle = core.list_namespaced_event(
                    namespace, field_selector=field, limit=limit
                )
            except TypeError:
                bundle = core.list_namespaced_event(namespace, field_selector=field)
            for ev in bundle.items or []:
                meta = ev.metadata
                involved = ev.involved_object
                ts = (
                    getattr(ev, "last_timestamp", None)
                    or getattr(ev, "event_time", None)
                    or getattr(meta, "creation_timestamp", None)
                )
                items.append(
                    WorkloadEvent(
                        type=(ev.type or "Normal"),
                        reason=(ev.reason or ""),
                        message=(ev.message or ""),
                        count=int(ev.count or 1),
                        last_timestamp=str(ts) if ts else "",
                        involved_kind=(involved.kind if involved else ""),
                        involved_name=(involved.name if involved else ""),
                    )
                )
        # pods of the workload
        pods = core.list_namespaced_pod(
            namespace, label_selector=f"app.kubernetes.io/name={name}"
        )
        for pod in pods.items or []:
            pname = pod.metadata.name
            try:
                bundle = core.list_namespaced_event(
                    namespace, field_selector=f"involvedObject.name={pname}", limit=limit
                )
            except TypeError:
                bundle = core.list_namespaced_event(
                    namespace, field_selector=f"involvedObject.name={pname}"
                )
            for ev in bundle.items or []:
                meta = ev.metadata
                involved = ev.involved_object
                ts = (
                    getattr(ev, "last_timestamp", None)
                    or getattr(ev, "event_time", None)
                    or getattr(meta, "creation_timestamp", None)
                )
                items.append(
                    WorkloadEvent(
                        type=(ev.type or "Normal"),
                        reason=(ev.reason or ""),
                        message=(ev.message or ""),
                        count=int(ev.count or 1),
                        last_timestamp=str(ts) if ts else "",
                        involved_kind=(involved.kind if involved else ""),
                        involved_name=(involved.name if involved else ""),
                    )
                )
    except client.exceptions.ApiException as exc:
        raise ClusterError(str(exc)) from exc

    # de-dup rough
    seen: set[tuple] = set()
    unique: list[WorkloadEvent] = []
    for item in items:
        key = (item.reason, item.message, item.involved_name, item.last_timestamp)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[:limit]


def read_workload_logs(namespace: str, name: str, tail_lines: int = 200) -> str:
    from app.cluster import ClusterError

    _apps, core, _net, client = _require_cluster()
    try:
        pods = core.list_namespaced_pod(
            namespace, label_selector=f"app.kubernetes.io/name={name}"
        )
    except client.exceptions.ApiException as exc:
        raise ClusterError(str(exc)) from exc

    if not pods.items:
        return "(aucun pod pour ce workload)\n"

    # prefer ready pod
    chosen = pods.items[0]
    for pod in pods.items:
        conds = pod.status.conditions or []
        if any(c.type == "Ready" and c.status == "True" for c in conds):
            chosen = pod
            break

    pod_name = chosen.metadata.name
    try:
        text = core.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            tail_lines=tail_lines,
            timestamps=True,
        )
    except client.exceptions.ApiException as exc:
        raise ClusterError(str(exc)) from exc
    header = f"# pod={pod_name} namespace={namespace} tail={tail_lines}\n"
    return header + (text or "")
