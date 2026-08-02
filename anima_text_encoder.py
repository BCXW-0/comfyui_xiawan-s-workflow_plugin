"""Portable Qwen-3 0.6B text encoder support for Xiawan's Anima branch.

The installed ComfyUI build predates native Anima text-encoder detection.  This
module mirrors the official Anima encoder contract without changing ComfyUI
core files, so the workflow remains portable with the Xiawan plugin.
"""

from dataclasses import dataclass
import os

import torch
from transformers import Qwen2Tokenizer, T5TokenizerFast

from comfy import sd1_clip
import comfy.sd
import comfy.text_encoders.llama as llama
import comfy.utils


@dataclass
class _Qwen3_06BConfig:
    vocab_size: int = 151936
    hidden_size: int = 1024
    intermediate_size: int = 3072
    num_hidden_layers: int = 28
    num_attention_heads: int = 16
    num_key_value_heads: int = 8
    max_position_embeddings: int = 32768
    rms_norm_eps: float = 1e-6
    rope_theta: float = 1000000.0
    transformer_type: str = "llama"
    head_dim: int = 128
    rms_norm_add: bool = False
    mlp_activation: str = "silu"
    qkv_bias: bool = False
    rope_dims: object = None
    q_norm: str = "gemma3"
    k_norm: str = "gemma3"
    rope_scale: object = None
    final_norm: bool = True


class _Qwen3_06B(llama.BaseLlama, torch.nn.Module):
    def __init__(self, config_dict, dtype, device, operations):
        super().__init__()
        config = _Qwen3_06BConfig(**config_dict)
        self.num_layers = config.num_hidden_layers
        self.model = llama.Llama2_(config, device=device, dtype=dtype, ops=operations)
        self.dtype = dtype


class _Qwen3Tokenizer(sd1_clip.SDTokenizer):
    def __init__(self, embedding_directory=None, tokenizer_data={}):
        tokenizer_path = os.path.join(
            os.path.dirname(os.path.realpath(llama.__file__)), "qwen25_tokenizer"
        )
        super().__init__(
            tokenizer_path,
            pad_with_end=False,
            embedding_directory=embedding_directory,
            embedding_size=1024,
            embedding_key="qwen3_06b",
            tokenizer_class=Qwen2Tokenizer,
            has_start_token=False,
            has_end_token=False,
            pad_to_max_length=False,
            max_length=99999999,
            min_length=1,
            pad_token=151643,
            tokenizer_data=tokenizer_data,
        )


class _T5XXLTokenizer(sd1_clip.SDTokenizer):
    def __init__(self, embedding_directory=None, tokenizer_data={}):
        tokenizer_path = os.path.join(
            os.path.dirname(os.path.realpath(llama.__file__)), "t5_tokenizer"
        )
        super().__init__(
            tokenizer_path,
            embedding_directory=embedding_directory,
            pad_with_end=False,
            embedding_size=4096,
            embedding_key="t5xxl",
            tokenizer_class=T5TokenizerFast,
            has_start_token=False,
            pad_to_max_length=False,
            max_length=99999999,
            min_length=1,
            tokenizer_data=tokenizer_data,
        )


class _AnimaTokenizer:
    def __init__(self, embedding_directory=None, tokenizer_data={}):
        self.qwen3_06b = _Qwen3Tokenizer(
            embedding_directory=embedding_directory, tokenizer_data=tokenizer_data
        )
        self.t5xxl = _T5XXLTokenizer(
            embedding_directory=embedding_directory, tokenizer_data=tokenizer_data
        )

    def tokenize_with_weights(self, text, return_word_ids=False, **kwargs):
        qwen_ids = self.qwen3_06b.tokenize_with_weights(text, return_word_ids, **kwargs)
        out = {
            "qwen3_06b": [
                [
                    (token[0], 1.0, token[2]) if return_word_ids else (token[0], 1.0)
                    for token in token_list
                ]
                for token_list in qwen_ids
            ],
            "t5xxl": self.t5xxl.tokenize_with_weights(text, return_word_ids, **kwargs),
        }
        return out

    def untokenize(self, token_weight_pair):
        return self.t5xxl.untokenize(token_weight_pair)

    def state_dict(self):
        return {}

    def decode(self, token_ids, **kwargs):
        return self.qwen3_06b.decode(token_ids, **kwargs)


class _Qwen3_06BModel(sd1_clip.SDClipModel):
    def __init__(
        self,
        device="cpu",
        layer="last",
        layer_idx=None,
        dtype=None,
        attention_mask=True,
        model_options={},
    ):
        super().__init__(
            device=device,
            layer=layer,
            layer_idx=layer_idx,
            textmodel_json_config={},
            dtype=dtype,
            special_tokens={"pad": 151643},
            layer_norm_hidden_state=False,
            model_class=_Qwen3_06B,
            enable_attention_masks=attention_mask,
            return_attention_masks=attention_mask,
            model_options=model_options,
        )


class _AnimaTEModel(sd1_clip.SD1ClipModel):
    def __init__(self, device="cpu", dtype=None, model_options={}):
        super().__init__(
            device=device,
            dtype=dtype,
            name="qwen3_06b",
            clip_model=_Qwen3_06BModel,
            model_options=model_options,
        )

    def encode_token_weights(self, token_weight_pairs):
        out = super().encode_token_weights(token_weight_pairs)
        out[2]["t5xxl_ids"] = torch.tensor(
            [token[0] for token in token_weight_pairs["t5xxl"][0]], dtype=torch.int
        )
        out[2]["t5xxl_weights"] = torch.tensor(
            [token[1] for token in token_weight_pairs["t5xxl"][0]]
        )
        return out


def load_anima_clip(clip_path, embedding_directory=None, model_options=None):
    """Load the official Anima Qwen-3 0.6B encoder through the local plugin."""
    model_options = dict(model_options or {})
    state_dict, metadata = comfy.utils.load_torch_file(
        clip_path, safe_load=True, return_metadata=True
    )
    if model_options.get("custom_operations") is None:
        state_dict, metadata = comfy.utils.convert_old_quants(
            state_dict, "", metadata=metadata
        )

    # The standalone Anima encoder stores keys as ``model.*``.  SD1ClipModel
    # owns the encoder under ``qwen3_06b.transformer`` though, so loading the
    # raw dictionary makes every weight appear missing while silently using an
    # uninitialised text encoder.  Native recent ComfyUI releases perform this
    # namespace adaptation in their loader; keep the plugin portable by doing
    # it here for the older bundled build.
    expected_prefix = "qwen3_06b.transformer."
    if state_dict and not any(key.startswith(expected_prefix) for key in state_dict):
        state_dict = {f"{expected_prefix}{key}": value for key, value in state_dict.items()}

    class _AnimaTarget:
        params = {}
        clip = _AnimaTEModel
        tokenizer = _AnimaTokenizer

    parameters = comfy.utils.calculate_parameters(state_dict)
    return comfy.sd.CLIP(
        _AnimaTarget,
        embedding_directory=embedding_directory,
        parameters=parameters,
        tokenizer_data={},
        state_dict=state_dict,
        model_options=model_options,
    )
