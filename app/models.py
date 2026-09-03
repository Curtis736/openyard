from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class WorkloadCreate(BaseModel):
    name: str = Field(min_length=1, max_length=63, pattern=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
    image: str = Field(min_length=1, max_length=255)
    replicas: int = Field(default=1, ge=1, le=5)
    port: int = Field(default=8080, ge=1, le=65535)
    cpu: str = Field(default="50m", pattern=r"^[0-9]+m?$")
    memory: str = Field(default="64Mi", pattern=r"^[0-9]+(Mi|Gi)$")
    apply: bool = False

    @field_validator("image")
    @classmethod
    def image_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or " " in cleaned:
            raise ValueError("image Docker invalide")
        return cleaned


class Workload(BaseModel):
    name: str
    image: str
    replicas: int
    port: int
    cpu: str
    memory: str
    namespace: str
    created_at: datetime
    status: str = "registered"
    ready_replicas: int = 0
    message: str = ""


class WorkloadStats(BaseModel):
    workloads: int
    pods_desired: int
    pods_ready: int = 0
    cluster_mode: bool = False
