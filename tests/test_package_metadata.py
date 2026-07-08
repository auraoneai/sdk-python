from __future__ import annotations

import pathlib
import sys

import aura_one
from aura_one import AuraOneClient, AsyncAuraOneClient
from aura_one.types import ClientConfig

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def test_public_version_surfaces_match_project_metadata() -> None:
    pyproject_path = pathlib.Path(__file__).resolve().parents[1] / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    version = pyproject["project"]["version"]
    config = ClientConfig(api_key="aura_test_" + "a" * 32)
    client = AuraOneClient(config)
    async_client = AsyncAuraOneClient(config)

    assert aura_one.__version__ == version
    assert client.get_config()["version"] == version
    assert async_client.get_config()["version"] == version
    assert client.http_client.default_headers["User-Agent"] == f"auraone-python-sdk/{version}"
    assert async_client.http_client.default_headers["User-Agent"] == f"auraone-python-sdk/{version}"
