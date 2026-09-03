from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.linux_images import list_linux_images, resolve_linux_image


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
    url: str = ""


class WorkloadStats(BaseModel):
    workloads: int
    pods_desired: int
    pods_ready: int = 0
    cluster_mode: bool = False
    instances: int = 0
    instances_running: int = 0
    compute_driver: str = "sim"


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
