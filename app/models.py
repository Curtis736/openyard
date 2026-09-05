from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.image_policy import validate_workload_image
from app.linux_images import list_linux_images, resolve_linux_image


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40, pattern=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
    pods_quota: int = Field(default=10, ge=1, le=50)
    cpu_quota: str = Field(default="1", pattern=r"^[0-9]+m?$|^[0-9]+(\.[0-9]+)?$")
    memory_quota: str = Field(default="1Gi", pattern=r"^[0-9]+(Mi|Gi)$")


class Project(BaseModel):
    name: str
    namespace: str
    api_key: str = ""
    pods_quota: int = 10
    cpu_quota: str = "1"
    memory_quota: str = "1Gi"
    created_at: datetime
    message: str = ""


class ProjectPublic(BaseModel):
    name: str
    namespace: str
    pods_quota: int
    cpu_quota: str
    memory_quota: str
    created_at: datetime
    message: str = ""
    api_key_set: bool = False
    pods_used: int = 0


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
    def image_allowed(cls, value: str) -> str:
        try:
            return validate_workload_image(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


class Workload(BaseModel):
    name: str
    project: str = "default"
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
    url: str = ""


class WorkloadStats(BaseModel):
    workloads: int
    pods_desired: int
    pods_ready: int = 0
    cluster_mode: bool = False
    instances: int = 0
    instances_running: int = 0
    compute_driver: str = "sim"
    projects: int = 0
    project: str | None = None


class InstanceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=63, pattern=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
    image: str = Field(default="ubuntu-22.04", min_length=1, max_length=64)
    vcpus: int = Field(default=1, ge=1, le=4)
    memory_mb: int = Field(default=1024, ge=256, le=8192)
    launch: bool = True

    @field_validator("image")
    @classmethod
    def linux_image_only(cls, value: str) -> str:
        return resolve_linux_image(value)["id"]


class Instance(BaseModel):
    name: str
    project: str = "default"
    image: str
    os: str = "linux"
    distro: str = "ubuntu"
    vcpus: int
    memory_mb: int
    created_at: datetime
    status: str = "pending"
    ipv4: str = ""
    driver: str = "sim"
    message: str = ""


class LinuxImageInfo(BaseModel):
    id: str
    name: str
    distro: str
    release: str
    description: str


def catalog_payload() -> list[LinuxImageInfo]:
    return [
        LinuxImageInfo(
            **{k: img[k] for k in ("id", "name", "distro", "release", "description")}
        )
        for img in list_linux_images()
    ]



class WorkloadEventOut(BaseModel):
    type: str
    reason: str
    message: str
    count: int = 1
    last_timestamp: str = ""
    involved_kind: str = ""
    involved_name: str = ""
