"""Verify the preinstalled pinned client without invoking a package manager."""

from __future__ import annotations

import hashlib
import json
from importlib import metadata, util
from pathlib import Path


class ClientUnavailableError(Exception):
    """The managed client is absent or differs from the reviewed fork."""


def verify_installed_client() -> None:
    """Require exact provenance, import location and source bytes; never install."""
    try:
        lock = json.loads(
            Path(__file__).with_name("client_lock.json").read_text(encoding="utf-8")
        )
        dist = metadata.distribution(lock["distribution"])
        provenance = json.loads(dist.read_text("direct_url.json") or "null")
        if not isinstance(provenance, dict):
            message = "Pinned Duke client provenance is missing"
            raise ClientUnavailableError(message)
        vcs = provenance.get("vcs_info", {})
        if not isinstance(vcs, dict):
            message = "Pinned Duke client VCS provenance is invalid"
            raise ClientUnavailableError(message)
        if (
            dist.version != lock["version"]
            or provenance.get("url") != lock["repository"]
            or vcs.get("vcs") != "git"
            or vcs.get("commit_id") != lock["commit"]
        ):
            message = "Installed Duke client differs from the pinned fork"
            raise ClientUnavailableError(message)

        expected = Path(dist.locate_file("aiodukeenergy/__init__.py")).resolve()
        spec = util.find_spec("aiodukeenergy")
        if (
            spec is None
            or spec.origin is None
            or Path(spec.origin).resolve() != expected
        ):
            message = "Duke client import location differs from provenance"
            raise ClientUnavailableError(message)

        for relative, digest in lock["sha256"].items():
            source = Path(dist.locate_file(relative)).read_bytes()
            if hashlib.sha256(source).hexdigest() != digest:
                message = "Installed Duke client source differs from lock"
                raise ClientUnavailableError(message)
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        metadata.PackageNotFoundError,
    ) as err:
        message = "Pinned Duke client cannot be verified; no install attempted"
        raise ClientUnavailableError(message) from err
