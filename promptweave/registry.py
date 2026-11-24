"""SQLite WAL prompt artifact registry conforming to prompt-artifact-v1."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from promptweave.compiler import CompiledPrompt
from promptweave.fingerprint import compute_sha256, format_prompt_id

PROMPT_ARTIFACT_SCHEMA = "prompt-artifact-v1"


def _extract_name_from_prompt_id(prompt_id: str) -> str:
    prefix = "prompt:"
    marker = "@sha256:"
    if prompt_id.startswith(prefix) and marker in prompt_id:
        extracted = prompt_id[len(prefix) : prompt_id.index(marker)]
        if extracted:
            return extracted
    return "default"


def _artifact_integrity_hash(
    *,
    schema: str,
    prompt_id: str,
    name: str,
    family: str,
    sha256: str,
    estimated_tokens: int,
    system_prompt: str,
    user_prompt: str,
) -> str:
    return compute_sha256(
        {
            "schema": schema,
            "prompt_id": prompt_id,
            "name": name,
            "family": family,
            "sha256": sha256,
            "estimated_tokens": estimated_tokens,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        }
    )


def _row_to_artifact(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "schema": row["schema"],
        "prompt_id": row["prompt_id"],
        "name": row["name"],
        "family": row["family"],
        "sha256": row["sha256"],
        "estimated_tokens": int(row["estimated_tokens"]),
        "system_prompt": row["system_prompt"],
        "user_prompt": row["user_prompt"],
        "created_at": row["created_at"],
    }


class PromptRegistry:
    """Durable SQLite WAL registry storing compiled prompt-artifact-v1 records."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        path_str = str(db_path)
        if path_str != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path_str, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS prompt_artifacts (
                    prompt_id TEXT PRIMARY KEY,
                    schema TEXT NOT NULL,
                    name TEXT NOT NULL,
                    family TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    estimated_tokens INTEGER NOT NULL,
                    system_prompt TEXT NOT NULL,
                    user_prompt TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    messages_json TEXT NOT NULL,
                    rendered TEXT NOT NULL,
                    tools_json TEXT NOT NULL,
                    dropped_context_blocks_json TEXT NOT NULL,
                    artifact_sha256 TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_prompt_artifacts_name "
                "ON prompt_artifacts (name, created_at)"
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> PromptRegistry:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def register(
        self,
        compiled: CompiledPrompt,
        *,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Store a compiled prompt artifact and return its prompt-artifact-v1 dict."""
        resolved_name = name or compiled.name or _extract_name_from_prompt_id(compiled.prompt_id)
        created_at = datetime.now(timezone.utc).isoformat()
        artifact_digest = _artifact_integrity_hash(
            schema=PROMPT_ARTIFACT_SCHEMA,
            prompt_id=compiled.prompt_id,
            name=resolved_name,
            family=compiled.family,
            sha256=compiled.sha256,
            estimated_tokens=compiled.estimated_tokens,
            system_prompt=compiled.system,
            user_prompt=compiled.user,
        )

        with self._lock:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO prompt_artifacts (
                    prompt_id,
                    schema,
                    name,
                    family,
                    sha256,
                    estimated_tokens,
                    system_prompt,
                    user_prompt,
                    created_at,
                    messages_json,
                    rendered,
                    tools_json,
                    dropped_context_blocks_json,
                    artifact_sha256
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    compiled.prompt_id,
                    PROMPT_ARTIFACT_SCHEMA,
                    resolved_name,
                    compiled.family,
                    compiled.sha256,
                    int(compiled.estimated_tokens),
                    compiled.system,
                    compiled.user,
                    created_at,
                    json.dumps(compiled.messages, sort_keys=True),
                    compiled.rendered,
                    json.dumps(compiled.tools, sort_keys=True),
                    json.dumps(compiled.dropped_context_blocks),
                    artifact_digest,
                ),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM prompt_artifacts WHERE prompt_id = ?",
                (compiled.prompt_id,),
            ).fetchone()
        assert row is not None
        return _row_to_artifact(row)

    def get(self, prompt_id: str) -> dict[str, Any] | None:
        """Retrieve a stored prompt-artifact-v1 record by prompt_id."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM prompt_artifacts WHERE prompt_id = ?",
                (prompt_id,),
            ).fetchone()
        if row is None:
            return None
        return _row_to_artifact(row)

    def list_versions(self, name: str | None = None) -> list[dict[str, Any]]:
        """List stored prompt-artifact-v1 records, optionally filtered by prompt name."""
        with self._lock:
            if name is None:
                rows = self._conn.execute(
                    "SELECT * FROM prompt_artifacts ORDER BY created_at DESC, rowid DESC"
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM prompt_artifacts WHERE name = ? "
                    "ORDER BY created_at DESC, rowid DESC",
                    (name,),
                ).fetchall()
        return [_row_to_artifact(row) for row in rows]

    def verify(self, prompt_id: str) -> bool:
        """Recompute SHA-256 integrity over a stored artifact to detect tampering."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM prompt_artifacts WHERE prompt_id = ?",
                (prompt_id,),
            ).fetchone()
        if row is None:
            return False

        if row["schema"] != PROMPT_ARTIFACT_SCHEMA:
            return False

        expected_prompt_id = format_prompt_id(row["name"], row["sha256"])
        if row["prompt_id"] != expected_prompt_id:
            return False

        try:
            messages = json.loads(row["messages_json"])
            tools = json.loads(row["tools_json"])
            dropped = json.loads(row["dropped_context_blocks_json"])
        except (TypeError, json.JSONDecodeError):
            return False

        recomputed_sha256 = compute_sha256(
            {
                "family": row["family"],
                "name": row["name"],
                "messages": messages,
                "rendered": row["rendered"],
                "tools": tools,
                "dropped_context_blocks": dropped,
            }
        )
        if recomputed_sha256 != row["sha256"]:
            return False

        recomputed_artifact_sha256 = _artifact_integrity_hash(
            schema=row["schema"],
            prompt_id=row["prompt_id"],
            name=row["name"],
            family=row["family"],
            sha256=row["sha256"],
            estimated_tokens=int(row["estimated_tokens"]),
            system_prompt=row["system_prompt"],
            user_prompt=row["user_prompt"],
        )
        return recomputed_artifact_sha256 == row["artifact_sha256"]
