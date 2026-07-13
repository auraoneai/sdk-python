# Contributing to auraone-sdk

Thanks for your interest in contributing. This repository hosts the official AuraOne Python SDK and `aura` CLI — both clients for the hosted AuraOne API.

## Scope

We welcome:

- Bug reports with a minimal reproduction.
- Documentation fixes.
- New convenience methods that wrap existing API endpoints.
- CLI subcommand additions.
- Airflow operator improvements.

Out of scope:

- Hosted backend behavior — file issues that describe expected vs actual behavior; we'll route them.
- Changes that require breaking the public API surface — these need a deprecation cycle.

## Development

```bash
git clone https://github.com/auraoneai/sdk-python.git
cd sdk-python
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q tests
```

## Release preflight

Release preparation is intentionally separate from publishing. Update `pyproject.toml`, `aura_one/version.py`, and `CHANGELOG.md` to the same semantic version, then run:

```bash
version="$(python -c 'import aura_one; print(aura_one.__version__)')"
python scripts/release_preflight.py --expected-version "$version"
pytest -q tests
rm -rf build dist
python -m build
python -m twine check --strict dist/*
python scripts/release_preflight.py --expected-version "$version" --dist dist
```

Do not upload from a workstation. A matching `vX.Y.Z` tag triggers GitHub Actions, which rebuilds and verifies the distributions before publishing through PyPI trusted publishing. A manual workflow dispatch performs the same build-only validation unless its `publish` input is explicitly enabled and approved through the `pypi` environment.

## Pull request expectations

- Keep changes focused.
- Add or update tests when changing behavior.
- Conventional commit prefixes are appreciated.

## Code of Conduct

By participating, you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

Contributions are made under the [MIT License](LICENSE).

## Security

For security issues, do not file public issues. See [SECURITY.md](SECURITY.md).
