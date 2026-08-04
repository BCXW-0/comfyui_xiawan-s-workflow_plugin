import { app } from "../../scripts/app.js";

// Keep backend input names and slot indexes unchanged. These labels only affect
// the canvas and widget text, so existing workflows remain executable.
const COMMON_LABELS = Object.freeze({
  image: "图像",
  images: "图像",
  image_a: "图像 A",
  image_b: "图像 B",
  image_negative: "负面参考图",
  mask: "遮罩",
  outpaint_mask: "扩图蒙版",
  upload: "上传图像",
  model: "模型",
  model_name: "模型名称",
  ckpt_name: "Checkpoint",
  checkpoint_name: "Checkpoint",
  diffusion_model: "扩散模型",
  text_encoder: "文本编码器",
  clip: "CLIP",
  opt_clip: "可选 CLIP",
  clip_vision: "CLIP Vision",
  vae: "VAE",
  positive: "正面条件",
  negative: "负面条件",
  positive_prompt: "正面提示词",
  negative_prompt: "负面提示词",
  core_prompt: "核心提示词",
  prompt: "提示词",
  prefix_prompt: "前缀提示词",
  selected_prompts: "已选提示词",
  prompt_a: "提示词 A",
  prompt_b: "提示词 B",
  extra_prompt: "附加提示词",
  base_prompt: "基础提示词",
  danbooru_prompts: "D站提示词",
  text: "文本",
  opt_text: "可选文本",
  string: "文本",
  temp_str: "临时文本",
  random_template: "随机模板",
  lora_syntax: "LoRA 语法",
  loaded_loras: "已加载 LoRA",
  lora_stack: "LoRA 堆栈",
  lora_name: "LoRA",
  trigger_words: "触发词",
  filtered_trigger_words: "过滤后触发词",
  control_net: "ControlNet",
  control_net_name: "ControlNet 模型",
  strength: "强度",
  start_percent: "起始百分比",
  end_percent: "结束百分比",
  start_at: "起始位置",
  end_at: "结束位置",
  control_start: "控制起始",
  control_end: "控制结束",
  resolution: "分辨率",
  width: "宽度",
  height: "高度",
  batch_size: "批次数量",
  color: "颜色",
  pad_color: "填充颜色",
  seed: "种子",
  seed_value: "种子值",
  current_seed: "当前种子",
  operation: "操作",
  steps: "步数",
  cfg: "CFG",
  main_denoise: "主采样降噪",
  denoise: "降噪",
  sampler_name: "采样器",
  scheduler: "调度器",
  refiner_enabled: "启用 Refiner",
  refiner_steps: "Refiner 步数",
  refiner_denoise: "Refiner 降噪",
  save_image: "保存图像",
  enable: "启用",
  enabled: "启用",
  active: "当前启用",
  index: "索引",
  switch: "开关",
  value: "值",
  value0: "值 0",
  value1: "值 1",
  on_false: "关闭分支",
  on_true: "开启分支",
  any_input: "任意输入",
  any_output: "任意输出",
  image_pass: "图像直通",
  model_pass: "模型直通",
  report: "报告",
  advice: "说明",
  group_name: "组名称",
  is_enabled: "是否启用",
  empty_cache: "清理显存",
  gc_collect: "执行 GC 回收",
  unload_models: "卸载模型",
  minimum_free_vram_mb: "最低可用显存(MB)",
  free_before_mb: "执行前显存(MB)",
  free_after_mb: "执行后显存(MB)",
  upscale_model: "放大模型",
  upscale_model_opt: "可选放大模型",
  upscaler: "放大器",
  upscale_method: "放大方法",
  scale_method: "缩放方法",
  scale_by: "放大倍率",
  target_scale: "目标倍率",
  upscale_factor: "放大倍率",
  iterative_scale: "迭代缩放",
  iterative_steps: "迭代次数",
  temp_prefix: "临时前缀",
  step_mode: "步进模式",
  vae_compression: "VAE 压缩",
  use_tiled: "启用平铺 VAE",
  use_tiled_vae: "启用平铺 VAE",
  tile_size: "瓦片大小",
  overlap: "重叠",
  tiled_encode: "分块编码",
  tiled_decode: "分块解码",
  profile_use_tiled: "配置启用平铺",
  profile_tile_size: "配置瓦片大小",
  stage_cleanup: "阶段缓存整理",
  profile_report: "配置说明",
  reference_image: "参考图像",
  interpolation: "插值方法",
  crop_position: "裁剪位置",
  sharpening: "锐化",
  coarse: "粗略模式",
  detect_hand: "检测手部",
  detect_body: "检测身体",
  detect_face: "检测面部",
  scale_stick_for_xinsr_cn: "缩放 Xinsr 棒",
  bbox_detector: "BBox 检测器",
  sam_model_opt: "可选 SAM 模型",
  segm_detector_opt: "可选分割检测器",
  detailer_hook: "细化钩子",
  scheduler_func_opt: "可选调度函数",
  guide_size: "引导尺寸",
  guide_size_for: "引导尺寸基准",
  max_size: "最大尺寸",
  feather: "遮罩羽化",
  noise_mask: "噪声遮罩",
  noise_mask_feather: "噪声遮罩羽化",
  force_inpaint: "强制局部重绘",
  bbox_threshold: "检测阈值",
  bbox_dilation: "检测膨胀",
  bbox_crop_factor: "检测裁剪倍率",
  crop_factor: "裁剪倍率",
  sam_detection_hint: "SAM 检测提示",
  sam_dilation: "SAM 膨胀",
  sam_threshold: "SAM 阈值",
  sam_bbox_expansion: "SAM 框扩展",
  sam_mask_hint_threshold: "SAM 遮罩提示阈值",
  sam_mask_hint_use_negative: "SAM 遮罩提示使用负面条件",
  drop_size: "忽略尺寸",
  wildcard: "通配符",
  cycle: "循环次数",
  inpaint_model: "局部重绘模型",
  attn_mask: "注意力遮罩",
  ipadapter: "IPAdapter",
  weight: "权重",
  weight_type: "权重类型",
  combine_embeds: "合并嵌入",
  embeds_scaling: "嵌入缩放",
  preset: "预设",
  auto_random: "自动随机",
  group_mode: "分组模式",
  default_active: "默认启用",
  allow_strength_adjustment: "允许调整强度",
  sdxl_enabled: "启用 SDXL",
  anima_enabled: "启用 Anima",
  unet_weight_dtype: "UNet 权重类型",
  clip_type: "CLIP 类型",
  clip_device: "CLIP 设备",
  base_seed: "基础种子",
  count: "数量",
  mode: "模式",
  offset_step: "偏移步长",
  freeu_b1: "FreeU B1",
  freeu_b2: "FreeU B2",
  freeu_s1: "FreeU S1",
  freeu_s2: "FreeU S2",
  enable_freeu: "启用 FreeU",
  enable_pag: "启用 PAG",
  pag_scale: "PAG 强度",
  device_mode: "设备模式",
  filename_prefix: "文件名前缀",
  file_format: "文件格式",
  quality: "质量",
  embed_workflow: "嵌入工作流",
  save_clean_copy: "保存干净副本",
  enable_preview: "启用预览",
  replace_space: "替换空格",
  general: "通用标签",
  character: "角色标签",
  categories: "标签类别",
  exclude_tags: "排除标签",
  session_method: "会话方式",
  img2img_direct_enabled: "I2I 直通",
  img2img_resample_enabled: "I2I 重采样",
  img2img_caption_enabled: "I2I 自动提示词",
  skip_base_sample: "跳过底图采样",
  apply_enabled: "启用应用",
  seed_matrix_text: "种子矩阵说明",
  label: "标签",
  both_preview: "双提示词预览",
  inject_enabled: "启用注入",
  apply_to_post: "应用到后级",
  meta_summary: "元数据摘要",
  final_output_index: "最终输出索引",
  latent_scale: "潜空间倍率",
  samples: "潜空间",
  pixels: "图像",
  type: "类型",
});

const TYPE_LABELS = Object.freeze({
  IMAGE: "图像",
  MASK: "遮罩",
  MODEL: "模型",
  CLIP: "CLIP",
  VAE: "VAE",
  CONDITIONING: "条件",
  LATENT: "潜空间",
  STRING: "文本",
  INT: "整数",
  FLOAT: "浮点数",
  BOOLEAN: "布尔值",
  CONTROL_NET: "ControlNet",
  SAM_MODEL: "SAM 模型",
  BBOX_DETECTOR: "BBox 检测器",
  SEGM_DETECTOR: "分割检测器",
  UPSCALE_MODEL: "放大模型",
  UPSCALER: "放大器",
  POSE_KEYPOINT: "姿态关键点",
  LORA_STACK: "LoRA 堆栈",
  DETAILER_PIPE: "细化管线",
  DETAILER_HOOK: "细化钩子",
  PK_HOOK: "PixelK 钩子",
  COMBO: "选项",
});

const NODE_LABELS = Object.freeze({
  CheckpointLoaderSimpleMira: {
    inputs: { ckpt_name: "Checkpoint" },
    outputs: { MODEL: "模型", CLIP: "CLIP", VAE: "VAE", model_name: "模型名称" },
  },
  CLIPTextEncode: {
    inputs: { clip: "CLIP", text: "提示词" },
    outputs: { CONDITIONING: "条件" },
  },
  ControlNetApplyAdvanced: {
    inputs: { positive: "正面条件", negative: "负面条件", control_net: "ControlNet", image: "控制图像", vae: "VAE", strength: "强度", start_percent: "起始百分比", end_percent: "结束百分比" },
    outputs: { positive: "正面条件", negative: "负面条件" },
  },
  ControlNetLoader: {
    inputs: { control_net_name: "ControlNet 模型" },
    outputs: { CONTROL_NET: "ControlNet" },
  },
  LoadImage: {
    inputs: { image: "图像", upload: "上传图像" },
    outputs: { IMAGE: "图像", MASK: "遮罩" },
  },
  EmptyImage: { outputs: { IMAGE: "图像" } },
  EmptyLatentImage: { outputs: { LATENT: "潜空间" } },
  KSampler: {
    inputs: { model: "模型", positive: "正面条件", negative: "负面条件", latent_image: "潜空间", seed: "种子", steps: "步数", cfg: "CFG", sampler_name: "采样器", scheduler: "调度器", denoise: "降噪" },
    outputs: { LATENT: "潜空间" },
  },
  VAEDecode: { inputs: { samples: "潜空间", vae: "VAE" }, outputs: { IMAGE: "图像" } },
  VAEEncode: { inputs: { pixels: "图像", vae: "VAE" }, outputs: { LATENT: "潜空间" } },
  SetLatentNoiseMask: { inputs: { samples: "潜空间", mask: "遮罩" }, outputs: { LATENT: "潜空间" } },
  LoraLoaderModelOnly: {
    inputs: { model: "模型", lora_name: "LoRA", strength_model: "模型强度" },
    outputs: { MODEL: "模型" },
  },
  "Lora Loader (LoraManager)": {
    inputs: { model: "模型", text: "文本", clip: "CLIP", lora_stack: "LoRA 堆栈" },
    outputs: { MODEL: "模型", CLIP: "CLIP", trigger_words: "触发词", loaded_loras: "已加载 LoRA" },
  },
  "TriggerWord Toggle (LoraManager)": {
    inputs: { group_mode: "分组模式", default_active: "默认启用", allow_strength_adjustment: "允许调整强度", trigger_words: "触发词" },
    outputs: { filtered_trigger_words: "过滤后触发词" },
  },
  DanbooruGalleryNode: {
    inputs: { enabled: "启用", bypass_image: "绕过图像", bypass_prompts: "绕过提示词" },
    outputs: { images: "图像", prompts: "提示词" },
  },
  PromptSelector: {
    inputs: { prefix_prompt: "前缀提示词", selected_prompts: "已选提示词" },
    outputs: { prompt: "提示词" },
  },
  WeiLinPromptUIWithoutLora: {
    inputs: { opt_text: "可选文本", opt_clip: "可选 CLIP", positive: "正面条件", auto_random: "自动随机", temp_str: "临时文本", random_template: "随机模板" },
    outputs: { STRING: "文本", CONDITIONING: "条件", CLIP: "CLIP" },
  },
  JoinStrings: { inputs: { string1: "文本 1", string2: "文本 2", delimiter: "分隔符" }, outputs: { STRING: "文本" } },
  PromptCleaningMaid: { inputs: { string: "文本" }, outputs: { string: "文本" } },
  XiawanInpaintPadScaffold: {
    inputs: { image: "图像", pad_left: "左填充", pad_right: "右填充", pad_top: "上填充", pad_bottom: "下填充", pad_color: "填充颜色" },
    outputs: { image: "图像", outpaint_mask: "扩图蒙版", width: "宽度", height: "高度", use_mask: "使用蒙版", advice: "说明" },
  },
  XiawanBaseParams: {
    inputs: { width: "宽度", height: "高度" },
    outputs: { width: "宽度", height: "高度", batch_size: "批次数量", steps: "步数", cfg: "CFG", main_denoise: "主采样降噪", sampler_name: "采样器", scheduler: "调度器", refiner_enabled: "启用 Refiner", refiner_steps: "Refiner 步数", refiner_denoise: "Refiner 降噪", img2img_direct_enabled: "I2I 直通", img2img_resample_enabled: "I2I 重采样", save_image: "保存图像", img2img_caption_enabled: "I2I 自动提示词", skip_base_sample: "跳过底图采样", mode_advice: "模式说明" },
  },
  XiawanAnimaBaseParams: {
    outputs: { width: "宽度", height: "高度", batch_size: "批次数量", steps: "步数", cfg: "CFG", main_denoise: "主采样降噪", sampler_name: "采样器", scheduler: "调度器" },
  },
  XiawanControlParams: {
    outputs: { openpose_strength: "OpenPose 强度", scribble_strength: "Scribble 强度", lineart_strength: "Lineart 强度", depth_strength: "Depth 强度", person_reference_weight: "人物参考权重", control_start: "控制起始", control_end: "控制结束", ipadapter_start: "IPAdapter 起始", ipadapter_end: "IPAdapter 结束" },
  },
  XiawanPromptAB: {
    outputs: { active_prompt: "当前提示词", label: "标签", both_preview: "双提示词预览", inject_enabled: "启用注入" },
  },
  XiawanQualityBoostParams: {
    outputs: { enable_freeu: "启用 FreeU", b1: "FreeU B1", b2: "FreeU B2", s1: "FreeU S1", s2: "FreeU S2", enable_pag: "启用 PAG", pag_scale: "PAG 强度", advice: "说明", apply_to_post: "应用到后级" },
  },
  XiawanHighResPerformanceProfile: {
    outputs: { tiled_encode: "分块编码", tiled_decode: "分块解码", stage_cleanup: "阶段缓存整理", minimum_free_vram_mb: "最低可用显存(MB)", tile_size: "瓦片大小", overlap: "重叠", profile_report: "配置说明" },
  },
  XiawanSaveMetaPack: {
    outputs: { checkpoint_name: "Checkpoint", lora_syntax: "LoRA 语法", positive_prompt: "正面提示词", negative_prompt: "负面提示词", meta_summary: "元数据摘要" },
  },
  XiawanSingleRegionDetailerParams: {
    outputs: { model_name: "检测模型", steps: "步数", cfg: "CFG", denoise: "降噪", sampler_name: "采样器", scheduler: "调度器", guide_size: "引导尺寸", max_size: "最大尺寸", feather: "遮罩羽化", bbox_threshold: "检测阈值", crop_factor: "裁剪倍率", noise_mask: "噪声遮罩", region_prompt: "分区提示词" },
  },
  XiawanAnyVAEDecode: { outputs: { image: "图像" } },
  XiawanAnyVAEEncode: { outputs: { latent: "潜空间" } },
  XiawanImageSwitch: { inputs: { switch: "开关", on_false: "关闭分支", on_true: "开启分支" }, outputs: { image: "图像" } },
  XiawanIntSwitch: { inputs: { switch: "开关", on_false: "关闭分支", on_true: "开启分支" }, outputs: { value: "值" } },
  XiawanLatentSwitch: { inputs: { switch: "开关", on_false: "关闭分支", on_true: "开启分支" }, outputs: { latent: "潜空间" } },
  XiawanModelSwitch: { inputs: { index: "索引", switch: "开关", value0: "值 0", value1: "值 1", on_false: "关闭分支", on_true: "开启分支" }, outputs: { model: "模型" } },
  XiawanFinalImageSwitch: { inputs: { index: "输出索引" }, outputs: { image: "图像" } },
  XiawanFinalOutputParams: { outputs: { final_output_index: "最终输出索引" } },
  XiawanGlobalSeedManager: { inputs: { seed_value: "种子值", operation: "操作", current_seed: "当前种子" }, outputs: { seed: "种子" } },
  XiawanVRAMModelGuard: { inputs: { model: "模型" }, outputs: { model: "模型", free_before_mb: "执行前显存(MB)", free_after_mb: "执行后显存(MB)", report: "报告" } },
  XiawanImageVRAMGuard: { inputs: { image: "图像" }, outputs: { image: "图像", free_before_mb: "执行前显存(MB)", free_after_mb: "执行后显存(MB)", report: "报告" } },
  XiawanLatentVRAMGuard: { inputs: { latent: "潜空间" }, outputs: { latent: "潜空间", free_before_mb: "执行前显存(MB)", free_after_mb: "执行后显存(MB)", report: "报告" } },
  XiawanRuntimeMemoryRelease: { inputs: { image: "图像" }, outputs: { image: "图像", free_after_mb: "执行后显存(MB)", report: "报告" } },
  XiawanHighResModelPreflight: { inputs: { model: "模型" }, outputs: { model: "模型", free_before_mb: "执行前显存(MB)", free_after_mb: "执行后显存(MB)", report: "报告" } },
  VRAM_Debug: { outputs: { any_output: "任意输出", image_pass: "图像直通", model_pass: "模型直通", freemem_before: "执行前显存(MB)", freemem_after: "执行后显存(MB)" } },
  XiawanAnimaModelLoader: { outputs: { MODEL: "模型", CLIP: "CLIP", VAE: "VAE" } },
  XiawanAnimaBranchIndex: { inputs: { sdxl_enabled: "启用 SDXL", anima_enabled: "启用 Anima" }, outputs: { index: "索引", sdxl_active: "SDXL 已启用", anima_active: "Anima 已启用" } },
  XiawanBatchSeedMatrix: { outputs: { seed_0: "种子 0", seed_1: "种子 1", seed_2: "种子 2", seed_3: "种子 3", batch_size: "批次数量", seed_matrix_text: "种子矩阵说明", apply_enabled: "启用应用" } },
  XiawanDanbooruGlobalPromptAppend: { outputs: { prompt: "提示词" } },
  XiawanOptionalPromptAppend: { outputs: { prompt: "提示词" } },
  XiawanTiledVAEParams: { outputs: { use_tiled_vae: "启用平铺 VAE", tile_size: "瓦片大小", overlap: "重叠", advice: "说明" } },
  XiawanIterativeUpscaleParams: { outputs: { scale_method: "缩放方法", steps: "步数", cfg: "CFG", sampler_name: "采样器", scheduler: "调度器", denoise: "降噪", use_tiled_vae: "启用平铺 VAE", tile_size: "瓦片大小", upscale_factor: "放大倍率", iterative_steps: "迭代次数", temp_prefix: "临时前缀", step_mode: "步进模式", vae_compression: "VAE 压缩" } },
  XiawanLatentUpscaleParams: { outputs: { upscale_method: "放大方法", scale_by: "放大倍率", steps: "步数", cfg: "CFG", sampler_name: "采样器", scheduler: "调度器", denoise: "降噪" } },
  XiawanModelUpscaleParams: { outputs: { upscale_method: "放大方法", scale_by: "放大倍率", target_scale: "目标倍率", steps: "步数", cfg: "CFG", sampler_name: "采样器", scheduler: "调度器", denoise: "降噪" } },
  XiawanTargetScaleImageGuard: { inputs: { image: "图像", reference_image: "参考图像", target_scale: "目标倍率", upscale_method: "放大方法" }, outputs: { image: "图像" } },
  ResolutionMasterSimplify: { inputs: { width: "宽度", height: "高度" }, outputs: { width: "宽度", height: "高度" } },
  FaceDetailer: { outputs: { image: "图像", cropped_refined: "裁剪细化图", cropped_enhanced_alpha: "裁剪增强图 Alpha", mask: "遮罩", detailer_pipe: "细化管线", cnet_images: "ControlNet 图像" } },
  FreeU_V2: { inputs: { model: "模型", b1: "FreeU B1", b2: "FreeU B2", s1: "FreeU S1", s2: "FreeU S2" }, outputs: { MODEL: "模型" } },
  PerturbedAttentionGuidance: { inputs: { model: "模型", scale: "PAG 强度" }, outputs: { MODEL: "模型" } },
  OpenposePreprocessor: { inputs: { image: "图像", detect_hand: "检测手部", detect_body: "检测身体", detect_face: "检测面部", resolution: "分辨率", scale_stick_for_xinsr_cn: "缩放 Xinsr 棒" }, outputs: { IMAGE: "图像", POSE_KEYPOINT: "姿态关键点" } },
  ScribblePreprocessor: { inputs: { image: "图像", resolution: "分辨率" }, outputs: { IMAGE: "图像" } },
  LineArtPreprocessor: { inputs: { image: "图像", coarse: "粗略模式", resolution: "分辨率" }, outputs: { IMAGE: "图像" } },
  DepthAnythingV2Preprocessor: { inputs: { image: "图像", ckpt_name: "Depth 模型", resolution: "分辨率" }, outputs: { IMAGE: "图像" } },
  cl_tagger_mira: { inputs: { image: "图像", model_name: "模型名称", general: "通用标签", character: "角色标签", replace_space: "替换空格", categories: "标签类别", exclude_tags: "排除标签", session_method: "会话方式" }, outputs: { tags: "标签" } },
  SAMLoader: { inputs: { model_name: "SAM 模型", device_mode: "设备模式" }, outputs: { SAM_MODEL: "SAM 模型" } },
  UltralyticsDetectorProvider: { inputs: { model_name: "检测模型" }, outputs: { BBOX_DETECTOR: "BBox 检测器", SEGM_DETECTOR: "分割检测器" } },
  UpscaleModelLoader: { inputs: { model_name: "放大模型" }, outputs: { UPSCALE_MODEL: "放大模型" } },
  IPAdapterUnifiedLoader: { inputs: { model: "模型", ipadapter: "IPAdapter", preset: "预设" }, outputs: { model: "模型", ipadapter: "IPAdapter" } },
  IPAdapterAdvanced: { inputs: { model: "模型", ipadapter: "IPAdapter", image: "参考图像", image_negative: "负面参考图", attn_mask: "注意力遮罩", clip_vision: "CLIP Vision", weight: "权重", weight_type: "权重类型", combine_embeds: "合并嵌入", start_at: "起始位置", end_at: "结束位置", embeds_scaling: "嵌入缩放" }, outputs: { MODEL: "模型" } },
  IterativeImageUpscale: { inputs: { pixels: "图像", upscaler: "放大器", vae: "VAE", upscale_factor: "放大倍率", steps: "步数", temp_prefix: "临时前缀", step_mode: "步进模式", vae_compression: "VAE 压缩" }, outputs: { image: "图像" } },
  PixelKSampleUpscalerProvider: { outputs: { UPSCALER: "放大器" } },
  PrepImageForClipVision: { inputs: { image: "图像", interpolation: "插值方法", crop_position: "裁剪位置", sharpening: "锐化" }, outputs: { IMAGE: "图像" } },
  SetUnionControlNetType: { inputs: { control_net: "ControlNet", type: "类型" }, outputs: { CONTROL_NET: "ControlNet" } },
  SimpleImageCompare: { inputs: { image_a: "图像 A", image_b: "图像 B", enabled: "启用" } },
});

const WORKFLOW_NODE_TYPES = new Set([
  "CheckpointLoaderSimpleMira", "cl_tagger_mira", "CLIPTextEncode", "ControlNetApplyAdvanced", "ControlNetLoader", "DanbooruGalleryNode", "DepthAnythingV2Preprocessor", "easy conditioningIndexSwitch", "easy imageIndexSwitch", "EmptyImage", "EmptyLatentImage", "FaceDetailer", "FreeU_V2", "GroupIgnoreManager", "GroupIsEnabled", "ImageScaleBy", "ImageUpscaleWithModel", "IPAdapterAdvanced", "IPAdapterUnifiedLoader", "IterativeImageUpscale", "JoinStrings", "KSampler", "LatentUpscaleBy", "LineArtPreprocessor", "LoadImage", "Lora Loader (LoraManager)", "OpenposePreprocessor", "PerturbedAttentionGuidance", "PixelKSampleUpscalerProvider", "PrepImageForClipVision", "PromptCleaningMaid", "PromptSelector", "ResolutionMasterSimplify", "SAMLoader", "SaveImagePlus", "ScribblePreprocessor", "SetLatentNoiseMask", "SetUnionControlNetType", "SimpleImageCompare", "TriggerWord Toggle (LoraManager)", "UltralyticsDetectorProvider", "UpscaleModelLoader", "VAEDecode", "VAEEncode", "VRAM_Debug", "WeiLinPromptUIWithoutLora", "XiawanAnimaBaseParams", "XiawanAnimaBranchIndex", "XiawanAnimaModelLoader", "XiawanAnyVAEDecode", "XiawanAnyVAEEncode", "XiawanBaseParams", "XiawanBatchSeedMatrix", "XiawanBooleanToIndex", "XiawanClearablePreviewImage", "XiawanClearableShowText", "XiawanControlParams", "XiawanDanbooruGlobalPromptAppend", "XiawanFinalImageSwitch", "XiawanFinalOutputParams", "XiawanGlobalSeedManager", "XiawanHighResModelPreflight", "XiawanHighResPerformanceProfile", "XiawanI2IPrepare", "XiawanImageSwitch", "XiawanImageVRAMGuard", "XiawanInpaintPadScaffold", "XiawanIntSwitch", "XiawanIterativeUpscaleParams", "XiawanLatentSwitch", "XiawanLatentUpscaleParams", "XiawanLatentVRAMGuard", "XiawanModelSwitch", "XiawanModelUpscaleParams", "XiawanOptionalPromptAppend", "XiawanPromptAB", "XiawanQualityBoostParams", "XiawanRuntimeMemoryRelease", "XiawanSaveMetaPack", "XiawanSingleRegionDetailerParams", "XiawanTaggerParams", "XiawanTargetScaleImageGuard", "XiawanTiledVAEParams", "XiawanVRAMModelGuard"
]);

function hasChineseText(value) {
  return typeof value === "string" && /[\u3400-\u9fff]/.test(value);
}

function translatedName(nodeType, direction, name, index) {
  if (typeof name !== "string" || !name || hasChineseText(name)) {
    return null;
  }

  const nodeLabels = NODE_LABELS[nodeType]?.[direction];
  if (nodeLabels && Object.prototype.hasOwnProperty.call(nodeLabels, name)) {
    return nodeLabels[name];
  }

  if (direction === "outputs" && Object.prototype.hasOwnProperty.call(TYPE_LABELS, name)) {
    return TYPE_LABELS[name];
  }

  if (Object.prototype.hasOwnProperty.call(COMMON_LABELS, name)) {
    return COMMON_LABELS[name];
  }

  const lowerName = name.toLowerCase();
  if (Object.prototype.hasOwnProperty.call(COMMON_LABELS, lowerName)) {
    return COMMON_LABELS[lowerName];
  }

  const imageMatch = lowerName.match(/^image(\d+)$/);
  if (imageMatch) return `图像 ${imageMatch[1]}`;

  const conditionMatch = lowerName.match(/^cond(\d+)$/);
  if (conditionMatch) return `条件 ${conditionMatch[1]}`;

  const valueMatch = lowerName.match(/^value(\d+)$/);
  if (valueMatch) return `值 ${valueMatch[1]}`;

  const seedMatch = lowerName.match(/^seed_(\d+)$/);
  if (seedMatch) return `种子 ${seedMatch[1]}`;

  const triggerMatch = lowerName.match(/^trigger_words(\d*)$/);
  if (triggerMatch) return triggerMatch[1] ? `触发词 ${triggerMatch[1]}` : "触发词";

  if (direction === "outputs" && typeof index === "number") {
    const typeLabel = TYPE_LABELS[name];
    if (typeLabel) return typeLabel;
  }

  return null;
}

function patchInputDefinition(nodeType, nodeData) {
  for (const category of ["required", "optional"]) {
    const inputs = nodeData?.input?.[category];
    if (!inputs) continue;

    for (const [name, spec] of Object.entries(inputs)) {
      const label = translatedName(nodeType, "inputs", name);
      if (!label || !Array.isArray(spec)) continue;
      spec[1] = { ...(spec[1] || {}), display_name: label };
    }
  }
}

function applyInputLabel(node, input, index) {
  if (!input) return false;
  const label = translatedName(node.comfyClass || node.type, "inputs", input.name, index);
  if (!label) return false;

  let changed = false;
  if (input.localized_name !== label) {
    input.localized_name = label;
    changed = true;
  }
  if (input.label !== label) {
    input.label = label;
    changed = true;
  }

  const widgetName = input.widget?.name || input.name;
  const widget = node.widgets?.find((item) => item?.name === widgetName);
  if (widget && widget.label !== label) {
    widget.label = label;
    changed = true;
  }
  return changed;
}

function applyOutputLabel(node, output, index) {
  if (!output) return false;
  const label = translatedName(node.comfyClass || node.type, "outputs", output.name, index);
  if (!label) return false;

  if (output.localized_name === label) return false;
  output.localized_name = label;
  return true;
}

function applyNodeLabels(node) {
  const nodeType = node?.comfyClass || node?.type;
  if (!node || !WORKFLOW_NODE_TYPES.has(nodeType)) return;

  let changed = false;
  for (const [index, input] of (node.inputs || []).entries()) {
    changed = applyInputLabel(node, input, index) || changed;
  }
  for (const [index, output] of (node.outputs || []).entries()) {
    changed = applyOutputLabel(node, output, index) || changed;
  }

  if (changed) {
    node.graph?.setDirtyCanvas?.(true, true);
  }
}

function installDynamicLabelHooks(node) {
  if (!node || node.__xwChinesePortLabelsInstalled) return;
  node.__xwChinesePortLabelsInstalled = true;

  const originalInputAdded = node.onInputAdded;
  node.onInputAdded = function (input) {
    const result = originalInputAdded?.apply(this, arguments);
    applyInputLabel(this, input, this.inputs?.indexOf(input));
    return result;
  };

  const originalOutputAdded = node.onOutputAdded;
  node.onOutputAdded = function (output) {
    const result = originalOutputAdded?.apply(this, arguments);
    applyOutputLabel(this, output, this.outputs?.indexOf(output));
    return result;
  };

  applyNodeLabels(node);
}

app.registerExtension({
  name: "Xiawan.ChinesePortLabels",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    const nodeTypeName = nodeData?.name;
    if (!WORKFLOW_NODE_TYPES.has(nodeTypeName)) return;

    patchInputDefinition(nodeTypeName, nodeData);

    const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = originalOnNodeCreated?.apply(this, arguments);
      installDynamicLabelHooks(this);
      return result;
    };

    const originalOnConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const result = originalOnConfigure?.apply(this, arguments);
      installDynamicLabelHooks(this);
      applyNodeLabels(this);
      return result;
    };
  },

  nodeCreated(node) {
    installDynamicLabelHooks(node);
  },

  loadedGraphNode(node) {
    installDynamicLabelHooks(node);
    applyNodeLabels(node);
  },
});
