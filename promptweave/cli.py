"""Command-line interface for PromptWeave."""

from __future__ import annotations

import argparse
import json
import sys

from promptweave.adapters import SUPPORTED_FAMILIES
from promptweave.compiler import compile_prompt
from promptweave.diff import diff_compiled
from promptweave.matrix import compile_matrix
from promptweave.registry import PromptRegistry
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

    diff_cmd = sub.add_parser(
        "diff",
        help="Diff two JSON IntentSpec files after compilation.",
    )
    diff_cmd.add_argument("spec_a", help="Path to baseline JSON IntentSpec file.")
    diff_cmd.add_argument("spec_b", help="Path to updated JSON IntentSpec file.")
    diff_cmd.add_argument(
        "--family",
        default="openai_compat",
        choices=SUPPORTED_FAMILIES,
        help="Target model family (default: openai_compat).",
    )
    diff_cmd.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Optional token budget applied to both specs.",
    )
    diff_cmd.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit machine-readable JSON diff output.",
    )

    reg_cmd = sub.add_parser(
        "registry",
        help="Manage compiled prompt artifacts in a SQLite WAL registry.",
    )
    reg_sub = reg_cmd.add_subparsers(dest="registry_command", required=True)

    reg_register = reg_sub.add_parser(
        "register",
        help="Compile an IntentSpec JSON file and register its prompt-artifact-v1 record.",
    )
    reg_register.add_argument("--db", required=True, help="Path to SQLite registry database.")
    reg_register.add_argument("spec_path", help="Path to JSON IntentSpec file.")
    reg_register.add_argument(
        "--family",
        default="openai_compat",
        choices=SUPPORTED_FAMILIES,
        help="Target model family (default: openai_compat).",
    )
    reg_register.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Optional token budget.",
    )
    reg_register.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit machine-readable JSON output.",
    )

    reg_list = reg_sub.add_parser(
        "list",
        help="List registered prompt artifacts.",
    )
    reg_list.add_argument("--db", required=True, help="Path to SQLite registry database.")
    reg_list.add_argument("--name", default=None, help="Optional prompt name filter.")
    reg_list.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit machine-readable JSON output.",
    )

    reg_get = reg_sub.add_parser(
        "get",
        help="Fetch a registered prompt artifact by prompt_id.",
    )
    reg_get.add_argument("--db", required=True, help="Path to SQLite registry database.")
    reg_get.add_argument("prompt_id", help="Pinned prompt_id to retrieve.")
    reg_get.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit machine-readable JSON output.",
    )

    reg_verify = reg_sub.add_parser(
        "verify",
        help="Verify SHA-256 integrity of a registered prompt artifact.",
    )
    reg_verify.add_argument("--db", required=True, help="Path to SQLite registry database.")
    reg_verify.add_argument("prompt_id", help="Pinned prompt_id to verify.")
    reg_verify.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit machine-readable JSON output.",
    )

    matrix_cmd = sub.add_parser(
        "matrix",
        help="Compile a JSON IntentSpec across multiple model families and compare footprints.",
    )
    matrix_cmd.add_argument("spec_path", help="Path to JSON IntentSpec file.")
    matrix_cmd.add_argument(
        "--families",
        default=None,
        help="Comma-separated list of model families (default: all supported families).",
    )
    matrix_cmd.add_argument(
        "--var",
        dest="vars",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Template variable binding in KEY=VALUE form (repeatable).",
    )
    matrix_cmd.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Optional token budget applied to every family in the matrix.",
    )
    matrix_cmd.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit machine-readable JSON matrix report.",
    )

    return parser


def _handle_diff(args: argparse.Namespace) -> int:
    try:
        spec_a = IntentSpec.from_json_file(args.spec_a)
        spec_b = IntentSpec.from_json_file(args.spec_b)
        compiled_a = compile_prompt(spec_a, family=args.family, max_tokens=args.max_tokens)
        compiled_b = compile_prompt(spec_b, family=args.family, max_tokens=args.max_tokens)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    diff = diff_compiled(compiled_a, compiled_b)
    if args.as_json:
        print(json.dumps(diff.to_dict(), indent=2))
    else:
        print(f"changed: {diff.changed}")
        print(f"sha256_changed: {diff.sha256_changed}")
        print(f"token_delta: {diff.token_delta:+d}")
        if diff.unified_system_diff:
            print(diff.unified_system_diff)
        if diff.unified_user_diff:
            print(diff.unified_user_diff)
    return 0


def _handle_registry(args: argparse.Namespace) -> int:
    with PromptRegistry(args.db) as registry:
        if args.registry_command == "register":
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
            artifact = registry.register(compiled, name=spec.name)
            if args.as_json:
                print(json.dumps(artifact, indent=2))
            else:
                print(artifact["prompt_id"])
            return 0

        if args.registry_command == "list":
            artifacts = registry.list_versions(args.name)
            if args.as_json:
                print(json.dumps(artifacts, indent=2))
            else:
                for item in artifacts:
                    print(f"{item['prompt_id']} ({item['family']}, {item['estimated_tokens']} tok)")
            return 0

        if args.registry_command == "get":
            artifact = registry.get(args.prompt_id)
            if artifact is None:
                print(f"Error: prompt_id not found: {args.prompt_id}", file=sys.stderr)
                return 1
            if args.as_json:
                print(json.dumps(artifact, indent=2))
            else:
                print(f"prompt_id: {artifact['prompt_id']}")
                print(f"family: {artifact['family']}")
                print(f"estimated_tokens: {artifact['estimated_tokens']}")
                print(f"system_prompt:\n{artifact['system_prompt']}")
                print(f"user_prompt:\n{artifact['user_prompt']}")
            return 0

        if args.registry_command == "verify":
            ok = registry.verify(args.prompt_id)
            if args.as_json:
                print(json.dumps({"prompt_id": args.prompt_id, "valid": ok}, indent=2))
            elif ok:
                print(f"OK: {args.prompt_id}")
            else:
                print(f"INVALID: {args.prompt_id}", file=sys.stderr)
            return 0 if ok else 1

    return 2


def _parse_var_bindings(raw_vars: list[str]) -> dict[str, str] | None:
    if not raw_vars:
        return None
    bindings: dict[str, str] = {}
    for item in raw_vars:
        key, sep, value = item.partition("=")
        if not sep or not key.strip():
            raise ValueError(f"Invalid --var binding '{item}'; expected KEY=VALUE.")
        bindings[key.strip()] = value
    return bindings


def _handle_matrix(args: argparse.Namespace) -> int:
    try:
        spec = IntentSpec.from_json_file(args.spec_path)
        families: list[str] | None = None
        if args.families is not None:
            families = [part.strip() for part in args.families.split(",") if part.strip()]
            if not families:
                raise ValueError("--families must specify at least one model family.")
        variables = _parse_var_bindings(args.vars)
        report = compile_matrix(
            spec,
            families=families,
            variables=variables,
            max_tokens=args.max_tokens,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"spec: {report.spec_name}")
        for fam, entry in report.families.items():
            trimmed = ", ".join(entry.trimmed_blocks) if entry.trimmed_blocks else "none"
            print(
                f"  {fam}: {entry.estimated_tokens} tok | "
                f"trimmed={trimmed} | {entry.prompt_id}"
            )
        print(f"min_tokens_family: {report.min_tokens_family}")
        print(f"max_tokens_family: {report.max_tokens_family}")
    return 0


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

    if args.command == "diff":
        return _handle_diff(args)

    if args.command == "registry":
        return _handle_registry(args)

    if args.command == "matrix":
        return _handle_matrix(args)

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
