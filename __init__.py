"""Xiawan Workflow Plugin.

Custom nodes for Xiawan's ComfyUI T2I/I2I workflow.
"""

import json
import os
import random
import re

import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo

import folder_paths

WEB_DIRECTORY = "./web"

try:
    import comfy.samplers
    import comfy.sd
    import comfy.utils
    import torch
except Exception:
    comfy = None
    torch = None


SAMPLERS = [
    "euler",
    "euler_cfg_pp",
    "euler_ancestral",
    "euler_ancestral_cfg_pp",
    "heun",
    "heunpp2",
    "exp_heun_2_x0",
    "exp_heun_2_x0_sde",
    "dpm_2",
    "dpm_2_ancestral",
    "lms",
    "dpm_fast",
    "dpm_adaptive",
    "dpmpp_2s_ancestral",
    "dpmpp_2s_ancestral_cfg_pp",
    "dpmpp_sde",
    "dpmpp_sde_gpu",
    "dpmpp_2m",
    "dpmpp_2m_cfg_pp",
    "dpmpp_2m_sde",
    "dpmpp_2m_sde_gpu",
    "dpmpp_2m_sde_heun",
    "dpmpp_2m_sde_heun_gpu",
    "dpmpp_3m_sde",
    "dpmpp_3m_sde_gpu",
    "ddpm",
    "lcm",
    "ipndm",
    "ipndm_v",
    "deis",
    "res_multistep",
    "res_multistep_cfg_pp",
    "res_multistep_ancestral",
    "res_multistep_ancestral_cfg_pp",
    "gradient_estimation",
    "gradient_estimation_cfg_pp",
    "er_sde",
    "seeds_2",
    "seeds_3",
    "sa_solver",
    "sa_solver_pece",
    "ddim",
    "uni_pc",
    "uni_pc_bh2",
]

IMPACT_SCHEDULERS = [
    "AYS SDXL",
    "AYS SD1",
    "AYS SVD",
    "GITS[coeff=1.2]",
    "LTXV[default]",
    "OSS FLUX",
    "OSS Wan",
    "OSS Chroma",
]

SCHEDULERS = [
    "simple",
    "sgm_uniform",
    "karras",
    "exponential",
    "ddim_uniform",
    "beta",
    "normal",
    "linear_quadratic",
    "kl_optimal",
]

TAGGER_MODEL_NAMES = ["cl_tagger/cl_tagger_1_02.onnx"]
TAGGER_SESSION_METHODS = ["CPU", "CPU Release", "GPU", "GPU Release"]

if comfy is not None:
    SAMPLERS = list(comfy.samplers.KSampler.SAMPLERS)
    SCHEDULERS = list(comfy.samplers.KSampler.SCHEDULERS)

LATENT_UPSCALE_METHODS = ["nearest-exact", "bilinear", "area", "bicubic", "bislerp"]
PIXEL_UPSCALE_METHODS = ["nearest-exact", "bilinear", "lanczos", "area"]
IMAGE_UPSCALE_METHODS = ["nearest-exact", "bilinear", "area", "bicubic", "lanczos"]
IMAGE_CROP_METHODS = ["disabled", "center"]
ITERATIVE_STEP_MODES = ["simple", "geometric"]
SAM_DETECTION_HINTS = [
    "center-1",
    "horizontal-2",
    "vertical-2",
    "rect-4",
    "diamond-4",
    "mask-area",
    "mask-points",
    "mask-point-bbox",
    "none",
]
SAM_NEGATIVE_HINTS = ["False", "Small", "Outter"]
SEED_MODES = ["fixed", "random", "last"]
GLOBAL_SEED_MODES = ["fixed", "random", "increase", "decrease", "last"]
BASE_IMAGE_MODES = ["自采样", "图生图直通", "图生图重采样"]
MAX_SEED = 0xffffffffffffffff

RESOLUTION_PRESETS = [
    "Custom",
    "832 x 1216 Portrait",
    "1024 x 1024 Square",
    "1216 x 832 Landscape",
    "1024 x 1536 Portrait",
    "1536 x 1024 Landscape",
]

RESOLUTION_MAP = {
    "832 x 1216 Portrait": (832, 1216),
    "1024 x 1024 Square": (1024, 1024),
    "1216 x 832 Landscape": (1216, 832),
    "1024 x 1536 Portrait": (1024, 1536),
    "1536 x 1024 Landscape": (1536, 1024),
}


def _value(kwargs, *names, default=None):
    for name in names:
        if name in kwargs:
            return kwargs[name]
    return default


def _coerce_bool(value):
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off", "none"}
    return bool(value)


_MISSING = object()


def _prompt_separator(delimiter=", "):
    separator = str(delimiter if delimiter is not None else ", ")
    return separator if separator else ", "


def _prompt_key(text):
    key = str(text or "").strip().lower().replace("_", " ")
    return re.sub(r"\s+", " ", key)


def _split_prompt_text(text):
    if text is None:
        return []

    items = []
    current = []
    depth = 0
    pairs = {"(": ")", "[": "]", "{": "}", "<": ">"}
    closing = set(pairs.values())
    separators = {",", "，", ";", "；", "、", "\n", "\r", "\t"}

    for char in str(text):
        if char in pairs:
            depth += 1
        elif char in closing and depth > 0:
            depth -= 1

        if depth == 0 and char in separators:
            token = "".join(current).strip()
            if token:
                items.append(token)
            current = []
        else:
            current.append(char)

    token = "".join(current).strip()
    if token:
        items.append(token)
    return items


def _flatten_prompt_tokens(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        tokens = []
        for item in value:
            tokens.extend(_flatten_prompt_tokens(item))
        return tokens

    tokens = []
    for token in _split_prompt_text(value):
        cleaned = re.sub(r"\s+", " ", str(token)).strip(" ,，;；、|")
        cleaned = cleaned.strip()
        if cleaned:
            tokens.append(cleaned)
    return tokens


def _merge_prompt_texts(*values, delimiter=", "):
    separator = _prompt_separator(delimiter)
    seen = set()
    merged = []

    for value in values:
        for token in _flatten_prompt_tokens(value):
            key = _prompt_key(token)
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(token)

    return separator.join(merged)


def _coerce_seed(value, default=0):
    try:
        seed = int(value)
    except Exception:
        seed = int(default)
    return max(0, min(MAX_SEED, seed))


def _previous_seed(kwargs, default):
    """Read the last seed from the workflow widget instead of process state."""
    current = _value(kwargs, "current_seed", "当前Seed", default=None)
    if current is None or (isinstance(current, str) and not current.strip()):
        return _coerce_seed(default, default)
    return _coerce_seed(current, default)


def _resolve_seed(kwargs, namespace, default):
    fixed_seed = _coerce_seed(_value(kwargs, "种子值", "采样种子值", "种子", "采样种子", "seed", default=default), default)
    mode = _value(kwargs, "Seed模式", "seed_mode", default="fixed")
    previous_seed = _previous_seed(kwargs, fixed_seed)
    if mode == "random":
        seed = random.randint(0, MAX_SEED)
    elif mode == "last":
        seed = previous_seed
    else:
        seed = fixed_seed
    return seed


def _seed_is_changed(kwargs):
    if _value(kwargs, "Seed模式", "seed_mode", default="fixed") == "random":
        return random.random()
    return False




def _resolve_global_seed(kwargs):
    seed_value = _coerce_seed(_value(kwargs, "seed_value", "???", default=123456789), 123456789)
    operation = _value(kwargs, "operation", "??", default="fixed")
    last_seed = _previous_seed(kwargs, seed_value)
    if operation == "random":
        seed = random.randint(0, MAX_SEED)
    elif operation == "increase":
        seed = _coerce_seed(last_seed + 1, seed_value)
    elif operation == "decrease":
        seed = _coerce_seed(last_seed - 1, seed_value)
    elif operation == "last":
        seed = last_seed
    else:
        seed = seed_value
    return seed


def _update_global_seed_widget(seed, unique_id, extra_pnginfo):
    info = extra_pnginfo[0] if isinstance(extra_pnginfo, list) and extra_pnginfo else extra_pnginfo
    uid = unique_id[0] if isinstance(unique_id, list) and unique_id else unique_id
    if not isinstance(info, dict) or "workflow" not in info:
        return
    workflow = info["workflow"]
    if not isinstance(workflow, dict):
        return
    node = next((x for x in workflow.get("nodes", []) if str(x.get("id")) == str(uid)), None)
    if node is None:
        return
    values = list(node.get("widgets_values") or [])
    while len(values) < 3:
        values.append("")
    values[2] = str(seed)
    node["widgets_values"] = values


def _update_global_seed_prompt(seed, unique_id, prompt):
    prompt_obj = prompt[0] if isinstance(prompt, list) and prompt else prompt
    uid = unique_id[0] if isinstance(unique_id, list) and unique_id else unique_id
    if not isinstance(prompt_obj, dict):
        return
    node = prompt_obj.get(str(uid))
    if not isinstance(node, dict):
        return
    inputs = node.setdefault("inputs", {})
    if isinstance(inputs, dict):
        inputs["current_seed"] = str(seed)


def _global_seed_is_changed(kwargs):
    if _value(kwargs, "operation", "??", default="fixed") in ("random", "increase", "decrease"):
        return random.random()
    return False


class XiawanGlobalSeedManager:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "seed_value": ("INT", {"default": 123456789, "min": 0, "max": MAX_SEED}),
                "operation": (GLOBAL_SEED_MODES, {"default": "fixed"}),
            },
            "optional": {
                "current_seed": ("STRING", {"default": ""}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("seed",)
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, **kwargs):
        seed = _resolve_global_seed(kwargs)
        _update_global_seed_prompt(seed, kwargs.get("unique_id"), kwargs.get("prompt"))
        _update_global_seed_widget(seed, kwargs.get("unique_id"), kwargs.get("extra_pnginfo"))
        return {"ui": {"current_seed": [str(seed)]}, "result": (seed,)}

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return _global_seed_is_changed(kwargs)


def _upscale_models():
    try:
        import folder_paths

        models = folder_paths.get_filename_list("upscale_models")
        if models:
            return models
    except Exception:
        pass
    return ["4xUltrasharp_4xUltrasharpV10.pt"]


def _bbox_models(default="bbox/face_yolov8m.pt"):
    def with_bbox_prefix(model_name):
        model_name = str(model_name).replace("\\", "/")
        if model_name.startswith(("bbox/", "segm/")):
            return model_name
        return f"bbox/{model_name}"

    try:
        import folder_paths

        models = folder_paths.get_filename_list("ultralytics_bbox")
        if models:
            models = [with_bbox_prefix(model) for model in models]
            default = with_bbox_prefix(default)
            if default not in models:
                models.insert(0, default)
            return models
    except Exception:
        pass
    models = [
        "bbox/face_yolov8m.pt",
        "bbox/full_eyes_detect_v1.pt",
        "bbox/PitEyeDetailer-v2-seg.pt",
        "bbox/hand_yolov8s.pt",
        "bbox/adetailerFootYolov8x_v20.pt",
        "bbox/nipples_yolov8s-seg.pt",
        "bbox/nipples_yolov8s-seg (1).pt",
        "bbox/PitHandDetailer-v2-Test-v9c.pt",
        "bbox/PitHandDetailer-v1b-seg.pt",
    ]
    if default not in models:
        models.insert(0, default)
    return models



class XiawanBaseParams:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "批次数量": ("INT", {"default": 1, "min": 1, "max": 64, "step": 1}),
                "步数": ("INT", {"default": 28, "min": 1, "max": 100, "step": 1}),
                "CFG": ("FLOAT", {"default": 5.5, "min": 0.0, "max": 30.0, "step": 0.1}),
                "主采样降噪": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "采样器": (SAMPLERS, {"default": "dpmpp_2m"}),
                "调度器": (SCHEDULERS, {"default": "karras"}),
                "启用 Refiner": ("BOOLEAN", {"default": False}),
                "Refiner 步数": ("INT", {"default": 12, "min": 1, "max": 80, "step": 1}),
                "Refiner 降噪": ("FLOAT", {"default": 0.22, "min": 0.0, "max": 1.0, "step": 0.01}),
                "底图模式": (BASE_IMAGE_MODES, {"default": BASE_IMAGE_MODES[0]}),
                "保存图像": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("INT", "INT", "INT", "INT", "FLOAT", "FLOAT", SAMPLERS, SCHEDULERS, "BOOLEAN", "INT", "FLOAT", "BOOLEAN", "BOOLEAN", "BOOLEAN", "BOOLEAN")
    RETURN_NAMES = ("width", "height", "batch_size", "steps", "cfg", "main_denoise", "sampler_name", "scheduler", "refiner_enabled", "refiner_steps", "refiner_denoise", "img2img_direct_enabled", "img2img_resample_enabled", "save_image", "img2img_caption_enabled")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, **kwargs):
        width = 832
        height = 1216
        batch_size = _value(kwargs, "批次数量", "batch_size", default=1)
        steps = _value(kwargs, "步数", "steps", default=28)
        cfg = _value(kwargs, "CFG", "cfg", default=5.5)
        main_denoise = _value(kwargs, "主采样降噪", "main_denoise", default=1.0)
        sampler_name = _value(kwargs, "采样器", "sampler_name", default="dpmpp_2m")
        scheduler = _value(kwargs, "调度器", "scheduler", default="karras")
        refiner_enabled = _value(kwargs, "启用 Refiner", "refiner_enabled", default=False)
        refiner_steps = _value(kwargs, "Refiner 步数", "refiner_steps", default=12)
        refiner_denoise = _value(kwargs, "Refiner 降噪", "refiner_denoise", default=0.25)
        base_image_mode = _value(kwargs, "底图模式", "base_image_mode", default=None)
        if base_image_mode is None:
            legacy_img2img = _value(kwargs, "img2img_enabled", "image_selector_enabled", default=False)
            base_image_mode = "图生图重采样" if legacy_img2img else BASE_IMAGE_MODES[0]
        img2img_direct_enabled = base_image_mode == "图生图直通"
        img2img_resample_enabled = base_image_mode == "图生图重采样"
        img2img_caption_enabled = img2img_direct_enabled or img2img_resample_enabled
        save_image = _value(kwargs, "保存图像", "save_image", default=True)
        return (width, height, batch_size, steps, cfg, main_denoise, sampler_name, scheduler, refiner_enabled, refiner_steps, refiner_denoise, img2img_direct_enabled, img2img_resample_enabled, save_image, img2img_caption_enabled)


class XiawanAnimaBaseParams:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "宽度": ("INT", {"default": 832, "min": 64, "max": 8192, "step": 8}),
                "高度": ("INT", {"default": 1216, "min": 64, "max": 8192, "step": 8}),
                "批次数量": ("INT", {"default": 1, "min": 1, "max": 64, "step": 1}),
                "步数": ("INT", {"default": 8, "min": 1, "max": 100, "step": 1}),
                "CFG": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 30.0, "step": 0.1}),
                "主采样降噪": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "采样器": (SAMPLERS, {"default": "euler"}),
                "调度器": (SCHEDULERS, {"default": "simple"}),
            },
        }

    RETURN_TYPES = ("INT", "INT", "INT", "INT", "FLOAT", "FLOAT", SAMPLERS, SCHEDULERS)
    RETURN_NAMES = ("width", "height", "batch_size", "steps", "cfg", "main_denoise", "sampler_name", "scheduler")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, **kwargs):
        width = _value(kwargs, "宽度", "width", default=1024)
        height = _value(kwargs, "高度", "height", default=1024)
        batch_size = _value(kwargs, "批次数量", "batch_size", default=1)
        steps = _value(kwargs, "步数", "steps", default=10)
        cfg = _value(kwargs, "CFG", "cfg", default=1.0)
        main_denoise = _value(kwargs, "主采样降噪", "main_denoise", default=1.0)
        sampler_name = _value(kwargs, "采样器", "sampler_name", default="euler")
        scheduler = _value(kwargs, "调度器", "scheduler", default="simple")
        return (width, height, batch_size, steps, cfg, main_denoise, sampler_name, scheduler)

class XiawanAnimaBranchIndex:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "sdxl_enabled": ("BOOLEAN", {"default": True, "forceInput": True}),
                "anima_enabled": ("BOOLEAN", {"default": False, "forceInput": True}),
            }
        }

    RETURN_TYPES = ("INT", "BOOLEAN", "BOOLEAN")
    RETURN_NAMES = ("index", "sdxl_active", "anima_active")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, sdxl_enabled=True, anima_enabled=False):
        anima_active = _coerce_bool(anima_enabled)
        sdxl_active = _coerce_bool(sdxl_enabled) and not anima_active
        index = 1 if anima_active else 0
        return (index, sdxl_active, anima_active)


class XiawanImageSwitch:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "switch": ("BOOLEAN", {"default": False, "forceInput": True}),
            },
            "optional": {
                "on_false": ("IMAGE", {"lazy": True}),
                "on_true": ("IMAGE", {"lazy": True}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def check_lazy_status(self, switch=False, on_false=_MISSING, on_true=_MISSING, **kwargs):
        if _coerce_bool(switch) and on_true is None:
            return ["on_true"]
        if not _coerce_bool(switch) and on_false is None:
            return ["on_false"]

    def output(self, switch=False, on_false=_MISSING, on_true=_MISSING):
        if on_false is _MISSING:
            return (on_true,)
        if on_true is _MISSING:
            return (on_false,)
        if _coerce_bool(switch):
            return (on_true,)
        return (on_false,)


class XiawanLatentSwitch:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "switch": ("BOOLEAN", {"default": False, "forceInput": True}),
            },
            "optional": {
                "on_false": ("LATENT", {"lazy": True}),
                "on_true": ("LATENT", {"lazy": True}),
            },
        }

    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("latent",)
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def check_lazy_status(self, switch=False, on_false=_MISSING, on_true=_MISSING, **kwargs):
        if _coerce_bool(switch) and on_true is None:
            return ["on_true"]
        if not _coerce_bool(switch) and on_false is None:
            return ["on_false"]

    def output(self, switch=False, on_false=_MISSING, on_true=_MISSING):
        if on_false is _MISSING:
            return (on_true,)
        if on_true is _MISSING:
            return (on_false,)
        if _coerce_bool(switch):
            return (on_true,)
        return (on_false,)


class XiawanModelSwitch:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "index": ("*", {"forceInput": True}),
            },
            "optional": {
                "value0": ("MODEL", {"lazy": True}),
                "value1": ("MODEL", {"lazy": True}),
            },
        }

    RETURN_TYPES = ("MODEL",)
    RETURN_NAMES = ("model",)
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    @staticmethod
    def _safe_index(index):
        if isinstance(index, bool):
            return 1 if index else 0
        try:
            return 1 if int(index) == 1 else 0
        except Exception:
            return 1 if _coerce_bool(index) else 0

    def check_lazy_status(self, index=0, value0=_MISSING, value1=_MISSING, **kwargs):
        selected = self._safe_index(index)
        if selected == 1 and value1 is None:
            return ["value1"]
        if selected != 1 and value0 is None:
            return ["value0"]

    def output(self, index=0, value0=_MISSING, value1=_MISSING):
        if value0 is _MISSING:
            return (value1,)
        if value1 is _MISSING:
            return (value0,)
        if self._safe_index(index) == 1:
            return (value1,)
        return (value0,)



class XiawanFinalImageSwitch:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "index": ("INT", {"default": 0, "forceInput": True}),
            },
            "optional": {
                "image0": ("IMAGE", {"lazy": True}),
                "image1": ("IMAGE", {"lazy": True}),
                "image2": ("IMAGE", {"lazy": True}),
                "image3": ("IMAGE", {"lazy": True}),
                "image4": ("IMAGE", {"lazy": True}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    @staticmethod
    def _safe_index(index):
        try:
            return max(0, min(4, int(index)))
        except Exception:
            return 0

    def check_lazy_status(self, index=0, **kwargs):
        selected = self._safe_index(index)
        needed = []
        for i in range(selected, -1, -1):
            key = f"image{i}"
            if kwargs.get(key, None) is None:
                needed.append(key)
        return needed

    def output(self, index=0, image0=_MISSING, image1=_MISSING, image2=_MISSING, image3=_MISSING, image4=_MISSING):
        images = [image0, image1, image2, image3, image4]
        selected = self._safe_index(index)
        for i in range(selected, -1, -1):
            image = images[i]
            if image is not _MISSING and image is not None:
                return (image,)
        for image in images:
            if image is not _MISSING and image is not None:
                return (image,)
        raise RuntimeError("XiawanFinalImageSwitch received no images from any enabled output branch.")


class XiawanAnimaModelLoader:
    @staticmethod
    def _native_anima_supported():
        """Require ComfyUI's official Anima model and text-encoder stack."""
        try:
            import comfy.ldm.anima.model  # noqa: F401
            import comfy.model_base

            te_model = getattr(getattr(comfy, "sd", None), "TEModel", None)
            return (
                hasattr(getattr(comfy, "sd", None), "load_clip")
                and hasattr(te_model, "QWEN3_06B")
                and hasattr(comfy.model_base, "Anima")
            )
        except Exception:
            return False

    @staticmethod
    def _release_previous_models():
        """Make room before loading Anima after an SDXL execution."""
        try:
            import gc
            import comfy.model_management as model_management

            model_management.unload_all_models()
            model_management.soft_empty_cache()
            gc.collect()
            if torch is not None and torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            # Loading remains delegated to ComfyUI; cleanup is best effort.
            pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "diffusion_model": (folder_paths.get_filename_list("diffusion_models"), {"default": "anima-base-v1.0.safetensors"}),
                "text_encoder": (folder_paths.get_filename_list("text_encoders"), {"default": "qwen_3_06b_base.safetensors"}),
                "vae": (folder_paths.get_filename_list("vae"), {"default": "qwen_image_vae.safetensors"}),
                "unet_weight_dtype": (["default", "fp8_e4m3fn", "fp8_e4m3fn_fast", "fp8_e5m2"], {"default": "default"}),
                "clip_type": (["anima_qwen3_06b"], {"default": "anima_qwen3_06b"}),
            },
            "optional": {
                "clip_device": (["default", "cpu"], {"default": "cpu", "advanced": True}),
            },
        }

    RETURN_TYPES = ("MODEL", "CLIP", "VAE")
    RETURN_NAMES = ("MODEL", "CLIP", "VAE")
    FUNCTION = "load_models"
    CATEGORY = "Xiawan/Workflow Controls"

    def load_models(
        self,
        diffusion_model="anima-base-v1.0.safetensors",
        text_encoder="qwen_3_06b_base.safetensors",
        vae="qwen_image_vae.safetensors",
        unet_weight_dtype="default",
        clip_type="anima_qwen3_06b",
        clip_device="cpu",
    ):
        if comfy is None or torch is None:
            raise RuntimeError("ComfyUI model loading modules are unavailable.")
        if not self._native_anima_supported():
            raise RuntimeError(
                "Anima requires a ComfyUI runtime with native Anima/LLMAdapter "
                "support. Upgrade ComfyUI before running this branch."
            )

        self._release_previous_models()
        model_options = {}
        if unet_weight_dtype == "fp8_e4m3fn":
            model_options["dtype"] = torch.float8_e4m3fn
        elif unet_weight_dtype == "fp8_e4m3fn_fast":
            model_options["dtype"] = torch.float8_e4m3fn
            model_options["fp8_optimizations"] = True
        elif unet_weight_dtype == "fp8_e5m2":
            model_options["dtype"] = torch.float8_e5m2

        unet_path = folder_paths.get_full_path_or_raise("diffusion_models", diffusion_model)
        model = comfy.sd.load_diffusion_model(unet_path, model_options=model_options)

        clip_options = {}
        if clip_device == "cpu":
            clip_options["load_device"] = clip_options["offload_device"] = torch.device("cpu")
        clip_path = folder_paths.get_full_path_or_raise("text_encoders", text_encoder)
        clip = comfy.sd.load_clip(
            [clip_path],
            embedding_directory=folder_paths.get_folder_paths("embeddings"),
            model_options=clip_options,
        )

        vae_path = folder_paths.get_full_path_or_raise("vae", vae)
        vae_sd = comfy.utils.load_torch_file(vae_path)
        vae_model = comfy.sd.VAE(sd=vae_sd)
        vae_model.throw_exception_if_invalid()

        return (model, clip, vae_model)


class XiawanOptionalLoraSyntax:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "enabled": ("BOOLEAN", {"default": True, "forceInput": True}),
                "lora_name": ("STRING", {"default": "anima-turbo-lora-v0.2.safetensors"}),
                "strength": ("FLOAT", {"default": 0.85, "min": -100.0, "max": 100.0, "step": 0.01, "forceInput": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("lora_syntax",)
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, enabled=True, lora_name="anima-turbo-lora-v0.2.safetensors", strength=0.85):
        if not _coerce_bool(enabled):
            return ("",)
        name = str(lora_name or "").strip()
        if not name:
            return ("",)
        return (f"<lora:{name}:{float(strength):.4g}>",)


class XiawanPromptParams:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "主体提示词": (
                    "STRING",
                    {
                        "default": "1girl, masterpiece, best quality, detailed eyes, clean linework",
                        "multiline": True,
                    },
                ),
                "风格背景提示词": (
                    "STRING",
                    {
                        "default": "artist style, coherent background, lighting, painterly details",
                        "multiline": True,
                    },
                ),
                "人物替换提示词": (
                    "STRING",
                    {
                        "default": "same character identity, matching hair, matching outfit, consistent face",
                        "multiline": True,
                    },
                ),
                "负面提示词": (
                    "STRING",
                    {
                        "default": "low quality, worst quality, bad anatomy, extra fingers, watermark, text",
                        "multiline": True,
                    },
                ),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("subject_prompt", "style_redraw_prompt", "person_swap_prompt", "negative_prompt")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, **kwargs):
        subject_prompt = _value(kwargs, "主体提示词", "subject_prompt", default="")
        style_redraw_prompt = _value(kwargs, "风格背景提示词", "style_redraw_prompt", default="")
        person_swap_prompt = _value(kwargs, "人物替换提示词", "person_swap_prompt", default="")
        negative_prompt = _value(kwargs, "负面提示词", "negative_prompt", default="")
        return (subject_prompt, style_redraw_prompt, person_swap_prompt, negative_prompt)


class XiawanPromptRoute:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "夏晚正面": ("STRING", {"multiline": True, "forceInput": True}),
                "夏晚负面": ("STRING", {"multiline": True, "forceInput": True}),
                "WeiLin正面": ("STRING", {"multiline": True, "forceInput": True}),
                "WeiLin负面": ("STRING", {"multiline": True, "forceInput": True}),
                "正面来源": (["夏晚", "WeiLin"], {"default": "夏晚"}),
                "负面来源": (["夏晚", "WeiLin"], {"default": "夏晚"}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("positive_prompt", "negative_prompt")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, **kwargs):
        xiawan_positive = _value(kwargs, "夏晚正面", "xiawan_positive", default="")
        xiawan_negative = _value(kwargs, "夏晚负面", "xiawan_negative", default="")
        weilin_positive = _value(kwargs, "WeiLin正面", "weilin_positive", default="")
        weilin_negative = _value(kwargs, "WeiLin负面", "weilin_negative", default="")
        positive_source = _value(kwargs, "正面来源", "positive_source", default="夏晚")
        negative_source = _value(kwargs, "负面来源", "negative_source", default="夏晚")
        positive = weilin_positive if positive_source == "WeiLin" else xiawan_positive
        negative = weilin_negative if negative_source == "WeiLin" else xiawan_negative
        return (positive, negative)


class XiawanOptionalPromptAppend:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "base_prompt": ("STRING", {"multiline": True, "forceInput": True}),
                "enabled": ("BOOLEAN", {"default": False, "forceInput": True}),
                "delimiter": ("STRING", {"default": ", "}),
            },
            "optional": {
                "extra_prompt": ("STRING", {"multiline": True, "forceInput": True, "lazy": True}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def check_lazy_status(self, base_prompt, enabled, delimiter=", ", extra_prompt=None, **kwargs):
        if _coerce_bool(enabled) and extra_prompt is None:
            return ["extra_prompt"]
        return []

    def output(self, base_prompt="", enabled=False, delimiter=", ", extra_prompt=None):
        base = _merge_prompt_texts(base_prompt, delimiter=delimiter)
        if not _coerce_bool(enabled):
            return (base,)

        return (_merge_prompt_texts(base, extra_prompt, delimiter=delimiter),)


class XiawanDanbooruGlobalPromptAppend:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "base_prompt": ("STRING", {"multiline": True, "forceInput": True}),
                "enabled": ("BOOLEAN", {"default": False, "forceInput": True}),
                "delimiter": ("STRING", {"default": ", "}),
            },
            "optional": {
                "danbooru_prompts": ("STRING", {"multiline": True, "forceInput": True, "lazy": True}),
            },
        }

    INPUT_IS_LIST = True
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def check_lazy_status(self, base_prompt, enabled=False, delimiter=", ", danbooru_prompts=None, **kwargs):
        if _coerce_bool(self._first_value(enabled, False)) and danbooru_prompts is None:
            return ["danbooru_prompts"]
        return []

    def output(self, base_prompt, enabled=False, delimiter=", ", danbooru_prompts=None):
        separator = self._first_text(delimiter, ", ")
        base = _merge_prompt_texts(base_prompt, delimiter=separator)
        if not _coerce_bool(self._first_value(enabled, False)):
            return (base,)

        return (_merge_prompt_texts(base, danbooru_prompts, delimiter=separator),)

    @staticmethod
    def _first_text(value, default=""):
        if isinstance(value, (list, tuple)):
            if not value:
                return default
            return XiawanDanbooruGlobalPromptAppend._first_text(value[0], default)
        if value is None:
            return default
        return str(value)

    @staticmethod
    def _first_value(value, default=None):
        if isinstance(value, (list, tuple)):
            if not value:
                return default
            return XiawanDanbooruGlobalPromptAppend._first_value(value[0], default)
        if value is None:
            return default
        return value

    @staticmethod
    def _flatten_texts(value):
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            texts = []
            for item in value:
                texts.extend(XiawanDanbooruGlobalPromptAppend._flatten_texts(item))
            return texts
        text = str(value).strip()
        return [text] if text else []


class XiawanTaggerParams:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_name": (TAGGER_MODEL_NAMES, {"default": "cl_tagger/cl_tagger_1_02.onnx"}),
                "general": ("FLOAT", {"default": 0.55, "min": 0.05, "max": 1.0, "step": 0.01}),
                "character": ("FLOAT", {"default": 0.6, "min": 0.05, "max": 1.0, "step": 0.01}),
                "replace_space": ("BOOLEAN", {"default": True}),
                "categories": ("STRING", {"default": "general,character,copyright,meta"}),
                "exclude_tags": ("STRING", {"default": ""}),
                "session_method": (TAGGER_SESSION_METHODS, {"default": "CPU"}),
            }
        }

    RETURN_TYPES = (TAGGER_MODEL_NAMES, "FLOAT", "FLOAT", "BOOLEAN", "STRING", "STRING", TAGGER_SESSION_METHODS)
    RETURN_NAMES = (
        "model_name",
        "general",
        "character",
        "replace_space",
        "categories",
        "exclude_tags",
        "session_method",
    )
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, model_name, general, character, replace_space, categories, exclude_tags, session_method):
        return (
            str(model_name or ""),
            float(general),
            float(character),
            _coerce_bool(replace_space),
            str(categories or ""),
            str(exclude_tags or ""),
            str(session_method or "CPU"),
        )


class XiawanClearableShowText:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "enabled": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "text": ("STRING", {"forceInput": True, "lazy": True}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "notify"
    OUTPUT_NODE = True
    CATEGORY = "Xiawan/Workflow Controls"

    def check_lazy_status(self, enabled, text=None, **kwargs):
        if _coerce_bool(enabled) and text is None:
            return ["text"]
        return []

    def notify(self, enabled=True, text="", unique_id=None, extra_pnginfo=None):
        value = str(text or "") if _coerce_bool(enabled) else ""
        if unique_id is not None and extra_pnginfo is not None:
            self._update_workflow_widget(value, unique_id, extra_pnginfo)
        return {"ui": {"text": [value]}, "result": (value,)}

    @staticmethod
    def _update_workflow_widget(value, unique_id, extra_pnginfo):
        info = extra_pnginfo[0] if isinstance(extra_pnginfo, list) and extra_pnginfo else extra_pnginfo
        uid = unique_id[0] if isinstance(unique_id, list) and unique_id else unique_id
        if not isinstance(info, dict) or "workflow" not in info:
            return
        workflow = info["workflow"]
        if not isinstance(workflow, dict):
            return
        node = next((x for x in workflow.get("nodes", []) if str(x.get("id")) == str(uid)), None)
        if node is not None:
            node["widgets_values"] = [value]


class XiawanFinalOutputParams:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "0 底图开关": ("BOOLEAN", {"default": True, "forceInput": True}),
                "1 潜放开关": ("BOOLEAN", {"default": True, "forceInput": True}),
                "2 迭代开关": ("BOOLEAN", {"default": True, "forceInput": True}),
                "3 通用开关": ("BOOLEAN", {"default": True, "forceInput": True}),
                "4 细化开关": ("BOOLEAN", {"default": True, "forceInput": True}),
            },
            "optional": {
                "4-a 脸部细化开关": ("BOOLEAN", {"default": False, "forceInput": True}),
                "4-b 眼睛细化开关": ("BOOLEAN", {"default": False, "forceInput": True}),
                "4-c 手部细化开关": ("BOOLEAN", {"default": False, "forceInput": True}),
                "4-d 足部细化开关": ("BOOLEAN", {"default": False, "forceInput": True}),
                "4-e 乳首细化开关": ("BOOLEAN", {"default": False, "forceInput": True}),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("final_output_index",)
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, **kwargs):
        detail_children_enabled = any(
            _coerce_bool(_value(kwargs, name, default=False))
            for name in (
                "4-a 脸部细化开关",
                "4-b 眼睛细化开关",
                "4-c 手部细化开关",
                "4-d 足部细化开关",
                "4-e 乳首细化开关",
            )
        )
        stages = [
            _coerce_bool(_value(kwargs, "0 底图开关", "base_enabled", default=True)),
            _coerce_bool(_value(kwargs, "1 潜放开关", "latent_enabled", default=False)),
            _coerce_bool(_value(kwargs, "2 迭代开关", "iterative_enabled", default=False)),
            _coerce_bool(_value(kwargs, "3 通用开关", "model_upscale_enabled", default=False)),
            _coerce_bool(_value(kwargs, "4 细化开关", "detailer_enabled", default=False)) and detail_children_enabled,
        ]
        for index in range(len(stages) - 1, -1, -1):
            if stages[index]:
                return (index,)
        return (0,)


class XiawanUpscaleParams:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "最终输出编号": ("INT", {"default": 4, "min": 0, "max": 4, "step": 1}),
                "潜放倍数": ("FLOAT", {"default": 1.25, "min": 1.0, "max": 4.0, "step": 0.05}),
                "放大降噪": ("FLOAT", {"default": 0.35, "min": 0.0, "max": 1.0, "step": 0.01}),
                "迭代倍数": ("FLOAT", {"default": 1.8, "min": 1.0, "max": 4.0, "step": 0.05}),
                "迭代次数": ("INT", {"default": 3, "min": 1, "max": 12, "step": 1}),
            }
        }

    RETURN_TYPES = ("INT", "FLOAT", "FLOAT", "FLOAT", "INT")
    RETURN_NAMES = ("final_output_index", "latent_scale", "refiner_denoise", "iterative_scale", "iterative_steps")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, **kwargs):
        return (
            _value(kwargs, "最终输出编号", "final_output_index", default=4),
            _value(kwargs, "潜放倍数", "latent_scale", default=1.5),
            _value(kwargs, "放大降噪", "refiner_denoise", default=0.35),
            _value(kwargs, "迭代倍数", "iterative_scale", default=1.8),
            _value(kwargs, "迭代次数", "iterative_steps", default=3),
        )



class XiawanLatentUpscaleParams:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "放大方法": (LATENT_UPSCALE_METHODS, {"default": "bicubic"}),
                "放大倍率": ("FLOAT", {"default": 1.25, "min": 1.0, "max": 8.0, "step": 0.05}),
                "步数": ("INT", {"default": 10, "min": 1, "max": 100, "step": 1}),
                "CFG": ("FLOAT", {"default": 4.8, "min": 0.0, "max": 30.0, "step": 0.1}),
                "采样器": (SAMPLERS, {"default": "dpmpp_2m"}),
                "调度器": (SCHEDULERS, {"default": "karras"}),
                "降噪": ("FLOAT", {"default": 0.22, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
        }

    RETURN_TYPES = (LATENT_UPSCALE_METHODS, "FLOAT", "INT", "FLOAT", SAMPLERS, SCHEDULERS, "FLOAT")
    RETURN_NAMES = ("upscale_method", "scale_by", "steps", "cfg", "sampler_name", "scheduler", "denoise")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, **kwargs):
        steps = _value(kwargs, "步数", "steps", default=10)
        return (_value(kwargs, "放大方法", "upscale_method", default="bicubic"), _value(kwargs, "放大倍率", "scale_by", default=1.25), steps, _value(kwargs, "CFG", "cfg", default=4.8), _value(kwargs, "采样器", "sampler_name", default="dpmpp_2m"), _value(kwargs, "调度器", "scheduler", default="karras"), _value(kwargs, "降噪", "denoise", default=0.22))


class XiawanIterativeUpscaleParams:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "缩放方法": (PIXEL_UPSCALE_METHODS, {"default": "lanczos"}),
                "步数": ("INT", {"default": 10, "min": 1, "max": 100, "step": 1}),
                "CFG": ("FLOAT", {"default": 4.8, "min": 0.0, "max": 30.0, "step": 0.1}),
                "采样器": (SAMPLERS, {"default": "dpmpp_2m"}),
                "调度器": (SCHEDULERS + IMPACT_SCHEDULERS, {"default": "karras"}),
                "降噪": ("FLOAT", {"default": 0.20, "min": 0.0, "max": 1.0, "step": 0.01}),
                "启用平铺 VAE": ("BOOLEAN", {"default": True}),
                "瓦片大小": ("INT", {"default": 1024, "min": 320, "max": 4096, "step": 64}),
                "放大倍率": ("FLOAT", {"default": 1.35, "min": 1.0, "max": 8.0, "step": 0.05}),
                "迭代次数": ("INT", {"default": 2, "min": 1, "max": 12, "step": 1}),
                "临时前缀": ("STRING", {"default": ""}),
                "步进模式": (ITERATIVE_STEP_MODES, {"default": "geometric"}),
                "VAE 压缩": ("INT", {"default": 8, "min": 0, "max": 256, "step": 8}),
            },
        }

    RETURN_TYPES = (PIXEL_UPSCALE_METHODS, "INT", "FLOAT", SAMPLERS, SCHEDULERS + IMPACT_SCHEDULERS, "FLOAT", "BOOLEAN", "INT", "FLOAT", "INT", "STRING", ITERATIVE_STEP_MODES, "INT")
    RETURN_NAMES = ("scale_method", "steps", "cfg", "sampler_name", "scheduler", "denoise", "use_tiled_vae", "tile_size", "upscale_factor", "iterative_steps", "temp_prefix", "step_mode", "vae_compression")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, **kwargs):
        steps = _value(kwargs, "步数", "steps", default=10)
        iterative_steps = _value(kwargs, "迭代次数", "iterative_steps", default=2)
        return (_value(kwargs, "缩放方法", "scale_method", default="lanczos"), steps, _value(kwargs, "CFG", "cfg", default=4.8), _value(kwargs, "采样器", "sampler_name", default="dpmpp_2m"), _value(kwargs, "调度器", "scheduler", default="karras"), _value(kwargs, "降噪", "denoise", default=0.20), _value(kwargs, "启用平铺 VAE", "use_tiled_vae", default=True), _value(kwargs, "瓦片大小", "tile_size", default=1024), _value(kwargs, "放大倍率", "upscale_factor", default=1.35), iterative_steps, _value(kwargs, "临时前缀", "temp_prefix", default=""), _value(kwargs, "步进模式", "step_mode", default="geometric"), _value(kwargs, "VAE 压缩", "vae_compression", default=8))


class XiawanModelUpscaleParams:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "放大方法": (IMAGE_UPSCALE_METHODS, {"default": "lanczos"}),
                "目标倍率": ("FLOAT", {"default": 1.0, "min": 0.01, "max": 8.0, "step": 0.01}),
                "模型原生倍率": ("FLOAT", {"default": 4.0, "min": 1.0, "max": 8.0, "step": 0.01}),
                "步数": ("INT", {"default": 8, "min": 1, "max": 100, "step": 1}),
                "CFG": ("FLOAT", {"default": 4.5, "min": 0.0, "max": 30.0, "step": 0.1}),
                "采样器": (SAMPLERS, {"default": "dpmpp_2m"}),
                "调度器": (SCHEDULERS, {"default": "karras"}),
                "降噪": ("FLOAT", {"default": 0.12, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
        }

    RETURN_TYPES = (IMAGE_UPSCALE_METHODS, "FLOAT", "FLOAT", "INT", "FLOAT", SAMPLERS, SCHEDULERS, "FLOAT")
    RETURN_NAMES = ("upscale_method", "scale_by", "target_scale", "steps", "cfg", "sampler_name", "scheduler", "denoise")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, **kwargs):
        target_scale = _value(kwargs, "目标倍率", "scale_by", default=1.0)
        model_native_scale = _value(kwargs, "模型原生倍率", "model_native_scale", default=4.0)
        correction_scale = target_scale / max(model_native_scale, 0.01)
        steps = _value(kwargs, "步数", "steps", default=8)
        return (_value(kwargs, "放大方法", "upscale_method", default="lanczos"), correction_scale, target_scale, steps, _value(kwargs, "CFG", "cfg", default=4.5), _value(kwargs, "采样器", "sampler_name", default="dpmpp_2m"), _value(kwargs, "调度器", "scheduler", default="karras"), _value(kwargs, "降噪", "denoise", default=0.12))

class XiawanTargetScaleImageGuard:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "reference_image": ("IMAGE",),
                "target_scale": ("FLOAT", {"default": 1.0, "min": 0.01, "max": 8.0, "step": 0.01}),
                "upscale_method": (IMAGE_UPSCALE_METHODS, {"default": "lanczos"}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "guard"
    CATEGORY = "Xiawan/Workflow Controls"

    def guard(self, image, reference_image, target_scale=1.0, upscale_method="lanczos"):
        import comfy.utils

        ref_h, ref_w = reference_image.shape[1], reference_image.shape[2]
        target_w = max(1, round(ref_w * target_scale))
        target_h = max(1, round(ref_h * target_scale))
        if image.shape[1] == target_h and image.shape[2] == target_w:
            return (image,)
        samples = image.movedim(-1, 1)
        scaled = comfy.utils.common_upscale(samples, target_w, target_h, upscale_method, "disabled")
        return (scaled.movedim(1, -1),)


class XiawanDetailerParams:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "细化尺寸": ("FLOAT", {"default": 512, "min": 64, "max": 16384, "step": 8}),
                "按检测框计算": ("BOOLEAN", {"default": True}),
                "最大尺寸": ("FLOAT", {"default": 1024, "min": 64, "max": 16384, "step": 8}),
                "种子": ("INT", {"default": 111111111, "min": 0, "max": 0xffffffffffffffff}),
                "步数": ("INT", {"default": 18, "min": 1, "max": 100, "step": 1}),
                "引导强度": ("FLOAT", {"default": 5.0, "min": 0.0, "max": 30.0, "step": 0.1}),
                "采样器": (SAMPLERS, {"default": "euler"}),
                "调度器": (SCHEDULERS + IMPACT_SCHEDULERS, {"default": "karras"}),
                "降噪幅度": ("FLOAT", {"default": 0.45, "min": 0.0001, "max": 1.0, "step": 0.01}),
                "遮罩羽化": ("INT", {"default": 5, "min": 0, "max": 100, "step": 1}),
                "启用噪声遮罩": ("BOOLEAN", {"default": True}),
                "强制重绘": ("BOOLEAN", {"default": True}),
                "检测阈值": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01}),
                "检测扩张": ("INT", {"default": 10, "min": -512, "max": 512, "step": 1}),
                "裁剪倍率": ("FLOAT", {"default": 1.5, "min": 1.0, "max": 10.0, "step": 0.1}),
                "SAM提示": (SAM_DETECTION_HINTS, {"default": "center-1"}),
                "SAM阈值": ("FLOAT", {"default": 0.93, "min": 0.0, "max": 1.0, "step": 0.01}),
                "循环次数": ("INT", {"default": 1, "min": 1, "max": 10, "step": 1}),
                "平铺编码": ("BOOLEAN", {"default": True}),
                "平铺解码": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = (
        "FLOAT",
        "BOOLEAN",
        "FLOAT",
        "INT",
        "INT",
        "FLOAT",
        SAMPLERS,
        SCHEDULERS + IMPACT_SCHEDULERS,
        "FLOAT",
        "INT",
        "BOOLEAN",
        "BOOLEAN",
        "FLOAT",
        "INT",
        "FLOAT",
        "COMBO",
        "FLOAT",
        "INT",
        "BOOLEAN",
        "BOOLEAN",
    )
    RETURN_NAMES = (
        "guide_size",
        "guide_size_for",
        "max_size",
        "seed",
        "steps",
        "cfg",
        "sampler_name",
        "scheduler",
        "denoise",
        "feather",
        "noise_mask",
        "force_inpaint",
        "bbox_threshold",
        "bbox_dilation",
        "bbox_crop_factor",
        "sam_detection_hint",
        "sam_threshold",
        "cycle",
        "tiled_encode",
        "tiled_decode",
    )
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, **kwargs):
        return (
            _value(kwargs, "细化尺寸", "guide_size", default=512),
            _value(kwargs, "按检测框计算", "guide_size_for", default=True),
            _value(kwargs, "最大尺寸", "max_size", default=1024),
            _value(kwargs, "种子", "seed", default=111111111),
            _value(kwargs, "步数", "steps", default=18),
            _value(kwargs, "引导强度", "CFG", "cfg", default=5.0),
            _value(kwargs, "采样器", "sampler_name", default="euler"),
            _value(kwargs, "调度器", "scheduler", default="karras"),
            _value(kwargs, "降噪幅度", "denoise", default=0.45),
            _value(kwargs, "遮罩羽化", "feather", default=5),
            _value(kwargs, "启用噪声遮罩", "noise_mask", default=True),
            _value(kwargs, "强制重绘", "force_inpaint", default=True),
            _value(kwargs, "检测阈值", "bbox_threshold", default=0.5),
            _value(kwargs, "检测扩张", "bbox_dilation", default=10),
            _value(kwargs, "裁剪倍率", "bbox_crop_factor", default=1.5),
            _value(kwargs, "SAM提示", "sam_detection_hint", default="center-1"),
            _value(kwargs, "SAM阈值", "sam_threshold", default=0.93),
            _value(kwargs, "循环次数", "cycle", default=1),
            _value(kwargs, "平铺编码", "tiled_encode", default=True),
            _value(kwargs, "平铺解码", "tiled_decode", default=True),
        )


class XiawanDetailerSampleParams:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "细化尺寸": ("FLOAT", {"default": 512, "min": 64, "max": 16384, "step": 8}),
                "按检测框计算": ("BOOLEAN", {"default": True}),
                "最大尺寸": ("FLOAT", {"default": 1024, "min": 64, "max": 16384, "step": 8}),
                "种子": ("INT", {"default": 111111111, "min": 0, "max": 0xffffffffffffffff}),
                "步数": ("INT", {"default": 18, "min": 1, "max": 100, "step": 1}),
                "引导强度": ("FLOAT", {"default": 5.0, "min": 0.0, "max": 30.0, "step": 0.1}),
                "采样器": (SAMPLERS, {"default": "euler"}),
                "调度器": (SCHEDULERS + IMPACT_SCHEDULERS, {"default": "karras"}),
                "降噪幅度": ("FLOAT", {"default": 0.45, "min": 0.0001, "max": 1.0, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("FLOAT", "BOOLEAN", "FLOAT", "INT", "INT", "FLOAT", SAMPLERS, SCHEDULERS + IMPACT_SCHEDULERS, "FLOAT")
    RETURN_NAMES = (
        "guide_size",
        "guide_size_for",
        "max_size",
        "seed",
        "steps",
        "cfg",
        "sampler_name",
        "scheduler",
        "denoise",
    )
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, **kwargs):
        return (
            _value(kwargs, "细化尺寸", "guide_size", default=512),
            _value(kwargs, "按检测框计算", "guide_size_for", default=True),
            _value(kwargs, "最大尺寸", "max_size", default=1024),
            _value(kwargs, "种子", "seed", default=111111111),
            _value(kwargs, "步数", "steps", default=18),
            _value(kwargs, "引导强度", "CFG", "cfg", default=5.0),
            _value(kwargs, "采样器", "sampler_name", default="euler"),
            _value(kwargs, "调度器", "scheduler", default="karras"),
            _value(kwargs, "降噪幅度", "denoise", default=0.45),
        )


class XiawanDetailerMaskParams:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "遮罩羽化": ("INT", {"default": 5, "min": 0, "max": 100, "step": 1}),
                "启用噪声遮罩": ("BOOLEAN", {"default": True}),
                "强制重绘": ("BOOLEAN", {"default": True}),
                "检测阈值": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01}),
                "检测扩张": ("INT", {"default": 10, "min": -512, "max": 512, "step": 1}),
                "裁剪倍率": ("FLOAT", {"default": 1.5, "min": 1.0, "max": 10.0, "step": 0.1}),
                "SAM提示": (SAM_DETECTION_HINTS, {"default": "center-1"}),
                "SAM阈值": ("FLOAT", {"default": 0.93, "min": 0.0, "max": 1.0, "step": 0.01}),
                "循环次数": ("INT", {"default": 1, "min": 1, "max": 10, "step": 1}),
                "平铺编码": ("BOOLEAN", {"default": True}),
                "平铺解码": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("INT", "BOOLEAN", "BOOLEAN", "FLOAT", "INT", "FLOAT", "COMBO", "FLOAT", "INT", "BOOLEAN", "BOOLEAN")
    RETURN_NAMES = (
        "feather",
        "noise_mask",
        "force_inpaint",
        "bbox_threshold",
        "bbox_dilation",
        "bbox_crop_factor",
        "sam_detection_hint",
        "sam_threshold",
        "cycle",
        "tiled_encode",
        "tiled_decode",
    )
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, **kwargs):
        return (
            _value(kwargs, "遮罩羽化", "feather", default=5),
            _value(kwargs, "启用噪声遮罩", "noise_mask", default=True),
            _value(kwargs, "强制重绘", "force_inpaint", default=True),
            _value(kwargs, "检测阈值", "bbox_threshold", default=0.5),
            _value(kwargs, "检测扩张", "bbox_dilation", default=10),
            _value(kwargs, "裁剪倍率", "bbox_crop_factor", default=1.5),
            _value(kwargs, "SAM提示", "sam_detection_hint", default="center-1"),
            _value(kwargs, "SAM阈值", "sam_threshold", default=0.93),
            _value(kwargs, "循环次数", "cycle", default=1),
            _value(kwargs, "平铺编码", "tiled_encode", default=True),
            _value(kwargs, "平铺解码", "tiled_decode", default=True),
        )


class XiawanRegionalDetailerParams:
    @classmethod
    def INPUT_TYPES(cls):
        face_models = _bbox_models("bbox/face_yolov8m.pt")
        eye_models = _bbox_models("bbox/full_eyes_detect_v1.pt")
        hand_models = _bbox_models("bbox/hand_yolov8s.pt")
        return {
            "required": {
                "脸部检测模型": (face_models, {"default": "bbox/face_yolov8m.pt" if "bbox/face_yolov8m.pt" in face_models else face_models[0]}),
                "脸部步数": ("INT", {"default": 18, "min": 1, "max": 100, "step": 1}),
                "脸部引导强度": ("FLOAT", {"default": 5.0, "min": 0.0, "max": 30.0, "step": 0.1}),
                "脸部降噪幅度": ("FLOAT", {"default": 0.45, "min": 0.0001, "max": 1.0, "step": 0.01}),
                "脸部采样器": (SAMPLERS, {"default": "euler"}),
                "脸部调度器": (SCHEDULERS + IMPACT_SCHEDULERS, {"default": "karras"}),
                "眼睛检测模型": (eye_models, {"default": "bbox/full_eyes_detect_v1.pt" if "bbox/full_eyes_detect_v1.pt" in eye_models else eye_models[0]}),
                "眼睛步数": ("INT", {"default": 14, "min": 1, "max": 100, "step": 1}),
                "眼睛引导强度": ("FLOAT", {"default": 5.0, "min": 0.0, "max": 30.0, "step": 0.1}),
                "眼睛降噪幅度": ("FLOAT", {"default": 0.32, "min": 0.0001, "max": 1.0, "step": 0.01}),
                "眼睛采样器": (SAMPLERS, {"default": "euler"}),
                "眼睛调度器": (SCHEDULERS + IMPACT_SCHEDULERS, {"default": "karras"}),
                "手部检测模型": (hand_models, {"default": "bbox/hand_yolov8s.pt" if "bbox/hand_yolov8s.pt" in hand_models else hand_models[0]}),
                "手部步数": ("INT", {"default": 20, "min": 1, "max": 100, "step": 1}),
                "手部引导强度": ("FLOAT", {"default": 5.5, "min": 0.0, "max": 30.0, "step": 0.1}),
                "手部降噪幅度": ("FLOAT", {"default": 0.5, "min": 0.0001, "max": 1.0, "step": 0.01}),
                "手部采样器": (SAMPLERS, {"default": "euler"}),
                "手部调度器": (SCHEDULERS + IMPACT_SCHEDULERS, {"default": "karras"}),
            }
        }

    RETURN_TYPES = (
        _bbox_models("bbox/face_yolov8m.pt"),
        "INT",
        "FLOAT",
        "FLOAT",
        SAMPLERS,
        SCHEDULERS + IMPACT_SCHEDULERS,
        _bbox_models("bbox/full_eyes_detect_v1.pt"),
        "INT",
        "FLOAT",
        "FLOAT",
        SAMPLERS,
        SCHEDULERS + IMPACT_SCHEDULERS,
        _bbox_models("bbox/hand_yolov8s.pt"),
        "INT",
        "FLOAT",
        "FLOAT",
        SAMPLERS,
        SCHEDULERS + IMPACT_SCHEDULERS,
    )
    RETURN_NAMES = (
        "face_model",
        "face_steps",
        "face_cfg",
        "face_denoise",
        "face_sampler",
        "face_scheduler",
        "eye_model",
        "eye_steps",
        "eye_cfg",
        "eye_denoise",
        "eye_sampler",
        "eye_scheduler",
        "hand_model",
        "hand_steps",
        "hand_cfg",
        "hand_denoise",
        "hand_sampler",
        "hand_scheduler",
    )
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, **kwargs):
        return (
            _value(kwargs, "脸部检测模型", "face_model", default="bbox/face_yolov8m.pt"),
            _value(kwargs, "脸部步数", "face_steps", default=18),
            _value(kwargs, "脸部引导强度", "face_cfg", default=5.0),
            _value(kwargs, "脸部降噪幅度", "face_denoise", default=0.45),
            _value(kwargs, "脸部采样器", "face_sampler", default="euler"),
            _value(kwargs, "脸部调度器", "face_scheduler", default="karras"),
            _value(kwargs, "眼睛检测模型", "eye_model", default="bbox/full_eyes_detect_v1.pt"),
            _value(kwargs, "眼睛步数", "eye_steps", default=14),
            _value(kwargs, "眼睛引导强度", "eye_cfg", default=5.0),
            _value(kwargs, "眼睛降噪幅度", "eye_denoise", default=0.32),
            _value(kwargs, "眼睛采样器", "eye_sampler", default="euler"),
            _value(kwargs, "眼睛调度器", "eye_scheduler", default="karras"),
            _value(kwargs, "手部检测模型", "hand_model", default="bbox/hand_yolov8s.pt"),
            _value(kwargs, "手部步数", "hand_steps", default=20),
            _value(kwargs, "手部引导强度", "hand_cfg", default=5.5),
            _value(kwargs, "手部降噪幅度", "hand_denoise", default=0.5),
            _value(kwargs, "手部采样器", "hand_sampler", default="euler"),
            _value(kwargs, "手部调度器", "hand_scheduler", default="karras"),
        )



class XiawanSingleRegionDetailerParams:
    @classmethod
    def INPUT_TYPES(cls):
        detector_models = _bbox_models("bbox/face_yolov8m.pt")
        default_model = "bbox/face_yolov8m.pt" if "bbox/face_yolov8m.pt" in detector_models else detector_models[0]
        return {
            "required": {
                "检测模型": (detector_models, {"default": default_model}),
                "步数": ("INT", {"default": 12, "min": 1, "max": 100, "step": 1}),
                "CFG": ("FLOAT", {"default": 4.8, "min": 0.0, "max": 30.0, "step": 0.1}),
                "降噪": ("FLOAT", {"default": 0.30, "min": 0.0001, "max": 1.0, "step": 0.01}),
                "采样器": (SAMPLERS, {"default": "dpmpp_2m"}),
                "调度器": (SCHEDULERS + IMPACT_SCHEDULERS, {"default": "karras"}),
                "引导尺寸": ("FLOAT", {"default": 512, "min": 64, "max": 2048, "step": 8}),
                "最大尺寸": ("FLOAT", {"default": 1024, "min": 64, "max": 4096, "step": 8}),
                "遮罩羽化": ("INT", {"default": 5, "min": 0, "max": 100, "step": 1}),
                "检测阈值": ("FLOAT", {"default": 0.50, "min": 0.01, "max": 1.0, "step": 0.01}),
                "裁剪倍率": ("FLOAT", {"default": 3.0, "min": 1.0, "max": 10.0, "step": 0.1}),
                "启用噪声遮罩": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("COMBO", "INT", "FLOAT", "FLOAT", SAMPLERS, SCHEDULERS + IMPACT_SCHEDULERS, "FLOAT", "FLOAT", "INT", "FLOAT", "FLOAT", "BOOLEAN")
    RETURN_NAMES = ("model_name", "steps", "cfg", "denoise", "sampler_name", "scheduler", "guide_size", "max_size", "feather", "bbox_threshold", "crop_factor", "noise_mask")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, **kwargs):
        steps = _value(kwargs, "步数", "steps", default=12)
        return (
            _value(kwargs, "检测模型", "model_name", default="bbox/face_yolov8m.pt"),
            steps,
            _value(kwargs, "CFG", "cfg", default=4.8),
            _value(kwargs, "降噪", "denoise", default=0.30),
            _value(kwargs, "采样器", "sampler_name", default="dpmpp_2m"),
            _value(kwargs, "调度器", "scheduler", default="karras"),
            float(_value(kwargs, "引导尺寸", "guide_size", default=512)),
            float(_value(kwargs, "最大尺寸", "max_size", default=1024)),
            int(_value(kwargs, "遮罩羽化", "feather", default=5)),
            float(_value(kwargs, "检测阈值", "bbox_threshold", default=0.5)),
            float(_value(kwargs, "裁剪倍率", "crop_factor", default=3.0)),
            _coerce_bool(_value(kwargs, "启用噪声遮罩", "noise_mask", default=True)),
        )


class XiawanControlParams:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "OpenPose强度": ("FLOAT", {"default": 0.75, "min": 0.0, "max": 2.0, "step": 0.01}),
                "0-c1 Scribble强度": ("FLOAT", {"default": 0.50, "min": 0.0, "max": 2.0, "step": 0.01}),
                "0-c2 Lineart强度": ("FLOAT", {"default": 0.42, "min": 0.0, "max": 2.0, "step": 0.01}),
                "0-c3 Depth强度": ("FLOAT", {"default": 0.32, "min": 0.0, "max": 2.0, "step": 0.01}),
                "人物参考权重": ("FLOAT", {"default": 0.65, "min": 0.0, "max": 2.0, "step": 0.01}),
                "控制起始": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "控制结束": ("FLOAT", {"default": 0.85, "min": 0.0, "max": 1.0, "step": 0.01}),
                "人物参考起始": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "人物参考结束": ("FLOAT", {"default": 0.85, "min": 0.0, "max": 1.0, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("FLOAT", "FLOAT", "FLOAT", "FLOAT", "FLOAT", "FLOAT", "FLOAT", "FLOAT", "FLOAT")
    RETURN_NAMES = (
        "openpose_strength",
        "scribble_strength",
        "lineart_strength",
        "depth_strength",
        "person_reference_weight",
        "control_start",
        "control_end",
        "ipadapter_start",
        "ipadapter_end",
    )
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, **kwargs):
        openpose_strength = _value(kwargs, "OpenPose强度", "openpose_strength", default=0.75)
        scribble_strength = _value(
            kwargs,
            "0-c1 Scribble强度",
            "Scribble强度",
            "重绘强度",
            "scribble_strength",
            "redraw_strength",
            default=0.50,
        )
        lineart_strength = _value(
            kwargs,
            "0-c2 Lineart强度",
            "Lineart强度",
            "lineart_strength",
            default=0.42,
        )
        depth_strength = _value(
            kwargs,
            "0-c3 Depth强度",
            "Depth强度",
            "depth_strength",
            default=0.32,
        )
        person_reference_weight = _value(kwargs, "人物参考权重", "person_reference_weight", default=0.65)
        control_start = _value(kwargs, "控制起始", "control_start", "start_percent", default=0.0)
        control_end = _value(kwargs, "控制结束", "control_end", "end_percent", default=0.85)
        ipadapter_start = _value(kwargs, "人物参考起始", "ipadapter_start", "start_at", default=0.0)
        ipadapter_end = _value(kwargs, "人物参考结束", "ipadapter_end", "end_at", default=0.85)
        # keep ordering sane
        if control_end < control_start:
            control_start, control_end = control_end, control_start
        if ipadapter_end < ipadapter_start:
            ipadapter_start, ipadapter_end = ipadapter_end, ipadapter_start
        return (
            openpose_strength,
            scribble_strength,
            lineart_strength,
            depth_strength,
            person_reference_weight,
            float(control_start),
            float(control_end),
            float(ipadapter_start),
            float(ipadapter_end),
        )


class XiawanConditionalSaveImage:
    def __init__(self):
        from nodes import SaveImage

        self._save_image = SaveImage()

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "图像": ("IMAGE",),
                "启用保存": ("BOOLEAN", {"default": True}),
                "文件名前缀": ("STRING", {"default": "Aaalice_slim_enhanced"}),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "save_images"
    OUTPUT_NODE = True
    CATEGORY = "Xiawan/Workflow Controls"

    def save_images(self, **kwargs):
        images = _value(kwargs, "图像", "images")
        enabled = _value(kwargs, "启用保存", "enabled", default=True)
        filename_prefix = _value(kwargs, "文件名前缀", "filename_prefix", default="Aaalice_slim_enhanced")
        prompt = kwargs.get("prompt")
        extra_pnginfo = kwargs.get("extra_pnginfo")
        if not enabled:
            return {"ui": {"images": []}}
        try:
            return self._save_images_memory_safe(images, filename_prefix, prompt, extra_pnginfo)
        except Exception:
            return self._save_image.save_images(images, filename_prefix, prompt, extra_pnginfo)

    def _save_images_memory_safe(self, images, filename_prefix, prompt=None, extra_pnginfo=None):
        import folder_paths
        from cli_args import args

        filename_prefix += self._save_image.prefix_append
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(
            filename_prefix,
            self._save_image.output_dir,
            images[0].shape[1],
            images[0].shape[0],
        )
        results = []
        for batch_number, image in enumerate(images):
            source = image.detach().cpu().numpy()
            arr = np.empty(source.shape, dtype=np.uint8)
            rows_per_chunk = max(1, min(128, source.shape[0]))
            for row in range(0, source.shape[0], rows_per_chunk):
                block = source[row:row + rows_per_chunk]
                arr[row:row + rows_per_chunk] = (np.clip(block, 0, 1) * 255).astype(np.uint8)
            img = Image.fromarray(np.ascontiguousarray(arr))
            metadata = None
            if not args.disable_metadata:
                metadata = PngInfo()
                if prompt is not None:
                    metadata.add_text("prompt", json.dumps(prompt))
                if extra_pnginfo is not None:
                    for key in extra_pnginfo:
                        metadata.add_text(key, json.dumps(extra_pnginfo[key]))

            filename_with_batch_num = filename.replace("%batch_num%", str(batch_number))
            file = f"{filename_with_batch_num}_{counter:05}_.png"
            img.save(
                os.path.join(full_output_folder, file),
                pnginfo=metadata,
                compress_level=self._save_image.compress_level,
            )
            results.append({
                "filename": file,
                "subfolder": subfolder,
                "type": self._save_image.type,
            })
            counter += 1

        return {"ui": {"images": results}}


class XiawanClearablePreviewImage:
    def __init__(self):
        from nodes import PreviewImage

        self._preview_image = PreviewImage()

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "enabled": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "images": ("IMAGE", {"lazy": True}),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "preview_images"
    OUTPUT_NODE = True
    CATEGORY = "Xiawan/Workflow Controls"

    def check_lazy_status(self, enabled, images=None, **kwargs):
        if enabled and images is None:
            return ["images"]
        return []

    def preview_images(self, enabled=True, images=None, prompt=None, extra_pnginfo=None):
        if not enabled or images is None:
            return {"ui": {"images": []}}
        return self._preview_image.save_images(images, prompt=prompt, extra_pnginfo=extra_pnginfo)




class XiawanBooleanToIndex:
    """Replace easy simpleMath 'a' bridges with a clear stage gate helper."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "enabled": ("BOOLEAN", {"default": False, "forceInput": True}),
            }
        }

    RETURN_TYPES = ("INT", "BOOLEAN")
    RETURN_NAMES = ("index", "enabled")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, enabled=False):
        flag = _coerce_bool(enabled)
        return (1 if flag else 0, flag)


class XiawanI2IPrepare:
    """Align input image to target resolution for stable img2img."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "width": ("INT", {"default": 832, "min": 64, "max": 8192, "step": 8}),
                "height": ("INT", {"default": 1216, "min": 64, "max": 8192, "step": 8}),
                "method": (["keep", "stretch", "center_crop", "pad"], {"default": "center_crop"}),
                "pad_color": ("INT", {"default": 0, "min": 0, "max": 255, "step": 1}),
            }
        }

    RETURN_TYPES = ("IMAGE", "INT", "INT")
    RETURN_NAMES = ("image", "width", "height")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, image, width=832, height=1216, method="center_crop", pad_color=0):
        import torch
        import torch.nn.functional as F

        width = int(width)
        height = int(height)
        # image: [B,H,W,C]
        b, h, w, c = image.shape
        if method == "keep":
            return (image, int(w), int(h))

        if method == "stretch":
            x = image.permute(0, 3, 1, 2)
            x = F.interpolate(x, size=(height, width), mode="bilinear", align_corners=False)
            return (x.permute(0, 2, 3, 1), width, height)

        # scale covering / fitting
        scale_cover = max(width / w, height / h)
        scale_fit = min(width / w, height / h)
        scale = scale_cover if method == "center_crop" else scale_fit
        nh = max(1, int(round(h * scale)))
        nw = max(1, int(round(w * scale)))
        x = image.permute(0, 3, 1, 2)
        x = F.interpolate(x, size=(nh, nw), mode="bilinear", align_corners=False)

        if method == "center_crop":
            top = max(0, (nh - height) // 2)
            left = max(0, (nw - width) // 2)
            x = x[:, :, top:top + height, left:left + width]
            # if rounding short, pad
            if x.shape[2] != height or x.shape[3] != width:
                out = x.new_zeros((b, c, height, width))
                out[:, :, :x.shape[2], :x.shape[3]] = x
                x = out
            return (x.permute(0, 2, 3, 1), width, height)

        # pad
        out = image.new_zeros((b, height, width, c))
        color = float(pad_color) / 255.0
        out[..., :] = color
        top = max(0, (height - nh) // 2)
        left = max(0, (width - nw) // 2)
        x = x.permute(0, 2, 3, 1)
        out[:, top:top + nh, left:left + nw, :] = x
        return (out, width, height)


class XiawanBranchPromptBuild:
    """Build branch-specific prompts without leaking the other branch LoRA triggers."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "core_prompt": ("STRING", {"default": "", "multiline": True, "forceInput": True}),
            },
            "optional": {
                "prefix": ("STRING", {"default": "", "multiline": True, "forceInput": True}),
                "suffix": ("STRING", {"default": "", "multiline": True, "forceInput": True}),
                "branch_triggers": ("STRING", {"default": "", "multiline": True, "forceInput": True}),
                "extra_a": ("STRING", {"default": "", "multiline": True, "forceInput": True}),
                "extra_b": ("STRING", {"default": "", "multiline": True, "forceInput": True}),
                "delimiter": ("STRING", {"default": ", "}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, core_prompt="", prefix="", suffix="", branch_triggers="", extra_a="", extra_b="", delimiter=", "):
        text = _merge_prompt_texts(prefix, core_prompt, branch_triggers, extra_a, extra_b, suffix, delimiter=delimiter or ", ")
        return (text,)


class XiawanResolutionBroadcast:
    """Broadcast width/height for EmptyLatent / EmptyImage / I2I prepare."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "width": ("INT", {"default": 832, "min": 64, "max": 8192, "step": 8, "forceInput": True}),
                "height": ("INT", {"default": 1216, "min": 64, "max": 8192, "step": 8, "forceInput": True}),
            }
        }

    RETURN_TYPES = ("INT", "INT", "INT", "INT", "INT", "INT")
    RETURN_NAMES = ("width", "height", "width_b", "height_b", "width_c", "height_c")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, width=832, height=1216):
        w, h = int(width), int(height)
        return (w, h, w, h, w, h)


class XiawanStagePreset:
    """User-facing recipe presets for common Xiawan workflows."""

    PRESETS = [
        "T2I 快速出图",
        "I2I 重采样修图",
        "姿态控制出图",
        "高清放大",
        "脸手精修",
        "全功能关闭(安全)",
    ]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "preset": (cls.PRESETS, {"default": "T2I 快速出图"}),
            }
        }

    RETURN_TYPES = ("BOOLEAN", "BOOLEAN", "BOOLEAN", "BOOLEAN", "BOOLEAN", "BOOLEAN", "BOOLEAN", "STRING")
    RETURN_NAMES = (
        "enable_control_pose",
        "enable_latent_upscale",
        "enable_iterative_upscale",
        "enable_model_upscale",
        "enable_detailer",
        "enable_face",
        "enable_hand",
        "recipe_note",
    )
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, preset="T2I 快速出图"):
        # defaults all off
        pose = lat = ite = model = det = face = hand = False
        note = ""
        if preset == "T2I 快速出图":
            note = "仅底图采样：适合先找构图。建议 832x1216 / 28steps / CFG5.5 / xiawan_pro。"
        elif preset == "I2I 重采样修图":
            note = "请将底图模式改为图生图重采样，denoise 建议 0.35~0.55。"
        elif preset == "姿态控制出图":
            pose = True
            note = "开启 OpenPose；上传姿态图，强度约 0.7~0.85，控制结束 0.8。"
        elif preset == "高清放大":
            lat = True
            note = "建议只开潜放或通用放大其一。4060 8G 优先：潜放 1.25x。"
        elif preset == "脸手精修":
            det = True
            face = True
            hand = True
            note = "开启部位细化：脸+手。先有满意底图再开。"
        else:
            note = "所有增强阶段建议关闭，仅验证主模型与 LoRA。"
        return (pose, lat, ite, model, det, face, hand, note)


class XiawanEndpointStatus:
    """Describe which stage is the current final output endpoint."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "base_on": ("BOOLEAN", {"default": True, "forceInput": True}),
                "latent_on": ("BOOLEAN", {"default": False, "forceInput": True}),
                "iter_on": ("BOOLEAN", {"default": False, "forceInput": True}),
                "model_on": ("BOOLEAN", {"default": False, "forceInput": True}),
                "detailer_on": ("BOOLEAN", {"default": False, "forceInput": True}),
            }
        }

    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("endpoint_label", "endpoint_index")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, base_on=True, latent_on=False, iter_on=False, model_on=False, detailer_on=False):
        # serial pipeline endpoint: last enabled stage wins
        stages = [
            (0, _coerce_bool(base_on), "0 底图"),
            (1, _coerce_bool(latent_on), "1 潜空间放大"),
            (2, _coerce_bool(iter_on), "2 迭代放大"),
            (3, _coerce_bool(model_on), "3 通用放大"),
            (4, _coerce_bool(detailer_on), "4 部位细化"),
        ]
        endpoint = stages[0]
        for s in stages:
            if s[1]:
                endpoint = s
        label = f"当前终点：{endpoint[2]}"
        return (label, endpoint[0])


class XiawanModelHealthCheck:
    """Soft health check for recommended Xiawan models on this machine."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "checkpoint_name": ("STRING", {"default": "zukiAnimeILL_v50.safetensors"}),
                "lora_name": ("STRING", {"default": "xiawan_pro.safetensors"}),
            }
        }

    RETURN_TYPES = ("STRING", "BOOLEAN")
    RETURN_NAMES = ("report", "ok")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, checkpoint_name="zukiAnimeILL_v50.safetensors", lora_name="xiawan_pro.safetensors"):
        import folder_paths
        lines = []
        ok = True
        ckpts = set(folder_paths.get_filename_list("checkpoints") or [])
        loras = set(folder_paths.get_filename_list("loras") or [])
        if checkpoint_name not in ckpts:
            ok = False
            lines.append(f"[缺失] Checkpoint: {checkpoint_name}")
        else:
            lines.append(f"[OK] Checkpoint: {checkpoint_name}")
        if lora_name not in loras:
            ok = False
            lines.append(f"[缺失] LoRA: {lora_name}")
        else:
            lines.append(f"[OK] LoRA: {lora_name}")
        lines.append("推荐默认：832x1216 | 28 steps | CFG 5.5 | dpmpp_2m + karras | LoRA 0.9")
        lines.append("显卡建议：RTX 4060 8G 先关 Refiner/迭代/多部位细化，确认底图后再逐级开启。")
        return ("\n".join(lines), ok)




class XiawanUpscaleRecipeHint:
    """Soft mutual-exclusion / recipe guidance for upscale stages."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "latent_on": ("BOOLEAN", {"default": False, "forceInput": True}),
                "iter_on": ("BOOLEAN", {"default": False, "forceInput": True}),
                "model_on": ("BOOLEAN", {"default": False, "forceInput": True}),
            }
        }

    RETURN_TYPES = ("STRING", "BOOLEAN")
    RETURN_NAMES = ("advice", "conflict")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, latent_on=False, iter_on=False, model_on=False):
        lat = _coerce_bool(latent_on)
        ite = _coerce_bool(iter_on)
        model = _coerce_bool(model_on)
        n = int(lat) + int(ite) + int(model)
        conflict = n >= 2
        if n == 0:
            advice = "放大链路未开启。需要更高清时：优先开 1 潜放(1.25x)，4060 8G 更稳。"
        elif n == 1:
            if lat:
                advice = "当前配方：仅潜放。适合轻放大，显存友好。"
            elif ite:
                advice = "当前配方：仅迭代放大。质量高但更慢，建议关闭潜放。"
            else:
                advice = "当前配方：仅通用模型放大。注意目标倍率与模型原生倍率。"
        else:
            advice = "警告：同时开启了多个放大阶段，耗时/显存会叠加。4060 8G 建议只保留一条主放大路径。"
        return (advice, conflict)


class XiawanInpaintPadScaffold:
    """Lightweight outpaint/inpaint pad helper producing target canvas size metadata."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "pad_left": ("INT", {"default": 0, "min": 0, "max": 4096, "step": 8}),
                "pad_right": ("INT", {"default": 0, "min": 0, "max": 4096, "step": 8}),
                "pad_top": ("INT", {"default": 0, "min": 0, "max": 4096, "step": 8}),
                "pad_bottom": ("INT", {"default": 0, "min": 0, "max": 4096, "step": 8}),
                "pad_color": ("INT", {"default": 0, "min": 0, "max": 255, "step": 1}),
            }
        }

    RETURN_TYPES = ("IMAGE", "MASK", "INT", "INT")
    RETURN_NAMES = ("image", "outpaint_mask", "width", "height")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, image, pad_left=0, pad_right=0, pad_top=0, pad_bottom=0, pad_color=0):
        import torch
        b, h, w, c = image.shape
        pl, pr, pt, pb = int(pad_left), int(pad_right), int(pad_top), int(pad_bottom)
        nh, nw = h + pt + pb, w + pl + pr
        color = float(pad_color) / 255.0
        out = image.new_zeros((b, nh, nw, c))
        out[..., :] = color
        out[:, pt:pt + h, pl:pl + w, :] = image
        mask = image.new_ones((b, nh, nw))
        mask[:, pt:pt + h, pl:pl + w] = 0.0  # 0=keep, 1=paint
        return (out, mask, nw, nh)




class XiawanMemoryProfile:
    """VRAM/RAM oriented profiles for Xiawan workflow defaults."""

    PROFILES = ["4G", "8G", "12G", "24G"]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "profile": (cls.PROFILES, {"default": "8G"}),
            }
        }

    RETURN_TYPES = ("INT", "INT", "INT", "BOOLEAN", "INT", "BOOLEAN", "BOOLEAN", "BOOLEAN", "STRING")
    RETURN_NAMES = (
        "width", "height", "batch_size", "use_tiled_vae", "tile_size",
        "enable_freeu", "enable_pag", "enable_detailer_default", "advice",
    )
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, profile="8G"):
        table = {
            "4G":  (768, 1152, 1, True, 512, False, False, False, "4G: 仅底图，关 FreeU/PAG/细化，Tiled VAE 开。"),
            "8G":  (832, 1216, 1, True, 768, True, False, False, "8G(本机推荐): 832x1216，FreeU 可开，PAG 慎开，细化后开。"),
            "12G": (896, 1344, 1, True, 896, True, True, True, "12G: 可开 FreeU+PAG，细化可默认开脸。"),
            "24G": (1024, 1536, 2, False, 1024, True, True, True, "24G: 高分辨率+batch2，质量插件可全开。"),
        }
        return table.get(profile, table["8G"])


class XiawanBatchSeedMatrix:
    """Produce a small seed matrix for multi-sample exploration."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "base_seed": ("INT", {"default": 123456789, "min": 0, "max": 0xffffffffffffffff}),
                "count": ("INT", {"default": 4, "min": 1, "max": 16}),
                "mode": (["offset", "random"], {"default": "offset"}),
                "offset_step": ("INT", {"default": 1, "min": 1, "max": 100000}),
            }
        }

    RETURN_TYPES = ("INT", "INT", "INT", "INT", "INT", "STRING")
    RETURN_NAMES = ("seed_0", "seed_1", "seed_2", "seed_3", "batch_size", "seed_matrix_text")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, base_seed=123456789, count=4, mode="offset", offset_step=1):
        import random
        base = int(base_seed) & 0xffffffffffffffff
        count = max(1, min(16, int(count)))
        seeds = []
        if mode == "random":
            rng = random.Random(base)
            seeds = [rng.randint(0, 0xffffffffffffffff) for _ in range(count)]
        else:
            step = max(1, int(offset_step))
            seeds = [(base + i * step) & 0xffffffffffffffff for i in range(count)]
        while len(seeds) < 4:
            seeds.append(seeds[-1] if seeds else base)
        text = "\n".join(f"S{i}: {s}" for i, s in enumerate(seeds[:count]))
        return (int(seeds[0]), int(seeds[1]), int(seeds[2]), int(seeds[3]), count, text)


class XiawanPromptAB:
    """Prompt A/B versioning helper for quick comparison."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt_a": ("STRING", {"default": "", "multiline": True}),
                "prompt_b": ("STRING", {"default": "", "multiline": True}),
                "active": (["A", "B"], {"default": "A"}),
            },
            "optional": {
                "core_prompt": ("STRING", {"default": "", "multiline": True, "forceInput": True}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("active_prompt", "label", "both_preview")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, prompt_a="", prompt_b="", active="A", core_prompt=""):
        a = _merge_prompt_texts(core_prompt, prompt_a, delimiter=", ")
        b = _merge_prompt_texts(core_prompt, prompt_b, delimiter=", ")
        use_a = str(active).upper() != "B"
        active_prompt = a if use_a else b
        label = "Prompt-A" if use_a else "Prompt-B"
        both = f"[A]\n{a}\n\n[B]\n{b}"
        return (active_prompt, label, both)


class XiawanQualityBoostParams:
    """Panel values for FreeU_V2 / PAG quality slots."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "enable_freeu": ("BOOLEAN", {"default": True}),
                "freeu_b1": ("FLOAT", {"default": 1.3, "min": 0.0, "max": 10.0, "step": 0.01}),
                "freeu_b2": ("FLOAT", {"default": 1.4, "min": 0.0, "max": 10.0, "step": 0.01}),
                "freeu_s1": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 10.0, "step": 0.01}),
                "freeu_s2": ("FLOAT", {"default": 0.2, "min": 0.0, "max": 10.0, "step": 0.01}),
                "enable_pag": ("BOOLEAN", {"default": False}),
                "pag_scale": ("FLOAT", {"default": 2.0, "min": 0.0, "max": 100.0, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("BOOLEAN", "FLOAT", "FLOAT", "FLOAT", "FLOAT", "BOOLEAN", "FLOAT", "STRING")
    RETURN_NAMES = ("enable_freeu", "b1", "b2", "s1", "s2", "enable_pag", "pag_scale", "advice")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, enable_freeu=True, freeu_b1=1.3, freeu_b2=1.4, freeu_s1=0.9, freeu_s2=0.2, enable_pag=False, pag_scale=2.0):
        tips = []
        if enable_freeu:
            tips.append("FreeU_V2 开启：增强结构对比，显存几乎不增。")
        if enable_pag:
            tips.append("PAG 开启：细节更锐，可能过饱和，建议 1.5~3.0。")
        if not tips:
            tips.append("质量插件均关闭：最稳、最省心。")
        return (
            _coerce_bool(enable_freeu),
            float(freeu_b1), float(freeu_b2), float(freeu_s1), float(freeu_s2),
            _coerce_bool(enable_pag), float(pag_scale), " ".join(tips),
        )


class XiawanSaveMetaPack:
    """Pack explicit metadata strings for SaveImagePlus embedding strategy."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "checkpoint_name": ("STRING", {"default": "zukiAnimeILL_v50.safetensors"}),
                "lora_syntax": ("STRING", {"default": "<lora:xiawan_pro:0.9>"}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "steps": ("INT", {"default": 28, "min": 1, "max": 200}),
                "cfg": ("FLOAT", {"default": 5.5, "min": 0.0, "max": 30.0, "step": 0.1}),
                "sampler_name": ("STRING", {"default": "dpmpp_2m"}),
                "scheduler": ("STRING", {"default": "karras"}),
                "width": ("INT", {"default": 832, "min": 64, "max": 8192}),
                "height": ("INT", {"default": 1216, "min": 64, "max": 8192}),
            },
            "optional": {
                "positive_prompt": ("STRING", {"default": "", "multiline": True, "forceInput": True}),
                "negative_prompt": ("STRING", {"default": "", "multiline": True, "forceInput": True}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("checkpoint_name", "lora_syntax", "positive_prompt", "negative_prompt", "meta_summary")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, checkpoint_name="zukiAnimeILL_v50.safetensors", lora_syntax="<lora:xiawan_pro:0.9>", seed=0, steps=28, cfg=5.5, sampler_name="dpmpp_2m", scheduler="karras", width=832, height=1216, positive_prompt="", negative_prompt=""):
        summary = (
            f"ckpt={checkpoint_name} | lora={lora_syntax} | seed={seed} | "
            f"steps={steps} cfg={cfg} | {sampler_name}+{scheduler} | {width}x{height}"
        )
        return (str(checkpoint_name), str(lora_syntax), str(positive_prompt or ""), str(negative_prompt or ""), summary)


class XiawanChangelog:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "version": ("STRING", {"default": "2.1.0-p2"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("changelog",)
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, version="2.1.0-p2"):
        text = f"""# Xiawan Workflow Changelog
## {version}
- P0: 全局分辨率、Anima提示词隔离、CN timing、导航修复、Boolean门、脏widget清理、元数据身份
- P1: I2I对齐、细化参数扩展、健康检查/配方/终点、扩图支架、放大建议
- P2: 内存档位、Seed矩阵、Prompt A/B、FreeU/PAG质量位、保存元数据包、依赖清单
## 推荐默认
zukiAnimeILL_v50 + xiawan_pro@0.9 | 832x1216 | 28/5.5/dpmpp_2m+karras | profile=8G
"""
        return (text,)


class XiawanDependencyManifest:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "include_optional": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("STRING", "BOOLEAN")
    RETURN_NAMES = ("manifest", "core_ok")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, include_optional=True):
        import folder_paths
        lines = ["# Xiawan 依赖清单", "## 核心模型"]
        ckpts = set(folder_paths.get_filename_list("checkpoints") or [])
        loras = set(folder_paths.get_filename_list("loras") or [])
        cnets = set(folder_paths.get_filename_list("controlnet") or [])
        ups = set(folder_paths.get_filename_list("upscale_models") or [])
        core = [
            ("Checkpoint", "zukiAnimeILL_v50.safetensors", ckpts),
            ("LoRA", "xiawan_pro.safetensors", loras),
        ]
        optional = [
            ("Refiner", "waiIllustriousSDXL_v140.safetensors", ckpts),
            ("ControlNet Union", "controlnetxlCNXL_xinsirCnUnionPromax.safetensors", cnets),
            ("ControlNet Tile", "noobaiXLControlnet_epsTile.safetensors", cnets),
            ("Upscale", "remacri_original.safetensors", ups),
        ]
        ok = True
        for label, name, pool in core:
            hit = name in pool
            ok = ok and hit
            lines.append(f"- [{'OK' if hit else 'MISSING'}] {label}: {name}")
        if include_optional:
            lines.append("## 可选增强")
            for label, name, pool in optional:
                lines.append(f"- [{'OK' if name in pool else 'MISS'}] {label}: {name}")
        lines.append("## 自定义节点包")
        lines.append("- comfyui_xiawan's-workflow_plugin (Xiawan*)")
        lines.append("- Impact Pack / Easy-Use / IPAdapter / Danbooru Gallery / Lora Manager / WeiLin / Mira")
        lines.append("## 质量插件位（Comfy 核心）")
        lines.append("- FreeU_V2 / PerturbedAttentionGuidance / VAEDecodeTiled / VAEEncodeTiled")
        return ("\n".join(lines), ok)


class XiawanStageCleanup:
    """Lightweight passthrough cleanup marker for stage exits (reduces VRAM_Debug clutter)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "enable_cleanup": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, image, enable_cleanup=True):
        if _coerce_bool(enable_cleanup):
            try:
                import gc, torch
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
        return (image,)


class XiawanTiledVAEParams:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "use_tiled_vae": ("BOOLEAN", {"default": True}),
                "tile_size": ("INT", {"default": 768, "min": 256, "max": 2048, "step": 64}),
                "overlap": ("INT", {"default": 64, "min": 0, "max": 512, "step": 8}),
            }
        }

    RETURN_TYPES = ("BOOLEAN", "INT", "INT", "STRING")
    RETURN_NAMES = ("use_tiled_vae", "tile_size", "overlap", "advice")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"

    def output(self, use_tiled_vae=True, tile_size=768, overlap=64):
        tile_size = max(256, int(tile_size))
        overlap = max(0, min(int(overlap), tile_size // 4))
        adv = "Tiled VAE 适合大图/低显存；tile 越大越快但更吃显存。"
        if not use_tiled_vae:
            adv = "已关闭 Tiled VAE：速度更快，大图可能 OOM。"
        return (_coerce_bool(use_tiled_vae), tile_size, overlap, adv)

NODE_CLASS_MAPPINGS = {
    "XiawanGlobalSeedManager": XiawanGlobalSeedManager,
    "XiawanBaseParams": XiawanBaseParams,
    "XiawanAnimaBaseParams": XiawanAnimaBaseParams,
    "XiawanAnimaBranchIndex": XiawanAnimaBranchIndex,
    "XiawanImageSwitch": XiawanImageSwitch,
    "XiawanLatentSwitch": XiawanLatentSwitch,
    "XiawanModelSwitch": XiawanModelSwitch,
    "XiawanFinalImageSwitch": XiawanFinalImageSwitch,
    "XiawanAnimaModelLoader": XiawanAnimaModelLoader,
    "XiawanOptionalPromptAppend": XiawanOptionalPromptAppend,
    "XiawanDanbooruGlobalPromptAppend": XiawanDanbooruGlobalPromptAppend,
    "XiawanTaggerParams": XiawanTaggerParams,
    "XiawanClearableShowText": XiawanClearableShowText,
    "XiawanFinalOutputParams": XiawanFinalOutputParams,
    "XiawanLatentUpscaleParams": XiawanLatentUpscaleParams,
    "XiawanIterativeUpscaleParams": XiawanIterativeUpscaleParams,
    "XiawanModelUpscaleParams": XiawanModelUpscaleParams,
    "XiawanTargetScaleImageGuard": XiawanTargetScaleImageGuard,
    "XiawanSingleRegionDetailerParams": XiawanSingleRegionDetailerParams,
    "XiawanControlParams": XiawanControlParams,
    "XiawanClearablePreviewImage": XiawanClearablePreviewImage,

    "XiawanBooleanToIndex": XiawanBooleanToIndex,
    "XiawanI2IPrepare": XiawanI2IPrepare,
    "XiawanBranchPromptBuild": XiawanBranchPromptBuild,
    "XiawanResolutionBroadcast": XiawanResolutionBroadcast,
    "XiawanInpaintPadScaffold": XiawanInpaintPadScaffold,
    "XiawanBatchSeedMatrix": XiawanBatchSeedMatrix,
    "XiawanPromptAB": XiawanPromptAB,
    "XiawanQualityBoostParams": XiawanQualityBoostParams,
    "XiawanSaveMetaPack": XiawanSaveMetaPack,
    "XiawanStageCleanup": XiawanStageCleanup,
    "XiawanTiledVAEParams": XiawanTiledVAEParams,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "XiawanGlobalSeedManager": "夏晚 · 全局 Seed 管理",
    "XiawanBaseParams": "夏晚 · SDXL 底图 / 主采样参数",
    "XiawanAnimaBaseParams": "夏晚 · Anima 底图参数",
    "XiawanAnimaBranchIndex": "夏晚 · SDXL / Anima 底图互斥",
    "XiawanAnimaModelLoader": "夏晚 · Anima 模型加载",
    "XiawanFinalImageSwitch": "夏晚 · 最终图像安全选择",
    "XiawanOptionalPromptAppend": "夏晚 · 可选提示词追加",
    "XiawanDanbooruGlobalPromptAppend": "夏晚 · D站全局提示词追加",
    "XiawanTaggerParams": "夏晚 · 反推 Tagger 配置",
    "XiawanClearableShowText": "夏晚 · 可清空文本预览",
    "XiawanFinalOutputParams": "夏晚 · 最终输出选择",
    "XiawanLatentUpscaleParams": "夏晚 · 1 潜空间放大参数",
    "XiawanIterativeUpscaleParams": "夏晚 · 2 迭代放大参数",
    "XiawanModelUpscaleParams": "夏晚 · 3 通用放大参数",
    "XiawanTargetScaleImageGuard": "夏晚 · 目标倍率尺寸保险",
    "XiawanSingleRegionDetailerParams": "夏晚 · 单区域细化参数",
    "XiawanControlParams": "夏晚 · 控制 / 人物 / 结构参数",
    "XiawanClearablePreviewImage": "夏晚 · 可清空图片预览",

    "XiawanBooleanToIndex": "夏晚 · 开关转索引",
    "XiawanI2IPrepare": "夏晚 · 图生图尺寸对齐",
    "XiawanBranchPromptBuild": "夏晚 · 分支提示词组装",
    "XiawanResolutionBroadcast": "夏晚 · 分辨率广播",
    "XiawanInpaintPadScaffold": "夏晚 · 扩图/局部垫图支架",
    "XiawanBatchSeedMatrix": "夏晚 · Seed 矩阵",
    "XiawanPromptAB": "夏晚 · 提示词 A/B",
    "XiawanQualityBoostParams": "夏晚 · 质量增强参数(FreeU/PAG)",
    "XiawanSaveMetaPack": "夏晚 · 保存元数据包",
    "XiawanStageCleanup": "夏晚 · 阶段清理透传",
    "XiawanTiledVAEParams": "夏晚 · Tiled VAE 参数",
}




# --- functional upgrades v2.2.0 ---
try:
    from . import func_upgrades as _xiawan_func_upgrades
except Exception:
    try:
        import func_upgrades as _xiawan_func_upgrades
    except Exception as _e:
        _xiawan_func_upgrades = None
        print("[Xiawan] func_upgrades import failed:", _e)

if _xiawan_func_upgrades is not None:
    _ov_classes, _ov_displays = _xiawan_func_upgrades.apply_overrides(globals())
    # Fix combo RETURN_TYPES evaluated before helpers were bound
    try:
        _ov_classes["XiawanBaseParams"].RETURN_TYPES = (
            "INT", "INT", "INT", "INT", "FLOAT", "FLOAT", SAMPLERS, SCHEDULERS,
            "BOOLEAN", "INT", "FLOAT", "BOOLEAN", "BOOLEAN", "BOOLEAN", "BOOLEAN", "BOOLEAN", "STRING",
        )
        _ov_classes["XiawanSingleRegionDetailerParams"].RETURN_TYPES = (
            "COMBO", "INT", "FLOAT", "FLOAT", SAMPLERS, SCHEDULERS + IMPACT_SCHEDULERS,
            "FLOAT", "FLOAT", "INT", "FLOAT", "FLOAT", "BOOLEAN", "STRING",
        )
    except Exception as _e:
        print("[Xiawan] RETURN_TYPES patch failed:", _e)
    NODE_CLASS_MAPPINGS.update(_ov_classes)
    NODE_DISPLAY_NAME_MAPPINGS.update(_ov_displays)
    # keep module-level names overridden for any direct references
    for _k, _v in _ov_classes.items():
        globals()[_k] = _v


# The workflow's third-party runtime support lives inside the Xiawan plugin.
# Only node types present in Xiawan's workflow are merged into ComfyUI.
try:
    from .xiawan_vendor_nodes import load_vendor_nodes as _load_xiawan_vendor_nodes

    _vendor_classes, _vendor_displays = _load_xiawan_vendor_nodes()
    NODE_CLASS_MAPPINGS.update(_vendor_classes)
    NODE_DISPLAY_NAME_MAPPINGS.update(_vendor_displays)
    print(f"[Xiawan] vendored workflow node types loaded: {len(_vendor_classes)}")
except Exception as _vendor_error:
    print("[Xiawan] vendored workflow node support unavailable:", _vendor_error)


_XIAWAN_BACKEND_ROUTES_REGISTERED = False


def _register_xiawan_lora_manager_backend():
    """Register vendored LoRA Manager routes once ComfyUI's app is available."""

    global _XIAWAN_BACKEND_ROUTES_REGISTERED
    if _XIAWAN_BACKEND_ROUTES_REGISTERED:
        return

    try:
        from .vendor.lora_manager.py.lora_manager import LoraManager as _LoraManager
    except Exception as _backend_import_error:
        print("[Xiawan] vendored LoRA Manager backend unavailable:", _backend_import_error)
        return

    try:
        _LoraManager.add_routes()
        _XIAWAN_BACKEND_ROUTES_REGISTERED = True
        print("[Xiawan] vendored LoRA Manager backend routes loaded")
    except Exception as _backend_error:
        print("[Xiawan] vendored LoRA Manager backend routes unavailable:", _backend_error)


_register_xiawan_lora_manager_backend()


_XIAWAN_WEILIN_BACKEND_REGISTERED = False


def _register_xiawan_weilin_backend():
    """Register the vendored WeiLin prompt editor API without extra nodes."""

    global _XIAWAN_WEILIN_BACKEND_REGISTERED
    if _XIAWAN_WEILIN_BACKEND_REGISTERED:
        return

    try:
        from .vendor.weilin_tools.app.server import prompt_server as _weilin_server

        del _weilin_server
        _XIAWAN_WEILIN_BACKEND_REGISTERED = True
        print("[Xiawan] vendored WeiLin prompt editor backend routes loaded")
    except Exception as _weilin_backend_error:
        print(
            "[Xiawan] vendored WeiLin prompt editor backend unavailable:",
            _weilin_backend_error,
        )


_register_xiawan_weilin_backend()


