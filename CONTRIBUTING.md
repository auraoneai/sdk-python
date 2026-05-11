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
