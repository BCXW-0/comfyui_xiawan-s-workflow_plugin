from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType


def load_resolver(monkeypatch, root: Path):
    folder_paths = ModuleType("folder_paths")
    lora_root = root / "loras"

    def get_full_path(folder_name: str, filename: str):
        assert folder_name == "loras"
        candidate = lora_root / filename.replace("/", "\\")
        return str(candidate) if candidate.is_file() else None

    folder_paths.get_full_path = get_full_path
    monkeypatch.setitem(sys.modules, "folder_paths", folder_paths)
    module_name = "vendor.lora_manager.py.utils.lora_paths"
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def test_resolves_extensionless_name_from_comfyui_paths(tmp_path, monkeypatch):
    lora_file = tmp_path / "loras" / "xiawan_style_star_eye_epoch20.safetensors"
    lora_file.parent.mkdir()
    lora_file.write_bytes(b"placeholder")
    resolver = load_resolver(monkeypatch, tmp_path)

    assert resolver.resolve_lora_path("xiawan_style_star_eye_epoch20") == str(lora_file.resolve())
    assert resolver.resolve_lora_path("xiawan_style_star_eye_epoch20.safetensors") == str(lora_file.resolve())


def test_resolves_nested_lora_name_and_direct_path(tmp_path, monkeypatch):
    lora_file = tmp_path / "loras" / "xiawan" / "style.safetensors"
    lora_file.parent.mkdir(parents=True)
    lora_file.write_bytes(b"placeholder")
    resolver = load_resolver(monkeypatch, tmp_path)

    assert resolver.resolve_lora_path("xiawan/style") == str(lora_file.resolve())
    assert resolver.resolve_lora_path(str(lora_file)) == str(lora_file.resolve())


def test_returns_none_for_missing_lora(tmp_path, monkeypatch):
    resolver = load_resolver(monkeypatch, tmp_path)

    assert resolver.resolve_lora_path("missing_lora") is None
