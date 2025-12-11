# Neo-DumasTrans

[English](README.md) | 中文

> 一个能精准解析文本及图片 PDF，进行大模型翻译和高保真排版，支持公式、表格、图片、超大文件、多页面混杂和复杂排版的 PDF 翻译软件。

---

## ✨ 核心特性与技术亮点

### 📄 智能 PDF 预处理（应对真实世界的复杂文档）
- 自动标准化坐标系统，消除负坐标、非规范数值等“脏数据”  
- 智能检测页面方向并统一旋转为正向（上下走向），显著提升后续解析鲁棒性  
- 有效处理扫描件歪斜、嵌入图像旋转、混合布局等棘手场景

### ⚡ 三模式 MinerU 引擎（灵活应对不同 PDF 文件）
- `txt`：纯文本 PDF → 使用 **本地 MinerU** 提取结构化内容  
- `ocr`：扫描/图像 PDF → 使用 **本地 MinerU + OCR** 还原文字与布局  
- `vlm`：复杂排版（含公式/表格/图文混排）→  
  - **不填 Token**：启用 **本地 VLM 模式** —— **直接在 Windows 上运行，无需 WSL2**，基于预编译 LMDeploy（需 CUDA 11.8+）实现高性能离线结构识别  
  - **填写 Token**：调用 **MinerU 官方在线 API** 避免硬件依赖  

### 🌐 高效结构化翻译流水线（云端翻译模式）
- 将多个可翻译段落打包为结构化 JSON 数组提交大模型  
- 返回内容自动校验格式一致性，杜绝段落错位、标签丢失或顺序混乱  
- 显著降低 token 消耗（减少重复 prompt 开销），提升吞吐效率

### 🧠 专为 HunYuan-MT 优化的本地推理（本地翻译模式）
- 基于 **llama.cpp** 加载 GGUF 模型，支持 CPU/GPU 推理  
- 对 `Hunyuan-MT-7B.Q4_K_S.gguf` 定制 prompt 模板、输出过滤与后处理逻辑  
- 翻译质量接近主流云端大模型，完全适配离线高保真场景  
- ⚠️ 其他 GGUF 模型可能因指令格式差异导致效果下降

### 🎨 高保真视觉融合覆盖
- 仅对**需翻译区域**进行智能覆盖：采样局部背景色生成自然过渡底色  
- 图片、水印、装饰元素、代码块等**非文本区域 100% 保留原貌**  
- 视觉上实现“原文消失、译文浮现”的无缝替换，彻底告别“涂白割裂感”

### 📏 像素级精准排版
- **双阶段字号校准**：  
  1️⃣ Pillow 粗估文本尺寸 → 初步限制字号上限  
  2️⃣ Playwright + Chromium 实时渲染测量 → 动态迭代调整，确保译文 **100% 落入原始 bbox**，无溢出、无截断  
- 利用浏览器原生排版引擎，完美支持 MathJax 公式、复杂表格等元素  
- 输出 PDF 具备像素级定位精度，媲美人工精修

### ⚙️ 高效异步流水线架构
- **开头预处理并发执行**（多文件并行标准化）  
- **中间流程异步流水线**：MinerU 解析 → 叶块提取 → 背景覆盖 → 翻译 → HTML 生成 → PDF 渲染  
- **结尾合并串行执行**，确保最终文件完整性  
- 支持自动分块（默认 25 页/块）、断点续跑、失败隔离，轻松处理超大 PDF

### 🧹 智能临时文件管理
- 启动时自动清理：  
  - 删除 **超过 7 天** 的临时文件  
  - 若工作区总大小 **> 10GB**，则清空缓存  
- 平衡调试便利性与磁盘安全，避免意外爆满

---

## 💻 推荐运行环境

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10 / 11（64 位） |
| 内存 | ≥ 16 GB（最低 8 GB，大文件建议 16G+） |
| 显卡驱动 | NVIDIA 驱动 ≥ 520，**CUDA 11.8 或更高** |
| 显存 | ≥ 8 GB（推荐 12 GB，如 RTX 3060 12G / 4070 12G） |
| 存储 | SSD，剩余空间 ≥ 20 GB |

> ✅ **本地 VLM 模式已集成预编译 LMDeploy，开箱即用，无需 WSL2、Docker 或手动编译**

---

## 📦 快速开始

### 下载 Windows 版（绿色免安装）
这里提供两个版本，请根据需求选择：

| 版本 | 说明 | 下载链接 |
|------|------|--------|
| **完整版** | 内置 `HunYuan-MT-7B.Q4_K_S.gguf`，开箱即用 | 🔗 [百度网盘链接（完整版）](https://pan.baidu.com/s/1eN4mhNKk7DEcPbtmnP-R1g?pwd=nu9u) |
| **轻量版** | 不含模型，需自行下载 | 🔗 [百度网盘链接（轻量版）](https://pan.baidu.com/s/1eN4mhNKk7DEcPbtmnP-R1g?pwd=nu9u) |

🔑 提取码：`nu9u`

### 从仓库安装（开发者）

如果你希望从源码构建或参与开发，请按以下步骤操作：

1. 克隆本仓库到本地：
   ```bash
   git clone https://github.com/Neo-Dumas/Neo-DumasTrans.git
   cd Neo-DumasTrans
   ```

2. **双击运行根目录下的 `setup.bat`**  
   - 脚本会自动下载便携版 Python 3.10.11（如尚未存在）
   - 自动安装所有必需的 Python 依赖（包括 PyTorch CUDA 11.8 版本、llama.cpp、MinerU、Playwright 等）
   - 自动配置 Playwright 的 Chromium 浏览器
   - 整个过程无需手动输入命令，也**不需要预先安装 Python 或 pip**

3. 安装完成后，双击 `run.bat` 即可启动图形界面。

> 💡 此方式适用于希望调试代码、修改功能或打包自定义版本的开发者。普通用户推荐直接使用上方提供的绿色完整版。

---

## ⚙️ 使用说明

1. 解压后，双击根目录下 `run.bat` 或 `双击启动程序.bat` 启动图形界面。
2. 在设置中选择：
   - **PDF 解析模式**：`txt` / `ocr` / `vlm`
     - 若选 `vlm` 且 **未填写 Token** → 启用 **Windows 原生本地 VLM 模式**（需 CUDA 11.8+）
     - 若填写 Token → 调用 MinerU 在线 API
   - **翻译后端**：云端 API 或 本地模型（推荐 `HunYuan-MT-7B.Q4_K_S.gguf`）
3. 选择 PDF 文件，点击“开始翻译”。

> 📌 完整版 `HunYuan-MT-7B.Q4_K_S.gguf`模型在程序根目录的 `models` 文件夹里，首次使用需手动指定。

---

## 🎯 适用场景

- 学术论文 / 技术文档的高质量翻译（保留公式、图表位置）  
- 扫描合同、报告的双语对照处理  
- 无网络环境下的离线高保真本地化  
- 文档自动化翻译流水线（支持断点续跑）

---

## 💡 致谢

本项目基于多个优秀的开源工具构建：

- [MinerU](https://github.com/opendatalab/MinerU)：支持公式和表格的结构化 PDF 解析（v2.6.5+）  
- [PyMuPDF (fitz)](https://github.com/pymupdf/PyMuPDF)：高性能 PDF 处理库  
- [Playwright](https://playwright.dev/)：用于像素级精确渲染的浏览器自动化工具  
- [MathJax](https://www.mathjax.org/)：高质量数学公式渲染  
- [llama.cpp](https://github.com/ggerganov/llama.cpp)：高效的本地大语言模型推理引擎  
- [OpenCV](https://opencv.org/)：用于 OCR 预处理的图像处理库  
- [HunYuan-MT-7B](https://gitcode.com/tencent_hunyuan/HunYuan-MT-7B-fp8)：腾讯开源翻译模型

便携版（绿色版）包含了以下第三方二进制组件，各自遵循其原始许可证：
- [`Ghostscript`](https://www.ghostscript.com/) – GNU AGPLv3  
- [`PyMuPDF`](https://github.com/pymupdf/PyMuPDF) – GNU AGPLv3  
- [`OpenCV`](https://github.com/opencv/opencv) – Apache License 2.0  
- [`Playwright`](https://github.com/microsoft/playwright) – Apache License 2.0  
- [`llama.cpp`](https://github.com/ggerganov/llama.cpp) – MIT  
- [`MinerU`](https://github.com/opendatalab/MinerU) – Apache License 2.0  
- [`HunYuan-MT-7B`](https://gitcode.com/tencent_hunyuan/HunYuan-MT-7B-fp8) – Apache License 2.0  

感谢这些开源项目的贡献者们！

---

## 📄 许可证  
本项目采用 AGPL-3.0 许可证发布。详情请参阅 [LICENSE](LICENSE) 文件。

---