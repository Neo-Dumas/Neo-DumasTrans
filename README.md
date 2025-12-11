# Neo-DumasTrans

English | [中文](README_zh.md)

> A PDF translation tool capable of accurately parsing text- and image-based PDFs, performing large-model translation with high-fidelity layout preservation—fully supporting mathematical formulas, tables, images, extremely large files, mixed multi-page layouts, and complex formatting.

---

## ✨ Core Features & Technical Highlights

### 📄 Intelligent PDF Preprocessing (Handles Real-World Complex Documents)
- Automatically normalizes coordinate systems, eliminating “dirty data” such as negative coordinates or non-standard numeric values  
- Smartly detects page orientation and rotates all pages to upright (top-to-bottom) alignment, significantly improving robustness in downstream parsing  
- Effectively handles challenging scenarios like skewed scans, rotated embedded images, and mixed-layout documents

### ⚡ Triple-Mode MinerU Engine (Adapts to Diverse PDF Types)
- `txt`: Pure-text PDF → Extract structured content using **local MinerU**  
- `ocr`: Scanned/image-based PDF → Restore text and layout via **local MinerU + OCR**  
- `vlm`: Complex layouts (with formulas/tables/mixed content) →  
  - **Leave Token blank**: Enable **local VLM mode** — **runs natively on Windows without WSL2**, leveraging precompiled LMDeploy (requires CUDA 11.8+) for high-performance offline structural recognition  
  - **Enter Token**: Use **MinerU official online API** to bypass local hardware requirements  

### 🌐 Efficient Structured Translation Pipeline (Cloud Translation Mode)
- Batches multiple translatable segments into a structured JSON array submitted to the LLM  
- Automatically validates format consistency of returned content, preventing paragraph misalignment, tag loss, or sequence errors  
- Significantly reduces token consumption (minimizing redundant prompt overhead) and boosts throughput efficiency

### 🧠 HunYuan-MT Optimized Local Inference (Local Translation Mode)
- Loads GGUF models via **llama.cpp**, supporting both CPU and GPU inference  
- Custom prompt templates, output filtering, and post-processing logic tailored for `Hunyuan-MT-7B.Q4_K_S.gguf`  
- Delivers translation quality comparable to mainstream cloud LLMs, fully suited for offline high-fidelity use  
- ⚠️ Other GGUF models may underperform due to instruction format mismatches

### 🎨 High-Fidelity Visual Overlay
- Applies intelligent overlay **only to regions requiring translation**: samples local background color to generate seamless transitional fill  
- **100% preserves original appearance** of non-text elements—images, watermarks, decorations, code blocks, etc.  
- Achieves a visually seamless “original disappears, translation appears” effect, completely eliminating the jarring “white-out” look

### 📏 Pixel-Precise Layout Rendering
- **Two-stage font size calibration**:  
  1️⃣ Pillow provides coarse text dimension estimation → sets initial font size upper bound  
  2️⃣ Playwright + Chromium performs real-time rendering measurement → iteratively fine-tunes to ensure translated text **fits 100% within original bounding box**, with no overflow or truncation  
- Leverages browser-native layout engine, fully supporting MathJax formulas, complex tables, and other advanced elements  
- Output PDF achieves pixel-level positioning accuracy, rivaling manual typesetting

### ⚙️ Efficient Asynchronous Pipeline Architecture
- **Concurrent preprocessing at start** (parallel standardization across multiple files)  
- **Asynchronous mid-stage pipeline**: MinerU parsing → leaf block extraction → background overlay → translation → HTML generation → PDF rendering  
- **Sequential final merge** to guarantee file integrity  
- Supports automatic chunking (default: 25 pages/chunk), resume-from-breakpoint, and failure isolation—effortlessly handles massive PDFs

### 🧹 Smart Temporary File Management
- Automatic cleanup on launch:  
  - Deletes temporary files **older than 7 days**  
  - If workspace total size **exceeds 10 GB**, clears entire cache  
- Balances debugging convenience with disk safety, preventing accidental storage exhaustion

---

## 💻 Recommended System Requirements

| Component | Requirement |
|----------|-------------|
| OS | Windows 10 / 11 (64-bit) |
| RAM | ≥ 16 GB (minimum 8 GB; 16+ GB recommended for large files) |
| GPU Driver | NVIDIA driver ≥ 520, **CUDA 11.8 or higher** |
| VRAM | ≥ 8 GB (12 GB recommended, e.g., RTX 3060 12G / 4070 12G) |
| Storage | SSD with ≥ 20 GB free space |

> ✅ **Local VLM mode includes precompiled LMDeploy—ready to run out-of-the-box without WSL2, Docker, or manual compilation**

---

## 📦 Quick Start

### Download Windows Portable Version (No Installation Required)
Two versions are available—choose based on your needs:

| Version | Description | Download Link |
|--------|-------------|---------------|
| **Full Package** | Includes built-in `HunYuan-MT-7B.Q4_K_S.gguf` model—ready to use immediately | 🔗 [Baidu Netdisk (Full)](https://pan.baidu.com/s/1eN4mhNKk7DEcPbtmnP-R1g?pwd=nu9u) |
| **Lightweight** | Does not include model—requires manual download | 🔗 [Baidu Netdisk (Light)](https://pan.baidu.com/s/1eN4mhNKk7DEcPbtmnP-R1g?pwd=nu9u) |

🔑 Extraction Code: `nu9u`

### Install from Repository (For Developers)

If you wish to build from source or contribute:

1. Clone the repository:
   ```bash
   git clone https://github.com/Neo-Dumas/Neo-DumasTrans.git
   cd Neo-DumasTrans
   ```

2. **Double-click `setup.bat` in the root directory**  
   - Automatically downloads portable Python 3.10.11 (if not present)  
   - Installs all required dependencies (including PyTorch CUDA 11.8, llama.cpp, MinerU, Playwright, etc.)  
   - Configures Playwright’s Chromium browser automatically  
   - Requires **no manual commands** and **no pre-installed Python or pip**

3. After setup, double-click `run.bat` to launch the GUI.

> 💡 Ideal for developers who want to debug, customize, or package modified versions. Regular users should prefer the portable full package above.

---

## ⚙️ Usage Instructions

1. After extraction, double-click `run.bat` or `双击启动程序.bat` to launch the GUI.
2. In settings, choose:
   - **PDF Parsing Mode**: `txt` / `ocr` / `vlm`
     - If `vlm` is selected **without a Token** → enables **native Windows local VLM mode** (requires CUDA 11.8+)
     - If Token is provided → uses MinerU online API
   - **Translation Backend**: Cloud API or local model (recommended: `HunYuan-MT-7B.Q4_K_S.gguf`)
3. Select your PDF file and click “Start Translation”.

> 📌 The full package includes the `HunYuan-MT-7B.Q4_K_S.gguf` model in the `models` folder—manually specify it on first use.

---

## 🎯 Ideal Use Cases

- High-quality translation of academic papers / technical documents (preserving formulas and figure placements)  
- Bilingual processing of scanned contracts and reports  
- Offline, high-fidelity localization in disconnected environments  
- Automated document translation pipelines (with resume support)

---

## 💡 Acknowledgements

This project builds upon several outstanding open-source tools:

- [MinerU](https://github.com/opendatalab/MinerU): Structured PDF parsing with formula/table support (v2.6.5+)  
- [PyMuPDF (fitz)](https://github.com/pymupdf/PyMuPDF): High-performance PDF processing library  
- [Playwright](https://playwright.dev/): Browser automation for pixel-accurate rendering  
- [MathJax](https://www.mathjax.org/): High-quality mathematical typesetting  
- [llama.cpp](https://github.com/ggerganov/llama.cpp): Efficient local LLM inference engine  
- [OpenCV](https://opencv.org/): Image processing for OCR preprocessing  
- [HunYuan-MT-7B](https://gitcode.com/tencent_hunyuan/HunYuan-MT-7B-fp8): Tencent’s open-source translation model

The portable (green) release bundles the following third-party binaries, each under its original license:
- [`Ghostscript`](https://www.ghostscript.com/) – GNU AGPLv3  
- [`PyMuPDF`](https://github.com/pymupdf/PyMuPDF) – GNU AGPLv3  
- [`OpenCV`](https://github.com/opencv/opencv) – Apache License 2.0  
- [`Playwright`](https://github.com/microsoft/playwright) – Apache License 2.0  
- [`llama.cpp`](https://github.com/ggerganov/llama.cpp) – MIT  
- [`MinerU`](https://github.com/opendatalab/MinerU) – Apache License 2.0  
- [`HunYuan-MT-7B`](https://gitcode.com/tencent_hunyuan/HunYuan-MT-7B-fp8) – Apache License 2.0  

We sincerely thank all contributors to these open-source projects!

---

## 📄 License  
This project is licensed under AGPL-3.0. See the [LICENSE](LICENSE) file for details.