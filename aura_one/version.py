"""Single version source for the AuraOne Python SDK."""

from __future__ import annotations

try:
    from importlib.metadata import PackageNotFoundError, version as _pkg_version

    try:
        __version__ = _pkg_version("auraone-sdk")
    except PackageNotFoundError:
        __version__ = "1.0.0"
except Exception:
    __version__ = "1.0.0"

VERSION = __version__

__all__ = ["__version__", "VERSION"]
