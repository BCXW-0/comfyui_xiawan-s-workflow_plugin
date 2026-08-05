# Xiawan Workflow R-1.4.0 Audit Report

## Runtime

- ComfyUI core: `0.28.0`
- ComfyUI frontend: `1.45.21`
- PyTorch: `2.10.0+cu128`
- Native Anima checks: `comfy.model_base.Anima`, `comfy.ldm.anima.model.LLMAdapter`, and `comfy.sd.TEModel.QWEN3_06B`
- Registered compatibility nodes: `XiawanAnimaModelLoader`, `XiawanVAESwitch`, `XiawanLatentSwitch`, and `XiawanBaseImagePreview`

## Layout

The R-1.4.0 clean template contains 226 nodes, 569 links, and 35 groups. All 224 R-1.3.0 nodes retain their original positions and sizes. The two added hidden logic nodes are placed in existing free regions, and the complete node rectangle audit reports zero overlaps.

The release template uses frontend metadata `1.45.21`, keeps the existing group hierarchy, and does not include developer-only model, LoRA, prompt, input-image, database, or output data.

## Anima Chain

The text-to-image path is:

```text
XiawanAnimaModelLoader -> Anima LoRA -> positive/negative CLIPTextEncode -> Anima KSampler -> VAEDecode -> base-image switch -> preview/output
```

For image-to-image, the shared input preparation now flows through:

```text
input image -> XiawanAnyVAEEncode
                    ^
          XiawanVAESwitch (SDXL VAE / Anima VAE)
                    |
          XiawanLatentSwitch (empty / I2I latent)
                    |
              Anima KSampler
```

The Anima latent input reuses the existing I2I mask switch, so direct, resample, and mask/outpaint modes retain their existing behavior. The Anima branch no longer always consumes an SDXL-encoded latent or an unconditional empty latent.

The clean-template Anima defaults are 30 steps, CFG 4, `er_sde`, `simple`, denoise 1.0. Missing native Anima support fails before model execution, preventing the old pseudo-success full-frame color-noise failure mode.

## Verification Scope

- JSON link source/target reciprocity: passed.
- Duplicate node/link IDs: passed.
- Existing geometry preservation: passed.
- Node rectangle overlap audit: passed.
- Clean-template input sanitization: passed.
- Runtime `/object_info` registration check after restart: passed.
- This audit did not open, preview, screenshot, or pixel-analyze generated images. Image-quality selection is not part of this structural audit.

## Runtime Smoke Tests

Both tests used in-memory API prompts and wrote only to the developer runtime output directory:

| Path suffix | Chain | Status | PNG metadata |
|---|---|---|---|
| `xiawan-anima-tests/r140-native-smoke_00001_.png` | native Anima text-to-image | success | 512x512, RGB, 223933 bytes |
| `xiawan-anima-tests/r140-i2i-smoke_00001_.png` | Anima VAE encode + latent switch image-to-image | success | 768x768, RGB, 326312 bytes |

The files were not opened for visual inspection. They are runtime artifacts only and were not copied into the desktop release source or Git.
