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


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _project_metadata() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]


def test_public_version_surfaces_match_project_metadata() -> None:
    version = _project_metadata()["version"]
    config = ClientConfig(api_key="aura_test_" + "a" * 32)
    client = AuraOneClient(config)
    async_client = AsyncAuraOneClient(config)

    assert aura_one.__version__ == version
    assert client.get_config()["version"] == version
    assert async_client.get_config()["version"] == version
    assert client.http_client.default_headers["User-Agent"] == f"auraone-python-sdk/{version}"
    assert async_client.http_client.default_headers["User-Agent"] == f"auraone-python-sdk/{version}"


def test_pypi_discovery_metadata_is_specific_and_focused() -> None:
    project = _project_metadata()
    description = project["description"].lower()
    keywords = project["keywords"]

    assert len(project["description"]) <= 200
    for phrase in ("python sdk", "cli", "hosted ai evaluations", "sync", "async"):
        assert phrase in description
    assert 8 <= len(keywords) <= 14
    assert len(keywords) == len(set(keywords))
    assert {
        "auraone",
        "ai-evaluation",
        "evaluation-api",
        "python-sdk",
        "async-client",
        "command-line-interface",
        "agent-evaluation",
        "model-evaluation",
        "llm-evaluation",
    } <= set(keywords)

    assert {
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Framework :: AsyncIO",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Quality Assurance",
    } <= set(project["classifiers"])

    assert {
        "Homepage",
        "Documentation",
        "Source",
        "Issues",
        "Changelog",
        "Security",
        "CI",
        "PyPI",
        "Releases",
        "TypeScript SDK",
        "Local EvalKit",
    } <= set(project["urls"])


def test_readme_covers_package_page_decision_and_release_contracts() -> None:
    project = _project_metadata()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for heading in (
        "## Choose This Package When",
        "## Install",
        "## First Useful Workflow",
        "## Sync, Async, And CLI",
        "## Credentials, Endpoint, And Data Boundary",
        "## Errors And Output Contracts",
        "## Source And Release Proof",
        "## Limitations",
        "## Next Action",
    ):
        assert heading in readme

    for marker in (
        "AuraOneClient",
        "AsyncAuraOneClient",
        "`aura` CLI",
        "AURAONE_API_KEY",
        "AURAONE_BASE_URL",
        "stdout",
        "stderr",
        "auraone-evalkit",
        "@auraone/sdk",
        "PyPI release and files",
    ):
        assert marker in readme

    assert f"| Current repository source | `{project['version']}` |" in readme
    assert f"`{project['version']}` was not published on July 13, 2026." in readme
