# -*- coding: utf-8 -*-
"""Functional upgrades for Xiawan workflow plugin (v2.2.0-func)."""
from __future__ import annotations

import gc

_coerce_bool = None
_value = None
_merge_prompt_texts = None
_MISSING = object()
SAMPLERS = []
SCHEDULERS = []
IMPACT_SCHEDULERS = []
BASE_IMAGE_MODES = ["自采样", "图生图直通", "图生图重采样"]
_bbox_models = None


def apply_overrides(ns: dict):
    global _coerce_bool, _value, _merge_prompt_texts, _MISSING
    global SAMPLERS, SCHEDULERS, IMPACT_SCHEDULERS, BASE_IMAGE_MODES, _bbox_models
    _coerce_bool = ns["_coerce_bool"]
    _value = ns["_value"]
    _merge_prompt_texts = ns.get("_merge_prompt_texts", lambda a, b, delimiter=", ": ", ".join([x for x in [a, b] if x]))
    _MISSING = ns["_MISSING"]
    SAMPLERS = ns["SAMPLERS"]
    SCHEDULERS = ns["SCHEDULERS"]
    IMPACT_SCHEDULERS = ns.get("IMPACT_SCHEDULERS", [])
    BASE_IMAGE_MODES = ns.get("BASE_IMAGE_MODES", BASE_IMAGE_MODES)
    _bbox_models = ns.get("_bbox_models")
    classes = {
        "XiawanModelSwitch": XiawanModelSwitch,
        "XiawanVRAMModelGuard": XiawanVRAMModelGuard,
        "XiawanRuntimeMemoryRelease": XiawanRuntimeMemoryRelease,
        "XiawanHighResPerformanceProfile": XiawanHighResPerformanceProfile,
        "XiawanImageVRAMGuard": XiawanImageVRAMGuard,
        "XiawanLatentVRAMGuard": XiawanLatentVRAMGuard,
        "XiawanHighResModelPreflight": XiawanHighResModelPreflight,
        "XiawanBaseParams": XiawanBaseParams,
        "XiawanBatchSeedMatrix": XiawanBatchSeedMatrix,
        "XiawanPromptAB": XiawanPromptAB,
        "XiawanTiledVAEParams": XiawanTiledVAEParams,
        "XiawanQualityBoostParams": XiawanQualityBoostParams,
        "XiawanSaveMetaPack": XiawanSaveMetaPack,
        "XiawanInpaintPadScaffold": XiawanInpaintPadScaffold,
        "XiawanSingleRegionDetailerParams": XiawanSingleRegionDetailerParams,
        "XiawanIntSwitch": XiawanIntSwitch,
        "XiawanStringSwitch": XiawanStringSwitch,
        "XiawanAnyVAEDecode": XiawanAnyVAEDecode,
        "XiawanAnyVAEEncode": XiawanAnyVAEEncode,
    }
    displays = {
        "XiawanModelSwitch": "夏晚 · 模型开关(双契约)",
        "XiawanVRAMModelGuard": "夏晚 · 采样前显存整理",
        "XiawanRuntimeMemoryRelease": "夏晚 · 输出后显存回收",
        "XiawanHighResPerformanceProfile": "夏晚 · 高分辨率性能配置",
        "XiawanImageVRAMGuard": "夏晚 · 图像阶段显存整理",
        "XiawanLatentVRAMGuard": "夏晚 · 潜空间阶段显存整理",
        "XiawanHighResModelPreflight": "夏晚 · 高分辨率模型预检",
        "XiawanBaseParams": "夏晚 · SDXL 底图 / 主采样参数",
        "XiawanBatchSeedMatrix": "夏晚 · Seed 矩阵(可应用batch)",
        "XiawanPromptAB": "夏晚 · 提示词 A/B(可注入)",
        "XiawanTiledVAEParams": "夏晚 · Tiled VAE(真路径参数)",
        "XiawanQualityBoostParams": "夏晚 · 质量增强(主采样/可选后级)",
        "XiawanSaveMetaPack": "夏晚 · 保存元数据包",
        "XiawanInpaintPadScaffold": "夏晚 · 扩图蒙版(可选)",
        "XiawanSingleRegionDetailerParams": "夏晚 · 单区域细化参数",
        "XiawanIntSwitch": "夏晚 · 整数开关",
        "XiawanStringSwitch": "夏晚 · 文本开关",
        "XiawanAnyVAEDecode": "夏晚 · VAE解码(可选Tiled)",
        "XiawanAnyVAEEncode": "夏晚 · VAE编码(可选Tiled)",
    }
    # Fix RETURN_TYPES after SAMPLERS bound
    try:
        XiawanBaseParams.RETURN_TYPES = (
            "INT", "INT", "INT", "INT", "FLOAT", "FLOAT", SAMPLERS, SCHEDULERS,
            "BOOLEAN", "INT", "FLOAT", "BOOLEAN", "BOOLEAN", "BOOLEAN", "BOOLEAN", "BOOLEAN", "STRING",
        )
        XiawanSingleRegionDetailerParams.RETURN_TYPES = (
            "COMBO", "INT", "FLOAT", "FLOAT", SAMPLERS, SCHEDULERS + IMPACT_SCHEDULERS,
            "FLOAT", "FLOAT", "INT", "FLOAT", "FLOAT", "BOOLEAN", "STRING",
        )
    except Exception:
        pass
    return classes, displays


class XiawanModelSwitch:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "index": ("*", {"forceInput": True}),
                "switch": ("BOOLEAN", {"forceInput": True}),
                "value0": ("MODEL", {"lazy": True}),
                "value1": ("MODEL", {"lazy": True}),
                "on_false": ("MODEL", {"lazy": True}),
                "on_true": ("MODEL", {"lazy": True}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "prompt": "PROMPT",
            },
        }
    RETURN_TYPES = ("MODEL",)
    RETURN_NAMES = ("model",)
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"
    @staticmethod
    def _safe_index(index=None, switch=None):
        if switch is not None and switch is not _MISSING:
            return 1 if _coerce_bool(switch) else 0
        if isinstance(index, bool):
            return 1 if index else 0
        try:
            return 1 if int(index) == 1 else 0
        except Exception:
            return 1 if _coerce_bool(index) else 0

    @staticmethod
    def _is_missing(value):
        # Defaults were created before apply_overrides replaces the module
        # sentinel. A bare object is therefore the only reliable legacy
        # missing-input marker at runtime.
        return value is _MISSING or type(value) is object
    @staticmethod
    def _connected_branch_names(prompt, unique_id):
        """Read the saved prompt so lazy evaluation follows the graph contract."""
        if isinstance(prompt, list):
            prompt = prompt[0] if prompt else None
        if isinstance(unique_id, list):
            unique_id = unique_id[0] if unique_id else None
        if not isinstance(prompt, dict):
            return set()
        node = prompt.get(str(unique_id)) or prompt.get(unique_id)
        if not isinstance(node, dict):
            return set()
        inputs = node.get("inputs")
        return set(inputs) if isinstance(inputs, dict) else set()

    def check_lazy_status(self, index=None, switch=None, value0=_MISSING, value1=_MISSING,
                          on_false=_MISSING, on_true=_MISSING, unique_id=None, prompt=None, **kwargs):
        selected = self._safe_index(index, switch)
        connected = self._connected_branch_names(prompt, unique_id)
        preferred = ("on_false", "value0") if selected == 0 else ("on_true", "value1")
        for name in preferred:
            if name in connected:
                return [name]
        return [preferred[0]]
    def output(self, index=None, switch=None, value0=_MISSING, value1=_MISSING,
               on_false=_MISSING, on_true=_MISSING, unique_id=None, prompt=None, **kwargs):
        v0 = value0 if not self._is_missing(value0) else on_false
        v1 = value1 if not self._is_missing(value1) else on_true
        if self._is_missing(v0) or v0 is None:
            return (v1,)
        if self._is_missing(v1) or v1 is None:
            return (v0,)
        if self._safe_index(index, switch) == 1:
            return (v1,)
        return (v0,)


def _cuda_free_mb():
    try:
        import torch

        if torch.cuda.is_available():
            free_bytes, _ = torch.cuda.mem_get_info()
            return int(free_bytes // (1024 * 1024))
    except Exception:
        pass
    return -1


def _release_cuda_cache(gc_collect=True, empty_cache=True, unload_models=False):
    actions = []
    if gc_collect:
        gc.collect()
        actions.append("gc")
    if unload_models:
        try:
            import comfy.model_management

            comfy.model_management.unload_all_models()
            actions.append("unload_models")
        except Exception as exc:
            actions.append(f"unload_models_skipped:{type(exc).__name__}")
    if empty_cache:
        try:
            import comfy.model_management as model_management

            model_management.soft_empty_cache()
            actions.append("soft_empty_cache")
        except Exception as exc:
            actions.append(f"soft_empty_cache_skipped:{type(exc).__name__}")
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                actions.append("empty_cache")
        except Exception as exc:
            actions.append(f"empty_cache_skipped:{type(exc).__name__}")
    return ", ".join(actions) if actions else "no_action"


class XiawanVRAMModelGuard:
    """Pass a model through while reclaiming cache only under memory pressure."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "enabled": ("BOOLEAN", {"default": True}),
                "gc_collect": ("BOOLEAN", {"default": True}),
                "empty_cache": ("BOOLEAN", {"default": True}),
                "minimum_free_vram_mb": ("INT", {"default": 2048, "min": 0, "max": 32768, "step": 128}),
            }
        }

    RETURN_TYPES = ("MODEL", "INT", "INT", "STRING")
    RETURN_NAMES = ("model", "free_before_mb", "free_after_mb", "report")
    FUNCTION = "guard"
    CATEGORY = "Xiawan/Performance"

    def guard(self, model, enabled=True, gc_collect=True, empty_cache=True, minimum_free_vram_mb=2048):
        before = _cuda_free_mb()
        threshold = max(0, int(minimum_free_vram_mb))
        should_release = _coerce_bool(enabled) and (before < 0 or threshold == 0 or before < threshold)
        actions = _release_cuda_cache(gc_collect, empty_cache) if should_release else "threshold_met"
        after = _cuda_free_mb()
        report = f"before={before}MB | threshold={threshold}MB | action={actions} | after={after}MB"
        return (model, before, after, report)


class XiawanRuntimeMemoryRelease:
    """Release disposable runtime cache after the final image has been produced."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "enabled": ("BOOLEAN", {"default": True}),
                "gc_collect": ("BOOLEAN", {"default": True}),
                "empty_cache": ("BOOLEAN", {"default": True}),
                "unload_models": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("IMAGE", "INT", "STRING")
    RETURN_NAMES = ("image", "free_after_mb", "report")
    FUNCTION = "release"
    CATEGORY = "Xiawan/Performance"

    def release(self, image, enabled=True, gc_collect=True, empty_cache=True, unload_models=False):
        before = _cuda_free_mb()
        actions = (
            _release_cuda_cache(gc_collect, empty_cache, unload_models)
            if _coerce_bool(enabled)
            else "disabled"
        )
        after = _cuda_free_mb()
        return (image, after, f"before={before}MB | action={actions} | after={after}MB")


class XiawanHighResPerformanceProfile:
    """Single source of truth for the high-resolution upscale/detail path."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "分块编码": ("BOOLEAN", {"default": True}),
                "分块解码": ("BOOLEAN", {"default": True}),
                "阶段缓存整理": ("BOOLEAN", {"default": True}),
                "最低可用显存(MB)": ("INT", {"default": 3072, "min": 0, "max": 32768, "step": 128}),
                "瓦片大小": ("INT", {"default": 128, "min": 64, "max": 2048, "step": 64}),
                "重叠": ("INT", {"default": 16, "min": 0, "max": 512, "step": 8}),
            }
        }

    RETURN_TYPES = ("BOOLEAN", "BOOLEAN", "BOOLEAN", "INT", "INT", "INT", "STRING")
    RETURN_NAMES = (
        "tiled_encode",
        "tiled_decode",
        "stage_cleanup",
        "minimum_free_vram_mb",
        "tile_size",
        "overlap",
        "profile_report",
    )
    FUNCTION = "output"
    CATEGORY = "Xiawan/Performance"

    def output(
        self,
        分块编码=True,
        分块解码=True,
        阶段缓存整理=True,
        最低可用显存MB=3072,
        瓦片大小=128,
        重叠=16,
        **kwargs,
    ):
        tiled_encode = _coerce_bool(_value(kwargs, "分块编码", "tiled_encode", default=分块编码))
        tiled_decode = _coerce_bool(_value(kwargs, "分块解码", "tiled_decode", default=分块解码))
        cleanup = _coerce_bool(_value(kwargs, "阶段缓存整理", "stage_cleanup", default=阶段缓存整理))
        minimum_free = max(0, int(_value(kwargs, "最低可用显存(MB)", "minimum_free_vram_mb", default=最低可用显存MB)))
        tile_size = max(64, int(_value(kwargs, "瓦片大小", "tile_size", default=瓦片大小)))
        overlap = max(0, min(int(_value(kwargs, "重叠", "overlap", default=重叠)), tile_size // 4))
        report = (
            f"tiled_encode={tiled_encode} | tiled_decode={tiled_decode} | "
            f"cleanup={cleanup} | min_free={minimum_free}MB | tile={tile_size}/{overlap}"
        )
        return (tiled_encode, tiled_decode, cleanup, minimum_free, tile_size, overlap, report)


class XiawanImageVRAMGuard:
    """Pass an image onward and unload models only when memory is pressured."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "enabled": ("BOOLEAN", {"default": True, "forceInput": True}),
                "minimum_free_vram_mb": ("INT", {"default": 3072, "min": 0, "max": 32768, "step": 128, "forceInput": True}),
            }
        }

    RETURN_TYPES = ("IMAGE", "INT", "INT", "STRING")
    RETURN_NAMES = ("image", "free_before_mb", "free_after_mb", "report")
    FUNCTION = "guard"
    CATEGORY = "Xiawan/Performance"

    def guard(self, image, enabled=True, minimum_free_vram_mb=3072):
        before = _cuda_free_mb()
        threshold = max(0, int(minimum_free_vram_mb))
        should_release = _coerce_bool(enabled) and (
            before < 0 or threshold == 0 or before < threshold
        )
        actions = (
            _release_cuda_cache(True, True, unload_models=True)
            if should_release
            else ("threshold_met" if _coerce_bool(enabled) else "disabled")
        )
        after = _cuda_free_mb()
        pressure = "under_threshold" if after >= 0 and after < threshold else "threshold_met"
        report = f"before={before}MB | action={actions} | after={after}MB | {pressure}:{threshold}MB"
        return (image, before, after, report)


class XiawanLatentVRAMGuard:
    """Offload sampler models before a VAE decode consumes high-resolution VRAM."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "latent": ("LATENT",),
                "enabled": ("BOOLEAN", {"default": True, "forceInput": True}),
                "minimum_free_vram_mb": ("INT", {"default": 3072, "min": 0, "max": 32768, "step": 128, "forceInput": True}),
            }
        }

    RETURN_TYPES = ("LATENT", "INT", "INT", "STRING")
    RETURN_NAMES = ("latent", "free_before_mb", "free_after_mb", "report")
    FUNCTION = "guard"
    CATEGORY = "Xiawan/Performance"

    def guard(self, latent, enabled=True, minimum_free_vram_mb=3072):
        before = _cuda_free_mb()
        threshold = max(0, int(minimum_free_vram_mb))
        should_release = _coerce_bool(enabled) and (
            before < 0 or threshold == 0 or before < threshold
        )
        actions = (
            _release_cuda_cache(True, True, unload_models=True)
            if should_release
            else ("threshold_met" if _coerce_bool(enabled) else "disabled")
        )
        after = _cuda_free_mb()
        pressure = "under_threshold" if after >= 0 and after < threshold else "threshold_met"
        report = f"before={before}MB | action={actions} | after={after}MB | {pressure}:{threshold}MB"
        return (latent, before, after, report)


class XiawanHighResModelPreflight:
    """Prepare a high-memory stage without unloading when memory is sufficient."""

    CONSERVATIVE_THRESHOLD_MB = 3072

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "enabled": ("BOOLEAN", {"default": True}),
                "unload_models": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("MODEL", "INT", "INT", "STRING")
    RETURN_NAMES = ("model", "free_before_mb", "free_after_mb", "report")
    FUNCTION = "guard"
    CATEGORY = "Xiawan/Performance"

    def guard(self, model, enabled=True, unload_models=True):
        before = _cuda_free_mb()
        should_unload = _coerce_bool(unload_models) and (
            before < 0 or before < self.CONSERVATIVE_THRESHOLD_MB
        )
        actions = (
            _release_cuda_cache(True, True, unload_models=should_unload)
            if _coerce_bool(enabled)
            else "disabled"
        )
        after = _cuda_free_mb()
        return (
            model,
            before,
            after,
            f"before={before}MB | threshold={self.CONSERVATIVE_THRESHOLD_MB}MB | "
            f"unload={should_unload} | action={actions} | after={after}MB",
        )


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
                "I2I自动降噪": ("BOOLEAN", {"default": True}),
                "I2I推荐降噪": ("FLOAT", {"default": 0.45, "min": 0.05, "max": 1.0, "step": 0.01}),
            },
            "optional": {
                "width": ("INT", {"default": 832, "min": 64, "max": 8192, "step": 8, "forceInput": True}),
                "height": ("INT", {"default": 1216, "min": 64, "max": 8192, "step": 8, "forceInput": True}),
            },
        }
    RETURN_TYPES = ("INT", "INT", "INT", "INT", "FLOAT", "FLOAT", SAMPLERS, SCHEDULERS, "BOOLEAN", "INT", "FLOAT", "BOOLEAN", "BOOLEAN", "BOOLEAN", "BOOLEAN", "BOOLEAN", "STRING")
    RETURN_NAMES = ("width", "height", "batch_size", "steps", "cfg", "main_denoise", "sampler_name", "scheduler", "refiner_enabled", "refiner_steps", "refiner_denoise", "img2img_direct_enabled", "img2img_resample_enabled", "save_image", "img2img_caption_enabled", "skip_base_sample", "mode_advice")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"
    def output(self, **kwargs):
        width = int(_value(kwargs, "width", default=832) or 832)
        height = int(_value(kwargs, "height", default=1216) or 1216)
        batch_size = _value(kwargs, "批次数量", "batch_size", default=1)
        steps = _value(kwargs, "步数", "steps", default=28)
        cfg = _value(kwargs, "CFG", "cfg", default=5.5)
        main_denoise = float(_value(kwargs, "主采样降噪", "main_denoise", default=1.0))
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
        auto_denoise = _coerce_bool(_value(kwargs, "I2I自动降噪", "i2i_auto_denoise", default=True))
        i2i_denoise = float(_value(kwargs, "I2I推荐降噪", "i2i_recommended_denoise", default=0.45))
        mode_advice = "T2I 自采样：降噪保持 1.0。"
        if img2img_resample_enabled:
            if auto_denoise and main_denoise >= 0.999:
                main_denoise = i2i_denoise
                mode_advice = f"I2I 重采样：已自动将降噪从 1.0 调整为 {i2i_denoise:.2f}。"
            else:
                mode_advice = f"I2I 重采样：使用当前降噪 {main_denoise:.2f}（推荐 0.35~0.55）。"
        elif img2img_direct_enabled:
            mode_advice = "I2I 直通：最终底图直接使用输入图；主采样不作为底图出口。"
        skip_base_sample = bool(img2img_direct_enabled)
        return (width, height, batch_size, steps, cfg, main_denoise, sampler_name, scheduler, refiner_enabled, refiner_steps, refiner_denoise, img2img_direct_enabled, img2img_resample_enabled, save_image, img2img_caption_enabled, skip_base_sample, mode_advice)


class XiawanEndpointStatus:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "base_on": ("BOOLEAN", {"default": True, "forceInput": True}),
                "latent_on": ("BOOLEAN", {"default": False, "forceInput": True}),
                "iter_on": ("BOOLEAN", {"default": False, "forceInput": True}),
                "model_on": ("BOOLEAN", {"default": False, "forceInput": True}),
                "detailer_on": ("BOOLEAN", {"default": False, "forceInput": True}),
            },
            "optional": {
                "detailer_face_on": ("BOOLEAN", {"default": False, "forceInput": True}),
                "detailer_eye_on": ("BOOLEAN", {"default": False, "forceInput": True}),
                "detailer_hand_on": ("BOOLEAN", {"default": False, "forceInput": True}),
                "detailer_foot_on": ("BOOLEAN", {"default": False, "forceInput": True}),
                "detailer_other_on": ("BOOLEAN", {"default": False, "forceInput": True}),
            },
        }
    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("endpoint_label", "endpoint_index")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"
    def output(self, base_on=True, latent_on=False, iter_on=False, model_on=False, detailer_on=False, detailer_face_on=False, detailer_eye_on=False, detailer_hand_on=False, detailer_foot_on=False, detailer_other_on=False):
        children = any(_coerce_bool(x) for x in (detailer_face_on, detailer_eye_on, detailer_hand_on, detailer_foot_on, detailer_other_on))
        detailer_effective = _coerce_bool(detailer_on) and children
        stages = [(0, _coerce_bool(base_on), "0 底图"), (1, _coerce_bool(latent_on), "1 潜空间放大"), (2, _coerce_bool(iter_on), "2 迭代放大"), (3, _coerce_bool(model_on), "3 通用放大"), (4, detailer_effective, "4 部位细化")]
        endpoint = stages[0]
        for s in stages:
            if s[1]:
                endpoint = s
        notes = []
        if _coerce_bool(detailer_on) and not children:
            notes.append("细化总开关已开但无子模块(4-a~4-e)，已回退到更早阶段")
        label = f"当前终点：{endpoint[2]} (index={endpoint[0]})"
        if notes:
            label += " | " + "；".join(notes)
        return (label, endpoint[0])


class XiawanBatchSeedMatrix:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "base_seed": ("INT", {"default": 123456789, "min": 0, "max": 0xffffffffffffffff}),
            "count": ("INT", {"default": 4, "min": 1, "max": 16}),
            "mode": (["offset", "random"], {"default": "offset"}),
            "offset_step": ("INT", {"default": 1, "min": 1, "max": 100000}),
            "启用应用到批次": ("BOOLEAN", {"default": False}),
        }}
    RETURN_TYPES = ("INT", "INT", "INT", "INT", "INT", "STRING", "BOOLEAN")
    RETURN_NAMES = ("seed_0", "seed_1", "seed_2", "seed_3", "batch_size", "seed_matrix_text", "apply_enabled")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"
    def output(self, base_seed=123456789, count=4, mode="offset", offset_step=1, **kwargs):
        import random
        base = int(base_seed) & 0xffffffffffffffff
        count = max(1, min(16, int(count)))
        apply_enabled = _coerce_bool(_value(kwargs, "启用应用到批次", "apply_enabled", default=False))
        if mode == "random":
            rng = random.Random(base)
            seeds = [rng.randint(0, 0xffffffffffffffff) for _ in range(count)]
        else:
            step = max(1, int(offset_step))
            seeds = [(base + i * step) & 0xffffffffffffffff for i in range(count)]
        while len(seeds) < 4:
            seeds.append(seeds[-1] if seeds else base)
        applied_seed = seeds[0] if apply_enabled else base
        batch_size = count if apply_enabled else 1
        status = "已应用到 batch（同次运行多图，seed 递增）" if apply_enabled else "仅预览（未改 batch；打开「启用应用到批次」生效）"
        text = status + "\n" + "\n".join(f"S{i}: {s}" for i, s in enumerate(seeds[:count]))
        return (int(applied_seed), int(seeds[1]), int(seeds[2]), int(seeds[3]), int(batch_size), text, apply_enabled)


class XiawanPromptAB:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt_a": ("STRING", {"default": "", "multiline": True}),
                "prompt_b": ("STRING", {"default": "", "multiline": True}),
                "active": (["A", "B"], {"default": "A"}),
                "启用注入主链": ("BOOLEAN", {"default": False}),
            },
            "optional": {"core_prompt": ("STRING", {"default": "", "multiline": True, "forceInput": True})},
        }
    RETURN_TYPES = ("STRING", "STRING", "STRING", "BOOLEAN")
    RETURN_NAMES = ("active_prompt", "label", "both_preview", "inject_enabled")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"
    def output(self, prompt_a="", prompt_b="", active="A", core_prompt="", **kwargs):
        inject = _coerce_bool(_value(kwargs, "启用注入主链", "inject_enabled", default=False))
        a = _merge_prompt_texts(core_prompt, prompt_a, delimiter=", ")
        b = _merge_prompt_texts(core_prompt, prompt_b, delimiter=", ")
        use_a = str(active).upper() != "B"
        variant = a if use_a else b
        active_prompt = variant if inject else (core_prompt or variant)
        label = ("Prompt-A" if use_a else "Prompt-B") + (" · 已注入" if inject else " · 仅预览")
        both = f"[{label}]\n[A]\n{a}\n\n[B]\n{b}"
        return (active_prompt, label, both, inject)


class XiawanMemoryProfile:
    PROFILES = ["4G", "8G", "12G", "24G"]
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "profile": (cls.PROFILES, {"default": "8G"}),
            "应用建议到TiledVAE": ("BOOLEAN", {"default": True}),
        }}
    RETURN_TYPES = ("INT", "INT", "INT", "BOOLEAN", "INT", "BOOLEAN", "BOOLEAN", "BOOLEAN", "STRING")
    RETURN_NAMES = ("width", "height", "batch_size", "use_tiled_vae", "tile_size", "enable_freeu", "enable_pag", "enable_detailer_default", "advice")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"
    def output(self, profile="8G", **kwargs):
        apply_tiled = _coerce_bool(_value(kwargs, "应用建议到TiledVAE", "apply_tiled", default=True))
        table = {
            "4G": (768, 1152, 1, True, 512, False, False, False, "【顾问档】4G：建议仅底图；关 FreeU/PAG/细化；Tiled 开。"),
            "8G": (832, 1216, 1, True, 768, True, False, False, "【顾问档·本机推荐】8G：832x1216；FreeU 可开，PAG 慎开；细化后开。"),
            "12G": (896, 1344, 1, True, 896, True, True, True, "【顾问档】12G：可开 FreeU+PAG，细化可默认开脸。"),
            "24G": (1024, 1536, 2, False, 1024, True, True, True, "【顾问档】24G：高分辨率+batch2，质量插件可全开。"),
        }
        w, h, b, tiled, tile, freeu, pag, det, advice = table.get(profile, table["8G"])
        if not apply_tiled:
            advice += " | 已关闭「应用建议到TiledVAE」。"
            tiled = False
        return (w, h, b, bool(tiled), tile, freeu, pag, det, advice)


class XiawanTiledVAEParams:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "use_tiled_vae": ("BOOLEAN", {"default": True}),
                "tile_size": ("INT", {"default": 768, "min": 256, "max": 2048, "step": 64}),
                "overlap": ("INT", {"default": 64, "min": 0, "max": 512, "step": 8}),
            },
            "optional": {
                "profile_use_tiled": ("BOOLEAN", {"default": True, "forceInput": True}),
                "profile_tile_size": ("INT", {"default": 768, "forceInput": True}),
            },
        }
    RETURN_TYPES = ("BOOLEAN", "INT", "INT", "STRING")
    RETURN_NAMES = ("use_tiled_vae", "tile_size", "overlap", "advice")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"
    def output(self, use_tiled_vae=True, tile_size=768, overlap=64, profile_use_tiled=None, profile_tile_size=None):
        use = _coerce_bool(use_tiled_vae)
        ts = max(256, int(tile_size))
        if profile_use_tiled is not None and _coerce_bool(profile_use_tiled) and use and profile_tile_size is not None:
            ts = max(256, int(profile_tile_size))
        overlap = max(0, min(int(overlap), ts // 4))
        adv = "Tiled VAE 开启：主路径将使用 tiled 编解码。" if use else "Tiled VAE 关闭：走普通编解码。"
        return (use, ts, overlap, adv)


class XiawanQualityBoostParams:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "enable_freeu": ("BOOLEAN", {"default": True}),
            "freeu_b1": ("FLOAT", {"default": 1.3, "min": 0.0, "max": 10.0, "step": 0.01}),
            "freeu_b2": ("FLOAT", {"default": 1.4, "min": 0.0, "max": 10.0, "step": 0.01}),
            "freeu_s1": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 10.0, "step": 0.01}),
            "freeu_s2": ("FLOAT", {"default": 0.2, "min": 0.0, "max": 10.0, "step": 0.01}),
            "enable_pag": ("BOOLEAN", {"default": False}),
            "pag_scale": ("FLOAT", {"default": 2.0, "min": 0.0, "max": 100.0, "step": 0.01}),
            "后级使用质量模型": ("BOOLEAN", {"default": False}),
        }}
    RETURN_TYPES = ("BOOLEAN", "FLOAT", "FLOAT", "FLOAT", "FLOAT", "BOOLEAN", "FLOAT", "STRING", "BOOLEAN")
    RETURN_NAMES = ("enable_freeu", "b1", "b2", "s1", "s2", "enable_pag", "pag_scale", "advice", "apply_to_post")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"
    def output(self, enable_freeu=True, freeu_b1=1.3, freeu_b2=1.4, freeu_s1=0.9, freeu_s2=0.2, enable_pag=False, pag_scale=2.0, **kwargs):
        apply_post = _coerce_bool(_value(kwargs, "后级使用质量模型", "apply_to_post", default=False))
        tips = []
        if enable_freeu:
            tips.append("FreeU_V2：主采样开启。")
        if enable_pag:
            tips.append("PAG：主采样开启（建议 1.5~3.0）。")
        tips.append("后级改用底图质量模型路径。" if apply_post else "默认：质量增强仅主采样；后级仍用 Refiner 检查点。")
        return (_coerce_bool(enable_freeu), float(freeu_b1), float(freeu_b2), float(freeu_s1), float(freeu_s2), _coerce_bool(enable_pag), float(pag_scale), " ".join(tips), apply_post)


class XiawanSaveMetaPack:
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
                "loaded_loras": ("STRING", {"default": "", "forceInput": True}),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("checkpoint_name", "lora_syntax", "positive_prompt", "negative_prompt", "meta_summary")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"
    @staticmethod
    def _prompt_node(prompt, node_id):
        prompt_obj = prompt[0] if isinstance(prompt, list) and prompt else prompt
        if not isinstance(prompt_obj, dict):
            return {}
        node = prompt_obj.get(str(node_id)) or prompt_obj.get(node_id)
        return node.get("inputs", {}) if isinstance(node, dict) else {}

    @staticmethod
    def _workflow_info(extra_pnginfo):
        info = extra_pnginfo[0] if isinstance(extra_pnginfo, list) and extra_pnginfo else extra_pnginfo
        return info.get("workflow") if isinstance(info, dict) else None

    @classmethod
    def _anima_enabled(cls, prompt, extra_pnginfo):
        workflow = cls._workflow_info(extra_pnginfo)
        if isinstance(workflow, dict):
            for node in workflow.get("nodes", []):
                if not isinstance(node, dict) or node.get("type") not in ("GroupIgnoreManager", "GroupMuteManager"):
                    continue
                for group in (node.get("properties") or {}).get("groups", []):
                    if isinstance(group, dict) and group.get("group_name") == "0-ii anima底图":
                        return bool(group.get("enabled", False))
        values = cls._prompt_node(prompt, 257)
        anima = values.get("anima_enabled")
        return bool(anima) if isinstance(anima, bool) else False

    @staticmethod
    def _first_value(values, *names):
        for name in names:
            value = values.get(name) if isinstance(values, dict) else None
            if isinstance(value, (list, tuple)):
                continue
            if value is not None:
                return value
        return None

    @classmethod
    def _runtime_values(cls, prompt, extra_pnginfo):
        anima = cls._anima_enabled(prompt, extra_pnginfo)
        params = cls._prompt_node(prompt, 255 if anima else 113)
        model_node = cls._prompt_node(prompt, 258 if anima else 8)
        lora_node = cls._prompt_node(prompt, 261 if anima else 10)
        checkpoint = cls._first_value(model_node, "diffusion_model" if anima else "ckpt_name")
        sampler = cls._first_value(params, "采样器", "sampler_name")
        scheduler = cls._first_value(params, "调度器", "scheduler")
        steps = cls._first_value(params, "步数", "steps")
        cfg = cls._first_value(params, "CFG", "cfg")
        width = cls._first_value(params, "宽度", "width")
        height = cls._first_value(params, "高度", "height")
        lora = cls._first_value(lora_node, "text")
        return checkpoint, lora, steps, cfg, sampler, scheduler, width, height

    def output(self, checkpoint_name="", lora_syntax="", seed=0, steps=28, cfg=5.5, sampler_name="", scheduler="", width=832, height=1216, positive_prompt="", negative_prompt="", loaded_loras="", prompt=None, extra_pnginfo=None):
        runtime = self._runtime_values(prompt, extra_pnginfo)
        checkpoint_name = runtime[0] or checkpoint_name or "unselected"
        loaded_loras = str(loaded_loras or runtime[1] or "").strip()
        lora_out = loaded_loras or str(lora_syntax or "")
        steps = runtime[2] if runtime[2] is not None else steps
        cfg = runtime[3] if runtime[3] is not None else cfg
        sampler_name = runtime[4] or sampler_name or "unselected"
        scheduler = runtime[5] or scheduler or "unselected"
        width = runtime[6] if runtime[6] is not None else width
        height = runtime[7] if runtime[7] is not None else height
        summary = f"ckpt={checkpoint_name} | lora={lora_out} | seed={seed} | steps={steps} cfg={cfg} | {sampler_name}+{scheduler} | {width}x{height}"
        return (str(checkpoint_name), lora_out, str(positive_prompt or ""), str(negative_prompt or ""), summary)


class XiawanInpaintPadScaffold:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "image": ("IMAGE",),
            "启用扩图蒙版": ("BOOLEAN", {"default": False}),
            "pad_left": ("INT", {"default": 0, "min": 0, "max": 4096, "step": 8}),
            "pad_right": ("INT", {"default": 0, "min": 0, "max": 4096, "step": 8}),
            "pad_top": ("INT", {"default": 0, "min": 0, "max": 4096, "step": 8}),
            "pad_bottom": ("INT", {"default": 0, "min": 0, "max": 4096, "step": 8}),
            "pad_color": ("INT", {"default": 0, "min": 0, "max": 255, "step": 1}),
        }}
    RETURN_TYPES = ("IMAGE", "MASK", "INT", "INT", "BOOLEAN", "STRING")
    RETURN_NAMES = ("image", "outpaint_mask", "width", "height", "use_mask", "advice")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"
    def output(self, image, pad_left=0, pad_right=0, pad_top=0, pad_bottom=0, pad_color=0, **kwargs):
        enable = _coerce_bool(_value(kwargs, "启用扩图蒙版", "enable", default=False))
        b, h, w, c = image.shape
        pl, pr, pt, pb = int(pad_left), int(pad_right), int(pad_top), int(pad_bottom)
        if not enable or (pl + pr + pt + pb) == 0:
            mask = image.new_zeros((b, h, w))
            return (image, mask, int(w), int(h), False, "扩图蒙版未启用或 pad=0：不影响主 I2I 链。")
        nh, nw = h + pt + pb, w + pl + pr
        color = float(pad_color) / 255.0
        out = image.new_zeros((b, nh, nw, c))
        out[..., :] = color
        out[:, pt:pt + h, pl:pl + w, :] = image
        mask = image.new_ones((b, nh, nw))
        mask[:, pt:pt + h, pl:pl + w] = 0.0
        return (out, mask, nw, nh, True, f"扩图启用：画布 {nw}x{nh}，仅 pad 区域重绘。请配合 I2I 重采样。")


class XiawanModelHealthCheck:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "checkpoint_name": ("STRING", {"default": "zukiAnimeILL_v50.safetensors"}),
                "lora_name": ("STRING", {"default": "xiawan_pro.safetensors"}),
            },
            "optional": {"extra_files": ("STRING", {"default": "", "multiline": True})},
        }
    RETURN_TYPES = ("STRING", "BOOLEAN")
    RETURN_NAMES = ("report", "ok")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"
    def output(self, checkpoint_name="zukiAnimeILL_v50.safetensors", lora_name="xiawan_pro.safetensors", extra_files=""):
        import folder_paths
        lines, ok = [], True
        ckpts = set(folder_paths.get_filename_list("checkpoints") or [])
        loras = set(folder_paths.get_filename_list("loras") or [])
        if checkpoint_name not in ckpts:
            ok = False
            lines.append(f"[缺失] Checkpoint: {checkpoint_name}")
        else:
            lines.append(f"[OK] Checkpoint: {checkpoint_name}")
        if lora_name not in loras and not any(str(lora_name).replace(".safetensors", "") in x for x in loras):
            ok = False
            lines.append(f"[缺失] LoRA: {lora_name}")
        else:
            lines.append(f"[OK] LoRA: {lora_name}")
        dirty = [" (1)", "(1).", " (2)", "(2)."]
        try:
            for kind in ("checkpoints", "loras", "upscale_models", "controlnet"):
                for name in folder_paths.get_filename_list(kind) or []:
                    if any(d in name for d in dirty):
                        lines.append(f"[脏名] {kind}: {name}")
                        ok = False
        except Exception:
            pass
        if extra_files:
            for part in str(extra_files).replace("\n", ",").split(","):
                part = part.strip()
                if part and any(d in part for d in dirty):
                    lines.append(f"[脏名] {part}")
                    ok = False
        lines.append("推荐默认：832x1216 | 28 | CFG 5.5 | dpmpp_2m+karras | LoRA 0.9")
        lines.append(f"健康状态: {'PASS' if ok else 'FAIL'}")
        return ("\n".join(lines), ok)


class XiawanUpscaleRecipeHint:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "latent_on": ("BOOLEAN", {"default": False, "forceInput": True}),
            "iter_on": ("BOOLEAN", {"default": False, "forceInput": True}),
            "model_on": ("BOOLEAN", {"default": False, "forceInput": True}),
            "配方": (["手动", "草稿仅底图", "标准潜放", "高清迭代", "仅模型放大"], {"default": "手动"}),
        }}
    RETURN_TYPES = ("STRING", "BOOLEAN", "BOOLEAN", "BOOLEAN", "BOOLEAN")
    RETURN_NAMES = ("advice", "conflict", "rec_latent", "rec_iter", "rec_model")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"
    def output(self, latent_on=False, iter_on=False, model_on=False, **kwargs):
        lat, ite, model = _coerce_bool(latent_on), _coerce_bool(iter_on), _coerce_bool(model_on)
        recipe = str(_value(kwargs, "配方", "recipe", default="手动"))
        rec = {"手动": (lat, ite, model), "草稿仅底图": (False, False, False), "标准潜放": (True, False, False), "高清迭代": (False, True, False), "仅模型放大": (False, False, True)}.get(recipe, (lat, ite, model))
        rec_latent, rec_iter, rec_model = rec
        n = int(lat) + int(ite) + int(model)
        conflict = n >= 2
        if recipe != "手动":
            advice = f"配方「{recipe}」建议：潜放={rec_latent} 迭代={rec_iter} 模型放大={rec_model}。请手动开关对应阶段组。"
            if (lat, ite, model) != (rec_latent, rec_iter, rec_model):
                advice += " 当前阶段与配方不一致。"
                conflict = True
        elif n == 0:
            advice = "放大链路未开启。4060 8G 推荐：标准潜放。"
        elif n == 1:
            advice = "当前单一放大路径，配置健康。"
        else:
            advice = "警告：多放大阶段串联，建议只保留一条主路径。"
        return (advice, conflict, rec_latent, rec_iter, rec_model)


class XiawanSingleRegionDetailerParams:
    @classmethod
    def INPUT_TYPES(cls):
        detector_models = _bbox_models("bbox/face_yolov8m.pt") if _bbox_models else ["bbox/face_yolov8m.pt"]
        default_model = "bbox/face_yolov8m.pt" if "bbox/face_yolov8m.pt" in detector_models else detector_models[0]
        return {"required": {
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
            "分区提示词": ("STRING", {"default": "", "multiline": True}),
        }}
    RETURN_TYPES = ("COMBO", "INT", "FLOAT", "FLOAT", SAMPLERS, SCHEDULERS, "FLOAT", "FLOAT", "INT", "FLOAT", "FLOAT", "BOOLEAN", "STRING")
    RETURN_NAMES = ("model_name", "steps", "cfg", "denoise", "sampler_name", "scheduler", "guide_size", "max_size", "feather", "bbox_threshold", "crop_factor", "noise_mask", "region_prompt")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"
    def output(self, **kwargs):
        return (
            _value(kwargs, "检测模型", "model_name", default="bbox/face_yolov8m.pt"),
            _value(kwargs, "步数", "steps", default=12),
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
            str(_value(kwargs, "分区提示词", "region_prompt", default="") or ""),
        )


class XiawanChangelog:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"
    def output(self):
        text = (
            "Xiawan Workflow Changelog\n"
            "v2.2.0-func\n"
            "- P0.1 ModelSwitch双契约；质量链语义+后级可选；SaveMeta live；终点细化回退提示\n"
            "- P1.1 Seed矩阵可应用batch；Prompt A/B可注入；I2I自动降噪；Tiled VAE真路径；扩图可选；Memory顾问语义\n"
            "- P2.1 放大配方枚举；Detailer分区提示词；健康检查脏名；模型身份源\n"
            "- Anima=轻量T2I支线（无完整CN/IPAdapter/Refiner/质量链）\n"
            "v2.1.1-ui-visual 视觉-only OCD\n"
            "v2.1.0-p2 Profile/矩阵/AB/FreeU-PAG\n"
        )
        return (text,)


class XiawanIntSwitch:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"switch": ("BOOLEAN", {"default": False, "forceInput": True})},
            "optional": {
                "on_false": ("INT", {"default": 1, "forceInput": True}),
                "on_true": ("INT", {"default": 1, "forceInput": True}),
            },
        }
    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("value",)
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"
    def output(self, switch=False, on_false=1, on_true=1):
        return (int(on_true if _coerce_bool(switch) else on_false),)


class XiawanStringSwitch:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"switch": ("BOOLEAN", {"default": False, "forceInput": True})},
            "optional": {
                "on_false": ("STRING", {"default": "", "forceInput": True, "multiline": True}),
                "on_true": ("STRING", {"default": "", "forceInput": True, "multiline": True}),
            },
        }
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"
    def output(self, switch=False, on_false="", on_true=""):
        return (str(on_true if _coerce_bool(switch) else on_false),)


class XiawanModelIdentity:
    @classmethod
    def INPUT_TYPES(cls):
        import folder_paths
        ckpts = folder_paths.get_filename_list("checkpoints") or ["zukiAnimeILL_v50.safetensors"]
        loras = folder_paths.get_filename_list("loras") or ["xiawan_pro.safetensors"]
        ckpt_default = "zukiAnimeILL_v50.safetensors" if "zukiAnimeILL_v50.safetensors" in ckpts else ckpts[0]
        lora_default = "xiawan_pro.safetensors" if "xiawan_pro.safetensors" in loras else loras[0]
        return {"required": {
            "checkpoint": (ckpts, {"default": ckpt_default}),
            "lora": (loras, {"default": lora_default}),
            "lora_strength": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 2.0, "step": 0.01}),
        }}
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("checkpoint_name", "lora_name", "lora_syntax", "summary")
    FUNCTION = "output"
    CATEGORY = "Xiawan/Workflow Controls"
    def output(self, checkpoint, lora, lora_strength=0.9):
        lora_base = str(lora).replace("\\", "/").split("/")[-1]
        lora_key = lora_base[:-12] if lora_base.endswith(".safetensors") else lora_base
        syntax = f"<lora:{lora_key}:{float(lora_strength):.2f}>"
        return (str(checkpoint), lora_base, syntax, f"{checkpoint} + {syntax}")


class XiawanAnyVAEDecode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "samples": ("LATENT",),
            "vae": ("VAE",),
            "use_tiled": ("BOOLEAN", {"default": False}),
            "tile_size": ("INT", {"default": 768, "min": 64, "max": 4096, "step": 32}),
            "overlap": ("INT", {"default": 64, "min": 0, "max": 4096, "step": 32}),
        }}
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "decode"
    CATEGORY = "Xiawan/Workflow Controls"
    def decode(self, samples, vae, use_tiled=False, tile_size=768, overlap=64):
        latent = samples["samples"]
        if _coerce_bool(use_tiled):
            ts = max(64, int(tile_size))
            ov = max(0, min(int(overlap), ts // 4))
            try:
                images = vae.decode_tiled(latent, tile_x=ts, tile_y=ts, overlap=ov)
            except TypeError:
                images = vae.decode_tiled(latent)
        else:
            images = vae.decode(latent)
        if hasattr(images, "shape") and len(images.shape) == 5:
            images = images.reshape(-1, images.shape[-3], images.shape[-2], images.shape[-1])
        return (images,)


class XiawanAnyVAEEncode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "pixels": ("IMAGE",),
            "vae": ("VAE",),
            "use_tiled": ("BOOLEAN", {"default": False}),
            "tile_size": ("INT", {"default": 768, "min": 64, "max": 4096, "step": 64}),
            "overlap": ("INT", {"default": 64, "min": 0, "max": 4096, "step": 32}),
        }}
    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("latent",)
    FUNCTION = "encode"
    CATEGORY = "Xiawan/Workflow Controls"
    def encode(self, pixels, vae, use_tiled=False, tile_size=768, overlap=64):
        if _coerce_bool(use_tiled):
            ts = max(64, int(tile_size))
            ov = max(0, min(int(overlap), ts // 4))
            try:
                t = vae.encode_tiled(pixels, tile_x=ts, tile_y=ts, overlap=ov)
            except TypeError:
                t = vae.encode_tiled(pixels)
        else:
            t = vae.encode(pixels)
        return ({"samples": t},)
