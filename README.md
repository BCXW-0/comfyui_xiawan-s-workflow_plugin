# Xiawan Workflow Plugin

面向 ComfyUI 的 SDXL / Anima 工作流插件，提供文生图、图生图、ControlNet、LoRA、提示词编辑、放大、部位细化、结果预览和低显存运行支持。

GitHub Description:

> An advanced ComfyUI workflow plugin for SDXL and Anima generation with prompt tools, LoRA management, ControlNet, upscaling, detail refinement, and low-VRAM support.

## 使用方式

### 安装

将本项目目录放入：

```text
ComfyUI/custom_nodes/comfyui_xiawan's-workflow_plugin
```

打开 ComfyUI 前确认插件目录完整，然后重启 ComfyUI。使用秋叶启动器时，在“绘世启动器”页面依次点击“终止进程”和“一键启动”。

### 打开工作流

使用发布模板：

```text
workflows/Xiawan's Workflow ver.R-1.1.json
```

R-1.1 是清洁模板，已清除 Checkpoint、LoRA、提示词和个人输入图配置。首次使用时，请先在参数区选择本地模型，再填写提示词和输入图。

`Xiawan's Workflow.json` 是开发者本地运行配置，包含实际跑图时的模型、LoRA、提示词和输入图，不作为发布模板使用。

### 细化模型

R-1.1 使用以下部位检测模型：

| 用途 | 文件名 |
|---|---|
| 脸部 | `face_yolov8m.pt` |
| 眼睛 | `full_eyes_detect_v1.pt` |
| 手部 | `hand_yolov8s.pt` |
| 足部 | `adetailerFootYolov8x_v20.pt` |
| 乳首 | `nipples_yolov8s-seg.pt` |

将它们放入：

```text
ComfyUI/models/ultralytics/bbox/
```

本仓库的 `models/ultralytics/bbox/` 已包含这些文件。通过 Git LFS 获取仓库后，如文件显示为指针文件，请执行 `git lfs pull`。

### 基本操作顺序

1. 在模型参数区选择 Checkpoint、LoRA、VAE 和需要的辅助模型。
2. 在提示词区填写正面、负面提示词，以及需要的固定前缀、固定后缀。
3. 在左侧开关区选择 SDXL 或 Anima，并按需要启用图生图、ControlNet、放大和部位细化。
4. 在参数区调整分辨率、Seed、采样步数、CFG、采样器和调度器。
5. 先测试底图，再逐项开启放大或细化阶段。
6. 低显存设备优先保持批次数量为 1，启用 Tiled VAE，并关闭不需要的阶段。

### 重要限制

日常使用只调整“开关区”和“参数控制区”。请不要随意移动、删除、复制、改名、改尺寸或重新连接“逻辑区”的节点和分组。每次修改工作流后，请先关闭旧工作流标签，再重新打开 JSON，避免 ComfyUI 使用旧画布缓存。

## 节点说明

### 开关区

| 节点 / 开关 | 用途 |
|---|---|
| 文生图主链路 | 控制整套主工作流是否运行。 |
| SDXL 底图 | 使用 SDXL 生成底图。 |
| Anima 底图 | 使用 Anima 生成底图，与 SDXL 二选一。 |
| 图生图直通 / 重采样 | 选择输入图的使用方式。没有输入图时保持关闭。 |
| OpenPose、人物替换、Scribble、Lineart、Depth | 启用对应的参考图或结构控制分支。 |
| 图像反推、D 站画廊 | 启用标签反推或参考图选择功能。 |
| 潜空间放大、迭代放大、通用放大 | 启用对应的放大阶段。 |
| 部位细化 | 启用部位细化总开关。 |
| 脸部、眼睛、手部、足部、乳首细化 | 单独启用对应的检测和细化阶段。 |

开启可选分支前，先确认参数区已经配置了对应的输入图、模型和参数。互斥的底图分支不要同时开启。

### 参数控制区

| 节点 / 参数 | 用途 |
|---|---|
| Checkpoint / Refiner Checkpoint | 选择主模型和可选 Refiner 模型。 |
| LoRA | 选择 LoRA 并调整权重；需要时启用触发词。 |
| 全局 Seed | 设置固定、随机、递增、递减或沿用上次 Seed。 |
| Seed 矩阵 | 预览 Seed 序列；启用“应用到批次”后使用矩阵首 Seed 并调整批次数量。 |
| 正面提示词 / 负面提示词 | 填写主要提示词。 |
| 固定前缀 / 固定后缀 | 填写每次生成都需要保留的通用提示词。 |
| 提示词 A/B | 在两组提示词之间切换和预览。 |
| 分辨率 / SDXL 主参数 / Anima 主参数 | 设置宽高、批次数量、步数、CFG、采样器、调度器和图生图降噪。 |
| OpenPose / 人物 / Scribble / Lineart / Depth | 设置参考图、控制强度和介入范围。 |
| 反推 / D 站画廊 | 设置反推模型、阈值、标签类别和参考图。 |
| 放大参数 | 设置放大倍率、放大模型、采样步数、CFG、采样器、调度器和 Tiled VAE。 |
| 部位细化参数 | 为每个部位选择检测模型、细化步数、CFG、降噪、检测阈值、裁剪倍率和区域提示词。 |
| FreeU / PAG | 调整质量增强功能；出现过度锐化或显存不足时关闭或降低强度。 |
| 保存元数据 / 最终输出 | 设置输出选项。保存节点会读取实际运行配置并写入 PNG 元数据。 |

部位细化模型必须使用与检测区域匹配的文件。模型缺失时，请先补齐 `ComfyUI/models/ultralytics/bbox/` 中的文件，再开启对应细化开关。
