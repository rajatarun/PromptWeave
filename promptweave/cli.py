"""Command-line interface for PromptWeave."""

from __future__ import annotations

import argparse
import json
import sys

from promptweave.adapters import SUPPORTED_FAMILIES
from promptweave.compiler import compile_prompt
from promptweave.spec import IntentSpec


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="promptweave",
        description="Deterministic model-family prompt compiler.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    compile_cmd = sub.add_parser(
        "compile",
        help="Compile a JSON IntentSpec file for a target model family.",
    )
    compile_cmd.add_argument("spec_path", help="Path to JSON IntentSpec file.")
    compile_cmd.add_argument(
        "--family",
        default="openai_compat",
        choices=SUPPORTED_FAMILIES,
        help="Target model family (default: openai_compat).",
    )
    compile_cmd.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Optional token budget; trims lowest-priority context_blocks first.",
    )
    compile_cmd.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit machine-readable JSON output including prompt_id and sha256.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "compile":
        try:
            spec = IntentSpec.from_json_file(args.spec_path)
            compiled = compile_prompt(
                spec,
                family=args.family,
                max_tokens=args.max_tokens,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

        if args.as_json:
            print(json.dumps(compiled.to_dict(), indent=2))
        else:
            print(compiled.rendered)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
