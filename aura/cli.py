"""Command-line interface for the AuraOne hosted API."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import shutil
import sys
from datetime import date, datetime
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, TextIO

import httpx

from aura_one.exceptions import (
    AuraOneError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
    TimeoutError as AuraTimeoutError,
    ValidationError,
)
from aura_one.version import VERSION, __version__

from .client import AuraClient


EXIT_OK = 0
EXIT_UNEXPECTED = 1
EXIT_USAGE = 2
EXIT_AUTHENTICATION = 3
EXIT_AUTHORIZATION = 4
EXIT_NOT_FOUND = 5
EXIT_CONFLICT = 6
EXIT_VALIDATION = 7
EXIT_RATE_LIMIT = 8
EXIT_NETWORK = 9
EXIT_API = 10
EXIT_INTERRUPTED = 130

OUTPUT_FORMATS = ("table", "json", "jsonl")
_ANSI_BOLD = "\033[1m"
_ANSI_RED = "\033[31m"
_ANSI_RESET = "\033[0m"


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def _add_output_options(
    parser: argparse.ArgumentParser,
    *,
    suppress_defaults: bool = False,
) -> None:
    default: Any = argparse.SUPPRESS if suppress_defaults else "table"
    parser.add_argument(
        "-o",
        "--output",
        choices=OUTPUT_FORMATS,
        default=default,
        help="output format (default: table)",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        default=argparse.SUPPRESS if suppress_defaults else False,
        help="disable ANSI styling; NO_COLOR is also supported",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aura",
        description="Run hosted AuraOne evaluations and inspect account status.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--base-url",
        default=_env("AURAONE_BASE_URL", "https://api.auraone.ai"),
        help="AuraOne API URL (env: AURAONE_BASE_URL)",
    )
    parser.add_argument(
        "--org-id",
        default=_env("AURAONE_ORG_ID"),
        help="organization ID assertion (env: AURAONE_ORG_ID)",
    )
    parser.add_argument(
        "--api-key",
        default=_env("AURAONE_API_KEY") or _env("AURAONE_TOKEN"),
        help="API key (env: AURAONE_API_KEY or AURAONE_TOKEN)",
    )
    _add_output_options(parser)

    sub = parser.add_subparsers(dest="cmd", required=True)

    templates = sub.add_parser("list-templates", help="list evaluation templates")
    templates.add_argument("--domain", help="filter templates by domain")
    templates.add_argument("--page", type=int, default=1, help="page number (default: 1)")
    templates.add_argument(
        "--per-page",
        type=int,
        default=20,
        help="results per page (default: 20)",
    )
    _add_output_options(templates, suppress_defaults=True)

    quotas = sub.add_parser("quotas", help="show organization quotas")
    _add_output_options(quotas, suppress_defaults=True)

    health = sub.add_parser("system-health", help="show hosted service health")
    _add_output_options(health, suppress_defaults=True)

    evaluate = sub.add_parser("evaluate", help="create an evaluation")
    evaluate.add_argument("--template-id", required=True, help="template identifier")
    evaluate.add_argument(
        "--agent-bundle-url",
        required=True,
        help="URL of the agent bundle",
    )
    evaluate.add_argument(
        "--wait",
        action="store_true",
        default=False,
        help="wait for a terminal result",
    )
    evaluate.add_argument(
        "--robust",
        action="store_true",
        default=False,
        help="retry evaluation creation with idempotency protection",
    )
    _add_output_options(evaluate, suppress_defaults=True)

    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if args.cmd == "list-templates":
        if args.page < 1:
            raise CliUsageError("--page must be at least 1")
        if not 1 <= args.per_page <= 100:
            raise CliUsageError("--per-page must be between 1 and 100")


class CliUsageError(ValueError):
    """A parsed command contains an invalid option combination or value."""


def _json_value(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _json_value(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _display_value(value: Any) -> str:
    value = _json_value(value)
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def _table_rows(payload: Any) -> List[Dict[str, Any]]:
    normalized = _json_value(payload)
    if isinstance(normalized, list):
        if not normalized:
            return []
        if all(isinstance(item, dict) for item in normalized):
            return [dict(item) for item in normalized]
        return [{"value": item} for item in normalized]
    if isinstance(normalized, dict):
        return [{"field": key, "value": value} for key, value in normalized.items()]
    return [{"value": normalized}]


def _truncate(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    if width <= 3:
        return value[:width]
    return value[: width - 3] + "..."


def _render_table(payload: Any, *, color: bool) -> str:
    rows = _table_rows(payload)
    if not rows:
        return "No results."

    columns: List[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)

    terminal_width = max(40, shutil.get_terminal_size(fallback=(120, 24)).columns)
    spacing = 2 * max(0, len(columns) - 1)
    available = max(len(columns) * 8, terminal_width - spacing)
    max_column_width = max(8, available // max(1, len(columns)))
    widths = {
        column: min(
            max(
                len(column),
                max(len(_display_value(row.get(column))) for row in rows),
            ),
            max_column_width,
        )
        for column in columns
    }

    header = "  ".join(column.upper().ljust(widths[column]) for column in columns)
    if color:
        header = f"{_ANSI_BOLD}{header}{_ANSI_RESET}"
    separator = "  ".join("-" * widths[column] for column in columns)
    body = [
        "  ".join(
            _truncate(_display_value(row.get(column)), widths[column]).ljust(
                widths[column]
            )
            for column in columns
        ).rstrip()
        for row in rows
    ]
    return "\n".join([header, separator, *body])


def _emit(payload: Any, output: str, *, color: bool) -> None:
    normalized = _json_value(payload)
    if output == "json":
        print(json.dumps(normalized, indent=2, sort_keys=True))
        return
    if output == "jsonl":
        records: Iterable[Any] = (
            normalized if isinstance(normalized, list) else [normalized]
        )
        for record in records:
            print(json.dumps(record, sort_keys=True, separators=(",", ":")))
        return
    print(_render_table(normalized, color=color))


def _use_color(args: argparse.Namespace, stream: TextIO) -> bool:
    return (
        not args.no_color
        and "NO_COLOR" not in os.environ
        and hasattr(stream, "isatty")
        and stream.isatty()
    )


def _status_code(exc: BaseException) -> Optional[int]:
    if isinstance(exc, AuraOneError):
        return exc.status_code
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code
    return None


def _error_contract(exc: BaseException) -> tuple[int, str, str, Optional[str]]:
    status = _status_code(exc)
    message = str(exc).strip() or exc.__class__.__name__

    if isinstance(exc, CliUsageError):
        return (
            EXIT_USAGE,
            "usage_error",
            message,
            "Run 'aura --help' to review valid options.",
        )
    if isinstance(exc, AuthenticationError) or status == 401 or (
        isinstance(exc, ValueError) and "requires an API key" in message
    ):
        return (
            EXIT_AUTHENTICATION,
            "authentication_error",
            message,
            "Set AURAONE_API_KEY or pass --api-key with a valid AuraOne API key.",
        )
    if isinstance(exc, AuthorizationError) or status == 403:
        return (
            EXIT_AUTHORIZATION,
            "authorization_error",
            message,
            "Confirm the API key has access to this organization and operation.",
        )
    if isinstance(exc, NotFoundError) or status == 404:
        return (
            EXIT_NOT_FOUND,
            "not_found",
            message,
            "Check the resource identifier and --base-url.",
        )
    if isinstance(exc, ConflictError) or status == 409:
        return (
            EXIT_CONFLICT,
            "conflict",
            message,
            "Refresh the resource state before retrying.",
        )
    if isinstance(exc, ValidationError) or status in (400, 422):
        return (
            EXIT_VALIDATION,
            "validation_error",
            message,
            "Check the command arguments and resource values.",
        )
    if isinstance(exc, RateLimitError) or status == 429:
        retry_after = getattr(exc, "retry_after", None)
        hint = (
            f"Retry after {retry_after} seconds."
            if retry_after
            else "Wait briefly, then retry the request."
        )
        return EXIT_RATE_LIMIT, "rate_limit_error", message, hint
    if isinstance(
        exc,
        (
            NetworkError,
            AuraTimeoutError,
            httpx.NetworkError,
            httpx.TimeoutException,
            httpx.RequestError,
        ),
    ):
        return (
            EXIT_NETWORK,
            "network_error",
            message,
            "Check connectivity and --base-url, then retry.",
        )
    if isinstance(exc, (ServerError, AuraOneError, httpx.HTTPError)) or (
        status and status >= 500
    ):
        return (
            EXIT_API,
            "api_error",
            message,
            "The AuraOne API did not complete the request; retry or check service health.",
        )
    return (
        EXIT_UNEXPECTED,
        "unexpected_error",
        message,
        "Retry with valid inputs; report the error if it persists.",
    )


def _emit_error(exc: BaseException, args: argparse.Namespace) -> int:
    exit_code, error_type, message, hint = _error_contract(exc)
    payload = {
        "error": {
            "type": error_type,
            "message": message,
            "hint": hint,
            "status_code": _status_code(exc),
            "exit_code": exit_code,
        }
    }

    if args.output in ("json", "jsonl"):
        print(
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            file=sys.stderr,
        )
    else:
        color = _use_color(args, sys.stderr)
        label = (
            f"{_ANSI_RED}{_ANSI_BOLD}Error:{_ANSI_RESET}" if color else "Error:"
        )
        print(f"{label} {message}", file=sys.stderr)
        if hint:
            print(f"Hint: {hint}", file=sys.stderr)
    return exit_code


def _run_command(args: argparse.Namespace, client: AuraClient) -> Any:
    if args.cmd == "list-templates":
        return client.list_templates(
            domain=args.domain,
            page=args.page,
            per_page=args.per_page,
        )
    if args.cmd == "evaluate":
        evaluate: Callable[..., Any] = (
            client.evaluate_robust if args.robust else client.evaluate
        )
        return evaluate(
            template_id=args.template_id,
            agent_bundle_url=args.agent_bundle_url,
            wait=args.wait,
        )
    if args.cmd == "quotas":
        return client.get_quotas()
    if args.cmd == "system-health":
        return client.get_system_health()
    raise CliUsageError(f"unknown command: {args.cmd}")


def run_cli(argv: Sequence[str]) -> int:
    args = build_parser().parse_args(list(argv))
    client: Optional[AuraClient] = None
    try:
        _validate_args(args)
        client = AuraClient(
            api_key=args.api_key,
            base_url=args.base_url,
            org_id=args.org_id,
        )
        payload = _run_command(args, client)
        _emit(payload, args.output, color=_use_color(args, sys.stdout))
        return EXIT_OK
    except KeyboardInterrupt:
        print("Error: operation cancelled", file=sys.stderr)
        return EXIT_INTERRUPTED
    except Exception as exc:
        return _emit_error(exc, args)
    finally:
        if client is not None:
            close = getattr(client, "_client", None)
            if close is not None and hasattr(close, "close"):
                close.close()


def main() -> None:
    sys.exit(run_cli(sys.argv[1:]))


__all__ = [
    "VERSION",
    "__version__",
    "EXIT_OK",
    "EXIT_UNEXPECTED",
    "EXIT_USAGE",
    "EXIT_AUTHENTICATION",
    "EXIT_AUTHORIZATION",
    "EXIT_NOT_FOUND",
    "EXIT_CONFLICT",
    "EXIT_VALIDATION",
    "EXIT_RATE_LIMIT",
    "EXIT_NETWORK",
    "EXIT_API",
    "EXIT_INTERRUPTED",
    "OUTPUT_FORMATS",
    "CliUsageError",
    "build_parser",
    "run_cli",
    "main",
]
