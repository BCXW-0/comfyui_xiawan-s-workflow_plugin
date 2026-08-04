from __future__ import annotations

import importlib
import sys
import types


def test_compare_returns_standard_and_split_image_payload(monkeypatch):
    preview_base = type("PreviewImage", (), {})
    monkeypatch.setitem(sys.modules, "nodes", types.SimpleNamespace(PreviewImage=preview_base))

    module = importlib.import_module(
        "vendor.danbooru_gallery.py.simple_image_compare.simple_image_compare"
    )
    compare = module.SimpleImageCompare()
    saved = {
        "image_a": [{"filename": "a.png", "subfolder": "", "type": "temp"}],
        "image_b": [{"filename": "b.png", "subfolder": "", "type": "temp"}],
    }

    def save_images(images, *_args):
        return {"ui": {"images": saved[images]}}

    compare.save_images = save_images
    payload = compare.compare_images(
        enabled=True,
        image_a="image_a",
        image_b="image_b",
    )

    assert payload["ui"]["a_images"] == saved["image_a"]
    assert payload["ui"]["b_images"] == saved["image_b"]
    assert payload["ui"]["images"] == saved["image_a"] + saved["image_b"]

    partial = compare.compare_images(enabled=True, image_a="image_a")
    assert partial["ui"]["images"] == saved["image_a"]
    assert partial["ui"]["b_images"] == []


def test_base_image_preview_is_an_output_node(monkeypatch):
    preview_base = type("PreviewImage", (), {})
    monkeypatch.setitem(sys.modules, "nodes", types.SimpleNamespace(PreviewImage=preview_base))

    vendor_nodes = importlib.import_module("xiawan_vendor_nodes")
    assert vendor_nodes.XiawanBaseImagePreview.OUTPUT_NODE is True
    assert vendor_nodes.XiawanBaseImagePreview.FUNCTION == "cleanup"


def test_base_image_preview_publishes_early_images(monkeypatch):
    class PreviewImage:
        def save_images(self, _images, **_kwargs):
            return {"ui": {"images": [{"filename": "base.png"}]}}

    monkeypatch.setitem(sys.modules, "nodes", types.SimpleNamespace(PreviewImage=PreviewImage))
    vendor_nodes = importlib.import_module("xiawan_vendor_nodes")
    monkeypatch.setattr(
        vendor_nodes.XiawanVRAMDebug,
        "cleanup",
        lambda self, *_args, **kwargs: {
            "ui": {"text": ["ok"]},
            "result": (None, kwargs.get("image_pass"), None, 0, 0),
        },
    )

    preview = vendor_nodes.XiawanBaseImagePreview()
    payload = preview.cleanup(False, False, False, image_pass=[object()])

    assert payload["ui"]["xiawan_base_images"] == [{"filename": "base.png"}]
