"""Catalogue des VM Linux proposées par OpenYard Compute."""

from __future__ import annotations

from typing import TypedDict


class LinuxImage(TypedDict):
    id: str
    name: str
    distro: str
    release: str
    multipass: str
    description: str


# Images Linux uniquement — mappées vers les alias Multipass.
LINUX_IMAGES: tuple[LinuxImage, ...] = (
    {
        "id": "ubuntu-22.04",
        "name": "Ubuntu 22.04 LTS",
        "distro": "ubuntu",
        "release": "22.04",
        "multipass": "22.04",
        "description": "Jammy Jellyfish — serveur Linux LTS",
    },
    {
        "id": "ubuntu-24.04",
        "name": "Ubuntu 24.04 LTS",
        "distro": "ubuntu",
        "release": "24.04",
        "multipass": "24.04",
        "description": "Noble Numbat — serveur Linux LTS",
    },
    {
        "id": "ubuntu-lts",
        "name": "Ubuntu LTS (courante)",
        "distro": "ubuntu",
        "release": "lts",
        "multipass": "lts",
        "description": "Dernière Ubuntu LTS Multipass",
    },
)

_BY_ID = {img["id"]: img for img in LINUX_IMAGES}
_BY_ALIAS = {
    **{img["id"]: img for img in LINUX_IMAGES},
    **{img["multipass"]: img for img in LINUX_IMAGES},
    **{img["release"]: img for img in LINUX_IMAGES},
    "ubuntu": _BY_ID["ubuntu-lts"],
    "linux": _BY_ID["ubuntu-lts"],
}


def list_linux_images() -> list[LinuxImage]:
    return list(LINUX_IMAGES)


def resolve_linux_image(value: str) -> LinuxImage:
    key = value.strip().lower()
    image = _BY_ALIAS.get(key)
    if image is None:
        allowed = ", ".join(img["id"] for img in LINUX_IMAGES)
        raise ValueError(f"image Linux inconnue : {value!r} (choix : {allowed})")
    return image


def multipass_alias(value: str) -> str:
    return resolve_linux_image(value)["multipass"]
