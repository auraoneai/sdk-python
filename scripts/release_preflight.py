#!/usr/bin/env python3
"""Validate source and distribution metadata before an auraone-sdk release."""

from __future__ import annotations

import argparse
import email.parser
import os
import re
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.9/3.10 workflow path
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+][0-9A-Za-z.-]+)?$")
WHEEL_NAME = re.compile(r"^auraone_sdk-(?P<version>[^-]+)-.+\.whl$")
SDIST_NAME = re.compile(r"^auraone_sdk-(?P<version>.+)\.tar\.gz$")


def _project_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def _module_version() -> str:
    text = (ROOT / "aura_one" / "version.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    if not match:
        raise ValueError("aura_one/version.py does not define __version__")
    return match.group(1)


def _ref_version() -> Optional[str]:
    ref = os.environ.get("GITHUB_REF", "")
    if ref.startswith("refs/tags/v"):
        return ref.removeprefix("refs/tags/v")
    return None


def _wheel_metadata(path: Path) -> Tuple[str, str]:
    with zipfile.ZipFile(path) as archive:
        metadata_names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ValueError(f"{path.name} must contain exactly one .dist-info/METADATA file")
        metadata = email.parser.Parser().parsestr(
            archive.read(metadata_names[0]).decode("utf-8", errors="strict")
        )
        names = set(archive.namelist())
        if not any(name.startswith("aura/") for name in names):
            raise ValueError(f"{path.name} does not contain the aura package")
        if not any(name.startswith("aura_one/") for name in names):
            raise ValueError(f"{path.name} does not contain the aura_one package")
        return metadata["Name"], metadata["Version"]


def _sdist_metadata(path: Path) -> Tuple[str, str]:
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getnames()
        pkg_info_names = [name for name in members if name.count("/") == 1 and name.endswith("/PKG-INFO")]
        if len(pkg_info_names) != 1:
            raise ValueError(f"{path.name} must contain exactly one top-level PKG-INFO file")
        extracted = archive.extractfile(pkg_info_names[0])
        if extracted is None:
            raise ValueError(f"could not read PKG-INFO from {path.name}")
        metadata = email.parser.Parser().parsestr(extracted.read().decode("utf-8", errors="strict"))
        if not any("/aura/cli.py" in name for name in members):
            raise ValueError(f"{path.name} does not contain aura/cli.py")
        if not any("/aura_one/version.py" in name for name in members):
            raise ValueError(f"{path.name} does not contain aura_one/version.py")
        return metadata["Name"], metadata["Version"]


def validate(expected_version: Optional[str], dist_dir: Optional[Path]) -> List[str]:
    errors: List[str] = []
    project_version = _project_version()
    module_version = _module_version()
    required_version = expected_version or _ref_version()

    if not SEMVER.fullmatch(project_version):
        errors.append(f"project version is not valid SemVer: {project_version}")
    if module_version != project_version:
        errors.append(
            f"version mismatch: pyproject.toml={project_version}, aura_one/version.py={module_version}"
        )
    if required_version and required_version != project_version:
        errors.append(f"release version mismatch: expected={required_version}, package={project_version}")

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## [{project_version}]" not in changelog:
        errors.append(f"CHANGELOG.md has no section for {project_version}")

    if dist_dir is not None:
        artifacts = sorted(path for path in dist_dir.iterdir() if path.is_file())
        wheels = [path for path in artifacts if path.suffix == ".whl"]
        sdists = [path for path in artifacts if path.name.endswith(".tar.gz")]
        unexpected = [path.name for path in artifacts if path not in wheels and path not in sdists]
        if len(wheels) != 1:
            errors.append(f"expected exactly one wheel in {dist_dir}, found {len(wheels)}")
        if len(sdists) != 1:
            errors.append(f"expected exactly one sdist in {dist_dir}, found {len(sdists)}")
        if unexpected:
            errors.append(f"unexpected files in {dist_dir}: {', '.join(unexpected)}")

        for artifact in wheels:
            match = WHEEL_NAME.fullmatch(artifact.name)
            if not match or match.group("version") != project_version:
                errors.append(f"wheel filename does not match version {project_version}: {artifact.name}")
                continue
            name, version = _wheel_metadata(artifact)
            if (name, version) != ("auraone-sdk", project_version):
                errors.append(f"wheel metadata mismatch: Name={name}, Version={version}")

        for artifact in sdists:
            match = SDIST_NAME.fullmatch(artifact.name)
            if not match or match.group("version") != project_version:
                errors.append(f"sdist filename does not match version {project_version}: {artifact.name}")
                continue
            name, version = _sdist_metadata(artifact)
            if (name, version) != ("auraone-sdk", project_version):
                errors.append(f"sdist metadata mismatch: Name={name}, Version={version}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-version", help="version expected from the release plan or tag")
    parser.add_argument("--dist", type=Path, help="validate the wheel and sdist in this directory")
    args = parser.parse_args()

    try:
        errors = validate(args.expected_version, args.dist)
    except (OSError, ValueError, KeyError, tomllib.TOMLDecodeError) as exc:
        errors = [str(exc)]

    if errors:
        for error in errors:
            print(f"release preflight failed: {error}", file=sys.stderr)
        return 1

    print(f"release preflight passed for auraone-sdk {_project_version()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
