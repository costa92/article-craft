#!/usr/bin/env python3
"""Unified runtime healthcheck for article-craft."""

from __future__ import annotations

import argparse
import json

from setup_dependencies import run_all_checks


def summarize(results: list[dict]) -> dict[str, int]:
    summary = {"pass": 0, "warn": 0, "block": 0}
    for result in results:
        status = result.get("status", "")
        if status in summary:
            summary[status] += 1
    return summary


def overall_status(results: list[dict]) -> str:
    statuses = {result.get("status") for result in results}
    if "block" in statuses:
        return "block"
    if "warn" in statuses:
        return "warn"
    return "pass"


def _render_human(payload: dict) -> None:
    print("article-craft doctor")
    print()
    for result in payload["checks"]:
        icon = {"pass": "PASS", "warn": "WARN", "block": "BLOCK"}[result["status"]]
        line = f"[{icon}] {result['name']}: {result['message']}"
        if result.get("name") == "notebooklm_cli":
            details = result.get("details") or {}
            command = details.get("command")
            flavor = details.get("flavor")
            if command and flavor:
                line += f" [{flavor}, cmd={command}]"
        print(line)
        if result.get("fix"):
            print(f"       fix: {result['fix']}")
    print()
    print(
        "summary: "
        f"{payload['summary']['pass']} pass, "
        f"{payload['summary']['warn']} warn, "
        f"{payload['summary']['block']} block"
    )


def cmd_check(args: argparse.Namespace) -> int:
    results = run_all_checks()
    status = overall_status(results)
    payload = {
        "ok": status == "pass",
        "status": status,
        "summary": summarize(results),
        "checks": results,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _render_human(payload)

    return {"pass": 0, "warn": 1, "block": 2}[status]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="doctor", description="article-craft runtime healthcheck")
    sub = parser.add_subparsers(dest="cmd", required=True)

    check = sub.add_parser("check", help="run dependency healthchecks")
    check.add_argument("--json", action="store_true", help="emit JSON output")
    check.set_defaults(func=cmd_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
