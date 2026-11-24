"""Deterministic prompt lockfile generation and drift detection for PromptWeave."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from promptweave.adapters import SUPPORTED_FAMILIES
from promptweave.compiler import compile_prompt
from promptweave.fingerprint import compute_sha256
from promptweave.registry import PromptRegistry
from promptweave.spec import IntentSpec

LOCK_VERSION = "1"
_FAMILY_ALIASES: dict[str, str] = {
    "openai": "openai_compat",
    "local": "local_small",
}


def _resolve_compiler_family(family: str) -> str:
    canonical = _FAMILY_ALIASES.get(family, family)
    if canonical not in SUPPORTED_FAMILIES:
        raise ValueError(
            f"Unsupported model family {family!r}; expected one of "
            f"{sorted(set(SUPPORTED_FAMILIES) | set(_FAMILY_ALIASES))}"
        )
    return canonical


def _live_artifact_sha256(registry: PromptRegistry, artifact: dict[str, Any]) -> str:
    """Return the verified SHA-256 of a registered artifact, or a recomputed hash if tampered."""
    if registry.verify(artifact["prompt_id"]):
        return str(artifact["sha256"])
    return compute_sha256(
        {
            "tampered": True,
            "name": artifact["name"],
            "family": artifact["family"],
            "system_prompt": artifact["system_prompt"],
            "user_prompt": artifact["user_prompt"],
        }
    )


def generate_lockfile(
    registry: PromptRegistry,
    families: list[str] | None = None,
) -> dict[str, Any]:
    """Generate a deterministic lockfile pinning compiled prompt hashes in ``registry``.

    Entry keys follow ``"<name>@<version>:<family>"`` with
    ``{"sha256": <64-hex>, "token_estimate": <int>}``.
    """
    # list_versions() returns newest-first; reverse so chronological order is v1, v2, ...
    all_artifacts = list(reversed(registry.list_versions()))

    by_name_family: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for art in all_artifacts:
        by_name_family[(art["name"], art["family"])].append(art)
        by_name[art["name"]].append(art)

    entries: dict[str, dict[str, Any]] = {}
    resolved_families: list[str] | None = None

    if families is None:
        for (name, family), artifacts in sorted(by_name_family.items()):
            for idx, art in enumerate(artifacts, start=1):
                key = f"{name}@v{idx}:{family}"
                entries[key] = {
                    "sha256": _live_artifact_sha256(registry, art),
                    "token_estimate": int(art["estimated_tokens"]),
                }
    else:
        resolved_families = list(families)
        for fam in resolved_families:
            _resolve_compiler_family(fam)

        for name in sorted(by_name.keys()):
            base_artifacts = by_name[name]
            latest = base_artifacts[-1]
            for fam in resolved_families:
                compiler_family = _resolve_compiler_family(fam)
                direct = by_name_family.get((name, fam)) or by_name_family.get(
                    (name, compiler_family)
                )
                if direct:
                    for idx, art in enumerate(direct, start=1):
                        key = f"{name}@v{idx}:{fam}"
                        entries[key] = {
                            "sha256": _live_artifact_sha256(registry, art),
                            "token_estimate": int(art["estimated_tokens"]),
                        }
                else:
                    spec = IntentSpec(
                        name=name,
                        role=latest["system_prompt"],
                        task=latest["user_prompt"],
                    )
                    compiled = compile_prompt(spec, family=compiler_family)
                    key = f"{name}@v1:{fam}"
                    entries[key] = {
                        "sha256": compiled.sha256,
                        "token_estimate": int(compiled.estimated_tokens),
                    }

    lockfile: dict[str, Any] = {
        "lock_version": LOCK_VERSION,
        "entries": dict(sorted(entries.items())),
    }
    if resolved_families is not None:
        lockfile["families"] = resolved_families
    return lockfile


def verify_lockfile(
    registry: PromptRegistry,
    lockfile: dict[str, Any],
) -> dict[str, Any]:
    """Compare live compiled outputs in ``registry`` against pinned ``lockfile`` hashes."""
    if not isinstance(lockfile, dict):
        raise ValueError("Lockfile must be a JSON object")
    if str(lockfile.get("lock_version")) != LOCK_VERSION:
        raise ValueError(
            f"Unsupported lock_version {lockfile.get('lock_version')!r}; expected {LOCK_VERSION!r}"
        )
    pinned_entries = lockfile.get("entries")
    if not isinstance(pinned_entries, dict):
        raise ValueError("Lockfile 'entries' must be a JSON object")

    families = lockfile.get("families")
    if families is not None and not isinstance(families, list):
        raise ValueError("Lockfile 'families' must be a list when present")

    live = generate_lockfile(registry, families=families)
    live_entries: dict[str, dict[str, Any]] = live["entries"]

    drifted: list[dict[str, Any]] = []
    missing: list[str] = []
    added: list[str] = []

    for key in sorted(pinned_entries.keys()):
        if key not in live_entries:
            missing.append(key)
            continue
        expected_sha = pinned_entries[key].get("sha256")
        actual_sha = live_entries[key].get("sha256")
        if expected_sha != actual_sha:
            drifted.append(
                {
                    "key": key,
                    "expected_sha256": expected_sha,
                    "actual_sha256": actual_sha,
                    "expected_token_estimate": pinned_entries[key].get("token_estimate"),
                    "actual_token_estimate": live_entries[key].get("token_estimate"),
                }
            )

    for key in sorted(live_entries.keys()):
        if key not in pinned_entries:
            added.append(key)

    passed = not drifted and not missing and not added
    return {
        "passed": passed,
        "drifted": drifted,
        "missing": missing,
        "added": added,
    }
