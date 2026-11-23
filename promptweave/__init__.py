"""PromptWeave — deterministic multi-family prompt compiler with SHA-256 fingerprinting."""

from promptweave.adapters import SUPPORTED_FAMILIES
from promptweave.compiler import CompiledPrompt, compile_prompt, estimate_tokens
from promptweave.fingerprint import compute_sha256, format_prompt_id
from promptweave.spec import ContextBlock, Example, IntentSpec

__version__ = "0.1.0"

__all__ = [
    "CompiledPrompt",
    "ContextBlock",
    "Example",
    "IntentSpec",
    "SUPPORTED_FAMILIES",
    "__version__",
    "compile_prompt",
    "compute_sha256",
    "estimate_tokens",
    "format_prompt_id",
]
