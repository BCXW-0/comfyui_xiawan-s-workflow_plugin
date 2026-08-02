"""Selective compatibility registration for Xiawan's vendored node support."""

from __future__ import annotations

import gc
import importlib
import json
import logging
import random
from pathlib import Path


def _module(relative_name: str):
    return importlib.import_module(relative_name, package=__package__)


def _mapped(relative_name: str, keys: tuple[str, ...]):
    module = _module(relative_name)
    classes = module.NODE_CLASS_MAPPINGS
    displays = getattr(module, "NODE_DISPLAY_NAME_MAPPINGS", {})
    missing = [key for key in keys if key not in classes]
    if missing:
        raise KeyError(f"{relative_name} does not provide: {', '.join(missing)}")
    return ({key: classes[key] for key in keys}, {key: displays.get(key, key) for key in keys})


class XiawanImageIndexSwitch:
    @classmethod
    def INPUT_TYPES(cls):
        optional = {f"image{index}": ("IMAGE", {"lazy": True}) for index in range(20)}
        return {"required": {"index": ("INT", {"default": 0, "min": 0, "max": 9, "step": 1})}, "optional": optional}

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "select"
    CATEGORY = "Xiawan/Compatibility"

    @classmethod
    def check_lazy_status(cls, index, **kwargs):
        key = f"image{index}"
        return [key] if kwargs.get(key) is None else []

    def select(self, index, **kwargs):
        return (kwargs[f"image{index}"],)


class XiawanConditioningIndexSwitch:
    @classmethod
    def INPUT_TYPES(cls):
        optional = {f"cond{index}": ("CONDITIONING", {"lazy": True}) for index in range(20)}
        return {"required": {"index": ("INT", {"default": 0, "min": 0, "max": 9, "step": 1})}, "optional": optional}

    RETURN_TYPES = ("CONDITIONING",)
    RETURN_NAMES = ("conditioning",)
    FUNCTION = "select"
    CATEGORY = "Xiawan/Compatibility"

    @classmethod
    def check_lazy_status(cls, index, **kwargs):
        key = f"cond{index}"
        return [key] if kwargs.get(key) is None else []

    def select(self, index, **kwargs):
        return (kwargs[f"cond{index}"],)


class XiawanJoinStrings:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"delimiter": ("STRING", {"default": " ", "multiline": False})},
            "optional": {
                "string1": ("STRING", {"default": "", "forceInput": True}),
                "string2": ("STRING", {"default": "", "forceInput": True}),
            },
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "join"
    CATEGORY = "Xiawan/Compatibility"

    def join(self, delimiter, string1="", string2=""):
        return (f"{string1}{delimiter}{string2}",)


class XiawanVRAMDebug:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "empty_cache": ("BOOLEAN", {"default": True}),
                "gc_collect": ("BOOLEAN", {"default": True}),
                "unload_all_models": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "any_input": ("*",),
                "image_pass": ("IMAGE",),
                "model_pass": ("MODEL",),
            },
        }

    RETURN_TYPES = ("*", "IMAGE", "MODEL", "INT", "INT")
    RETURN_NAMES = ("any_output", "image_pass", "model_pass", "freemem_before", "freemem_after")
    FUNCTION = "cleanup"
    CATEGORY = "Xiawan/Performance"

    def cleanup(self, gc_collect, empty_cache, unload_all_models, image_pass=None, model_pass=None, any_input=None):
        from comfy import model_management

        before = int(model_management.get_free_memory())
        if empty_cache:
            model_management.soft_empty_cache()
        if unload_all_models:
            model_management.unload_all_models()
        if gc_collect:
            gc.collect()
        after = int(model_management.get_free_memory())
        return {"ui": {"text": [f"{before:,}x{after:,}"]}, "result": (any_input, image_pass, model_pass, before, after)}


class XiawanWeiLinPromptUIWithoutLora:
    @classmethod
    def IS_CHANGED(cls, auto_random, **kwargs):
        return float("nan") if auto_random else False

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "positive": ("STRING", {"multiline": True, "default": "", "placeholder": "输入提示词"}),
                "auto_random": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "temp_str": ("STRING", {"multiline": True, "default": "", "placeholder": "temp prompt words"}),
                "random_template": ("STRING", {"multiline": True, "default": "", "placeholder": "random template path name"}),
                "opt_text": ("*", {"default": ""}),
                "opt_clip": ("CLIP",),
            },
            "hidden": {"unique_id": "UNIQUE_ID", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    RETURN_TYPES = ("STRING", "CONDITIONING", "CLIP")
    RETURN_NAMES = ("STRING", "CONDITIONING", "CLIP")
    FUNCTION = "encode"
    OUTPUT_NODE = True
    CATEGORY = "Xiawan/Prompt"

    @staticmethod
    def _random_from_template(template: str) -> str:
        if template:
            try:
                from .vendor.weilin_tools.app.server.prompt_api.random_tag_template import (
                    go_radom_template,
                )

                result = go_radom_template(template)
                if isinstance(result, dict):
                    generated = str(result.get("random_tags", "")).strip()
                    if generated:
                        return generated
            except (ImportError, OSError, ValueError, KeyError):
                pass

        path = Path(template)
        if not template or not path.is_file():
            return ""
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ""
        if isinstance(payload, dict):
            payload = payload.get("random_tags", payload.get("tags", []))
            if isinstance(payload, str):
                return payload.strip()
        if isinstance(payload, list):
            values = [str(value).strip() for value in payload if str(value).strip()]
            return random.choice(values) if values else ""
        return ""

    def encode(self, positive="", auto_random=False, temp_str="", random_template="", opt_text="", opt_clip=None, unique_id=None, extra_pnginfo=None):
        del temp_str, unique_id, extra_pnginfo
        source = str(positive or "")
        try:
            decoded = json.loads(source)
            if isinstance(decoded, dict):
                source = str(decoded.get("prompt", source))
        except json.JSONDecodeError:
            pass
        prefix = "" if opt_text is None else str(opt_text).strip()
        if auto_random:
            source = self._random_from_template(random_template) or source
        text = ", ".join(part for part in (prefix, source) if part)
        conditioning = None
        if opt_clip is not None:
            tokens = opt_clip.tokenize(text)
            conditioning = opt_clip.encode_from_tokens_scheduled(tokens)
        result = (text, conditioning, opt_clip)
        return {"ui": {"positive": [source]}, "result": result} if auto_random else result


def load_vendor_nodes():
    """Return only the third-party node types used by Xiawan's workflow."""

    classes = {
        "easy imageIndexSwitch": XiawanImageIndexSwitch,
        "easy conditioningIndexSwitch": XiawanConditioningIndexSwitch,
        "JoinStrings": XiawanJoinStrings,
        "VRAM_Debug": XiawanVRAMDebug,
        "WeiLinPromptUIWithoutLora": XiawanWeiLinPromptUIWithoutLora,
    }
    displays = {
        "easy imageIndexSwitch": "Xiawan Image Index Switch",
        "easy conditioningIndexSwitch": "Xiawan Conditioning Index Switch",
        "JoinStrings": "Xiawan Join Strings",
        "VRAM_Debug": "Xiawan VRAM Debug",
        "WeiLinPromptUIWithoutLora": "WeiLin 提示词编辑器",
    }

    util = _module(".vendor.mira.Util")
    tagger = _module(".vendor.mira.Tagger")
    classes.update({"CheckpointLoaderSimpleMira": util.CheckpointLoaderSimple, "cl_tagger_mira": tagger.cl_tagger})
    displays.update({"CheckpointLoaderSimpleMira": "Checkpoint Loader with Name", "cl_tagger_mira": "Mira CL Tagger"})

    vendor_maps = (
        (".vendor.danbooru_gallery.py.danbooru_gallery", ("DanbooruGalleryNode",)),
        (".vendor.danbooru_gallery.py.group_ignore_manager", ("GroupIgnoreManager",)),
        (".vendor.danbooru_gallery.py.group_is_enabled", ("GroupIsEnabled",)),
        (".vendor.danbooru_gallery.py.prompt_cleaning_maid", ("PromptCleaningMaid",)),
        (".vendor.danbooru_gallery.py.prompt_selector", ("PromptSelector",)),
        (".vendor.danbooru_gallery.py.resolution_master_simplify", ("ResolutionMasterSimplify",)),
        (".vendor.danbooru_gallery.py.save_image_plus", ("SaveImagePlus",)),
        (".vendor.danbooru_gallery.py.simple_image_compare", ("SimpleImageCompare",)),
        (".vendor.controlnet_aux.node_wrappers.depth_anything_v2", ("DepthAnythingV2Preprocessor",)),
        (".vendor.controlnet_aux.node_wrappers.lineart", ("LineArtPreprocessor",)),
        (".vendor.controlnet_aux.node_wrappers.openpose", ("OpenposePreprocessor",)),
        (".vendor.controlnet_aux.node_wrappers.scribble", ("ScribblePreprocessor",)),
        (".vendor.impact_subpack.modules.subpack_nodes", ("UltralyticsDetectorProvider",)),
        (".vendor.ipadapter_plus.IPAdapterPlus", ("IPAdapterAdvanced", "IPAdapterUnifiedLoader", "PrepImageForClipVision")),
    )
    for module_name, keys in vendor_maps:
        mapped_classes, mapped_displays = _mapped(module_name, keys)
        classes.update(mapped_classes)
        displays.update(mapped_displays)

    _module(".vendor.impact_pack")
    impact = _module(".vendor.impact_pack.modules.impact.impact_pack")
    classes.update(
        {
            "FaceDetailer": impact.FaceDetailer,
            "IterativeImageUpscale": impact.IterativeImageUpscale,
            "PixelKSampleUpscalerProvider": impact.PixelKSampleUpscalerProvider,
            "SAMLoader": impact.SAMLoader,
        }
    )
    displays.update(
        {
            "FaceDetailer": "FaceDetailer",
            "IterativeImageUpscale": "Iterative Image Upscale",
            "PixelKSampleUpscalerProvider": "Pixel KSample Upscaler Provider",
            "SAMLoader": "SAM Loader",
        }
    )

    lora_loader = _module(".vendor.lora_manager.py.nodes.lora_loader")
    trigger_words = _module(".vendor.lora_manager.py.nodes.trigger_word_toggle")
    classes.update(
        {
            "Lora Loader (LoraManager)": lora_loader.LoraLoaderLM,
            "TriggerWord Toggle (LoraManager)": trigger_words.TriggerWordToggleLM,
        }
    )
    displays.update(
        {
            "Lora Loader (LoraManager)": "LoRA",
            "TriggerWord Toggle (LoraManager)": "LoRA 触发词",
        }
    )
    return classes, displays
