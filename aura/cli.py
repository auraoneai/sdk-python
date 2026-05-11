import argparse
import sys
from typing import List
from .client import AuraClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aura")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--org-id", default="public")
    parser.add_argument("--api-key", default=None)

    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list-templates")
    sub.add_parser("quotas")
    sub.add_parser("system-health")

    eval_p = sub.add_parser("evaluate")
    eval_p.add_argument("--template-id", required=True)
    eval_p.add_argument("--agent-bundle-url", required=True)
    eval_p.add_argument("--wait", action="store_true", default=False)
    eval_p.add_argument("--robust", action="store_true", default=False)

    return parser


def run_cli(argv: List[str]) -> int:
    args = build_parser().parse_args(argv)
    client = AuraClient(api_key=args.api_key, base_url=args.base_url, org_id=args.org_id)

    if args.cmd == "list-templates":
        items = client.list_templates()
        for t in items:
            print(f"{t.id}\t{t.name}\t{t.version}\t{t.domain or ''}")
        return 0

    if args.cmd == "evaluate":
        if args.robust:
            res = client.evaluate_robust(template_id=args.template_id, agent_bundle_url=args.agent_bundle_url, wait=args.wait)
        else:
            res = client.evaluate(template_id=args.template_id, agent_bundle_url=args.agent_bundle_url, wait=args.wait)
        print(res)
        return 0

    if args.cmd == "quotas":
        q = client.get_quotas()
        print(q)
        return 0

    if args.cmd == "system-health":
        h = client.get_system_health()
        print(h)
        return 0

    return 1


def main() -> None:
    sys.exit(run_cli(sys.argv[1:]))

