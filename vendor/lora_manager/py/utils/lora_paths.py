"""LoRA path resolution shared by the manager nodes.

ComfyUI exposes model names with their file extensions, while older LoRA
Manager widgets may store extensionless names.  Resolve both forms through
ComfyUI's model search paths instead of depending on the asynchronous cache.
"""

from __future__ import annotations

import os
from typing import Optional

import folder_paths  # type: ignore


LORA_FILE_EXTENSIONS = (
    ".safetensors",
    ".sft",
    ".ckpt",
    ".pt",
    ".pt2",
    ".bin",
    ".pth",
    ".pkl",
)


def _candidate_names(lora_name: object) -> list[str]:
    if not isinstance(lora_name, (str, os.PathLike)):
        return []

    normalized = os.fspath(lora_name).strip().replace("\\", "/")
    if not normalized:
        return []

    candidates = [normalized]
    if not normalized.lower().endswith(LORA_FILE_EXTENSIONS):
        candidates.extend(normalized + extension for extension in LORA_FILE_EXTENSIONS)
    return candidates


def resolve_lora_path(lora_name: object) -> Optional[str]:
    """Resolve a LoRA name or path to an existing file.

    The cache can be empty or stale while ComfyUI is starting, and it can lag
    behind a newly trained LoRA.  ``folder_paths`` is the authoritative model
    registry for loading, so it is always consulted before giving up.
    """

    get_full_path = getattr(folder_paths, "get_full_path", None)
    for candidate in _candidate_names(lora_name):
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)

        if get_full_path is None:
            continue
        try:
            resolved = get_full_path("loras", candidate)
        except (AttributeError, KeyError, OSError, TypeError, ValueError):
            continue
        if resolved and os.path.isfile(resolved):
            return os.path.abspath(resolved)

    return None
