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
