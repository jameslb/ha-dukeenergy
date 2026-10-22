"""Build local review bundles; never deploy, restart, install or access a network."""
# ruff: noqa: INP001

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOT_GATE = (
    "    if not hass.is_running:\n"
    '        message = "Waiting for Home Assistant startup before Duke setup"\n'
    "        raise ConfigEntryNotReady(message)\n\n"
)


def build(installed: Path, output: Path) -> None:
    """Preserve the verified installed bundle and overlay four reviewed files."""
    installed = installed.resolve()
    output = output.resolve()
    if output.exists() or "custom_components" in output.parts:
        message = "Output must be new and outside the integration search path"
        raise ValueError(message)
    lock = json.loads((ROOT / "deployment/installed-0.4.0.lock.json").read_text())
    files = {}
    for path in installed.rglob("*"):
        if path.is_symlink():
            message = "Symlinks are not accepted in the installed snapshot"
            raise ValueError(message)
        if path.is_file() and "__pycache__" not in path.parts:
            files[path.relative_to(installed).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    if files != lock["sha256"]:
        message = "Installed snapshot differs from the reviewed preflight; abort"
        raise ValueError(message)

    source = ROOT / "custom_components/duke_energy"
    for label in ("candidate", "rollback"):
        target = output / label / "custom_components/duke_energy"
        target.mkdir(parents=True)
        for name in files:
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(installed / name, destination)
        for name in (
            "__init__.py",
            "manifest.json",
            "client_dependency.py",
            "client_lock.json",
        ):
            shutil.copyfile(source / name, target / name)
        if label == "rollback":
            init = target / "__init__.py"
            text = init.read_text(encoding="utf-8")
            if text.count(BOOT_GATE) != 1:
                message = "Candidate startup gate differs from reviewed rollback"
                raise ValueError(message)
            init.write_text(text.replace(BOOT_GATE, ""), encoding="utf-8", newline="\n")
            manifest = target / "manifest.json"
            data = json.loads(manifest.read_text())
            data["version"] = lock["version"]
            manifest.write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n"
            )
        if json.loads((target / "manifest.json").read_text())["requirements"]:
            message = "Offline bundle must not declare installer requirements"
            raise ValueError(message)
        hashes = {
            path.relative_to(target).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted(target.rglob("*"))
            if path.is_file()
        }
        (output / label / "bundle-hashes.json").write_text(
            json.dumps(hashes, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.installed, args.output)
