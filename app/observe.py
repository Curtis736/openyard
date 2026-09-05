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
