"""Jinja2-based template engine supporting local filesystem and S3 storage."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from jinja2 import BaseLoader, Environment, FileSystemLoader, TemplateNotFound

_SUPPORTED_MODELS = {"claude", "gpt4", "gemini"}


class _S3Loader(BaseLoader):
    """Lazy-loading Jinja2 loader that fetches templates from S3 with in-process caching."""

    def __init__(self, bucket: str, prefix: str = "templates/") -> None:
        self.bucket = bucket
        self.prefix = prefix
        self._cache: dict[str, str] = {}

    def get_source(self, environment: Environment, template: str) -> tuple[str, str, Any]:
        key = f"{self.prefix}{template}"
        if key not in self._cache:
            import boto3  # imported lazily so tests without boto3 credentials still work
            s3 = boto3.client("s3")
            obj = s3.get_object(Bucket=self.bucket, Key=key)
            self._cache[key] = obj["Body"].read().decode("utf-8")
        source = self._cache[key]
        return source, key, lambda: True

    def list_templates(self) -> list[str]:
        return [f"{m}.j2" for m in _SUPPORTED_MODELS]


def _build_env() -> Environment:
    storage = os.getenv("TEMPLATE_STORAGE", "local")
    if storage == "s3":
        bucket = os.getenv("TEMPLATE_BUCKET", "")
        if not bucket:
            raise RuntimeError("TEMPLATE_BUCKET must be set when TEMPLATE_STORAGE=s3")
        loader: BaseLoader = _S3Loader(bucket)
    else:
        template_dir = Path(__file__).parent.parent / "templates"
        loader = FileSystemLoader(str(template_dir))

    return Environment(
        loader=loader,
        autoescape=False,
        keep_trailing_newline=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )


class TemplateEngine:
    """Renders model-specific Jinja2 templates from an intent dict."""

    def __init__(self) -> None:
        self._env = _build_env()

    def render(self, model: str, intent: dict[str, Any]) -> str:
        """
        Render the prompt template for `model` using `intent` fields.
        Raises TemplateNotFound if the model has no registered template.
        """
        if model not in _SUPPORTED_MODELS:
            raise ValueError(f"Unsupported model '{model}'. Supported: {sorted(_SUPPORTED_MODELS)}")
        template = self._env.get_template(f"{model}.j2")
        return template.render(**intent).strip()

    def reload(self) -> None:
        """Force re-initialise the environment (clears S3 cache)."""
        self._env = _build_env()
