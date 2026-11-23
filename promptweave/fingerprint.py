"""Deterministic SHA-256 content fingerprinting for compiled prompts."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def sanitize_prompt_name(name: str) -> str:
    cleaned = _SAFE_NAME_RE.sub("-", name.strip()).strip("-")
    return cleaned or "default"


def compute_sha256(payload: dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 hex digest over canonical JSON."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def format_prompt_id(name: str, digest: str) -> str:
    """Format a GatewayWeave-compatible pinned prompt identifier."""
    return f"prompt:{sanitize_prompt_name(name)}@sha256:{digest}"
