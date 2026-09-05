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
