# Neo-DumasTrans

> A PDF translation tool that accurately parses text and image-based PDFs, leverages large language models for high-quality translation, and preserves original layout with pixel-perfect fidelity—supporting formulas, tables, images, multi-page mixed layouts, and massive files.

[中文](README_zh.md) | English

---

## ✨ Core Features

- **Fully Automated End-to-End Pipeline**  
  From raw PDF input to translated, overlaid PDF output—no manual intervention required.

- **Powered by Efficient MinerU Engine with Three Parsing Modes**
  - `txt`: Text-based PDFs → parsed using **local MinerU** for structured content  
  - `ocr`: Scanned/image PDFs → processed via **local MinerU + OCR** to recover text and layout  
  - `vlm`: Complex layouts (with formulas, tables, mixed content) → uses **MinerU online API** for high-precision structure (requires API token)

- **Local LLM Translation (Optimized for HunYuan-MT)**  
  - Supports GGUF-format local models; **specifically tuned for `Hunyuan-MT-7B.Q4_K_S.gguf`** with structured prompts and post-filtering  
  - Translation quality rivals large cloud models—ideal for offline use  
  - Available in **Full Version** (includes the model) and **Lightweight Version** (bring your own model)

- **High-Fidelity Background-Aware Overlay**  
  Only **translatable text regions** are modified:  
  - Samples local background color (not plain white) for natural blending  
  - Non-text areas (images, decorations, code blocks, etc.) remain **completely untouched**  
  - Avoids the jarring "white-out" effect, preserving visual consistency

- **Pixel-Precise Translation Overlay**  
  Translated text is rendered exactly over the original position, maintaining the PDF’s visual integrity.

- **Automatic Chunking & Parallel Processing**  
  Large files are split by pages (default: 25 pages/chunk) and processed concurrently to prevent memory overflow.

- **Smart Intermediate File Management**  
  On startup, the workspace is automatically cleaned:  
  - Temporary files older than **7 days** are deleted  
  - If total workspace size exceeds **10GB**, cleanup is triggered  
  → Enables recovery after crashes while preventing disk exhaustion.

---

## 🚀 Technical Advantages

### 1. Structured JSON Batch Translation (Online Mode)
- Multiple translatable segments are batched into a structured JSON array for LLM inference.  
- Output is validated to ensure format consistency with input.  
- Reduces token usage (less prompt repetition) and prevents paragraph misalignment or tag loss.

### 2. HunYuan-MT–Optimized Local Inference
- Runs GGUF models via **llama.cpp**, supporting both CPU and GPU  
- Custom prompt templates and output parsers tailored for `Hunyuan-MT-7B.Q4_K_S.gguf`  
- ⚠️ Other GGUF models may underperform due to format or instruction mismatches

### 3. Background-Aware Rendering for Visual Fidelity
- Draws overlay layers matching the surrounding background color  
- Final PDF = **original page (with images/watermarks/decorations)** + **seamlessly blended translation layer**  
- Achieves a “disappear-and-replace” effect—natural, not obstructive

### 4. Two-Stage Font & Layout Calibration (Zero Overflow Guarantee)
- **Stage 1 (Estimation)**: Uses Pillow to roughly estimate text width/height and set initial font size.  
- **Stage 2 (Refinement)**: Launches a real browser via Playwright to measure actual rendered dimensions and iteratively adjusts font size—ensuring 100% containment within the original bounding box while maximizing fill.

### 5. Playwright + Chromium for Pixel-Accurate Output
- Converts HTML to PDF using Playwright-driven Google Chrome.  
- Leverages native browser rendering engine—fully compatible with MathJax formulas, complex tables, etc.  
- Delivers publication-grade visual precision, indistinguishable from manual typesetting.

---

## 📦 Quick Start

### Download Windows Version (Portable, No Installation)
Two versions available:

| Version | Description | Download |
|--------|-------------|--------|
| **Full** | Includes `Hunyuan-MT-7B.Q4_K_S.gguf` – ready to run | 🔗 [Baidu Netdisk (Full)](https://pan.baidu.com/s/1eN4mhNKk7DEcPbtmnP-R1g?pwd=nu9u) |
| **Light** | Model not included – bring your own | 🔗 [Baidu Netdisk (Light)](https://pan.baidu.com/s/1eN4mhNKk7DEcPbtmnP-R1g?pwd=nu9u) |

🔑 Extraction Code: `nu9u`

---

## ⚙️ Usage

1. Extract the archive and double-click `run.bat` to launch the GUI.
2. In settings, choose:
   - **PDF Parsing Mode**: `txt` / `ocr` / `vlm`
   - **Translation Backend**: Cloud API or Local Model (recommended: `Hunyuan-MT-7B.Q4_K_S.gguf`)
3. Select a PDF file and click “Start Translation”.

> 📌 The Full version auto-loads the model on first run—no extra setup needed.

---

## 🎯 Ideal Use Cases

- High-quality translation of academic papers & technical docs (preserving formulas/figures)  
- Bilingual processing of scanned contracts or reports  
- Offline, high-fidelity localization without internet  
- Automated document translation pipelines (with resume-on-failure support)

---

## 🧱 Architecture Highlights

- **Pipeline-Based Async Design**: 7 stages decoupled via `asyncio.Queue`, enabling concurrency and fault isolation.  
- **Modular Components**: Each function (PDF prep, MinerU parsing, translation, overlay, rendering, PDF conversion, merging) is an independent module.  
- **Fault Tolerance**: Successfully processed files are skipped; single chunk failure won’t halt the entire job.  
- **Logging**: Detailed execution logs via `loguru` for easy debugging.

---

## 💡 Acknowledgements

- [MinerU](https://github.com/opendatalab/MinerU): Powerful PDF structural parser  
- [Playwright](https://playwright.dev/): Reliable browser automation  
- [MathJax](https://www.mathjax.org/): High-quality math rendering  
- [llama.cpp](https://github.com/ggerganov/llama.cpp): Efficient local LLM inference  
- Tencent HunYuan Team: Open-sourced [HunYuan-MT translation models](https://hunyuan.tencent.com/)