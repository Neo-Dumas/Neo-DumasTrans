# install_deps.py
import os
import sys
import subprocess
import urllib.request

# ================== 配置区 ==================
HERE = os.path.dirname(os.path.abspath(__file__))
PYTHON_EXE = os.path.join(HERE, "python-3.10.11", "python.exe")
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
GET_PIP_PATH = os.path.join(HERE, "get-pip.py")

TORCH_INDEX_URL = "https://download.pytorch.org/whl/cu118"

DEPENDENCIES = [
    "PyMuPDF==1.26.5",
    "dill==0.4.0",
    "doclayout_yolo==0.0.4",
    "ftfy==6.3.1",
    "gradio_pdf==0.0.22",
    "langdetect==1.0.9",
    os.path.join(HERE, "llama_cpp_python-0.3.16-cp310-cp310-win_amd64.whl"),
    os.path.join(HERE, "lmdeploy-0.11.0-cp310-cp310-win_amd64.whl"),
    "mineru[core,lmdeploy]==2.6.5",
    "nvidia-ml-py==13.580.82",
    "omegaconf==2.3.0",
    "pefile==2024.8.26",
    "playwright==1.55.0",
    "pyclipper==1.3.0.post6",
    "PyQt5==5.15.11",
    "pywin32-ctypes==0.2.3",
    "scikit-learn==1.7.2",
    "shapely==2.1.2",
    "tinycss2==1.4.0",
    "ultralytics==8.3.225",
]
# ===========================================

def run(cmd, cwd=None, check=True):
    """运行命令，可选是否因错误退出"""
    print(f"[+] Running: {' '.join(str(x) for x in cmd)}")
    result = subprocess.run(cmd, cwd=cwd or HERE, text=True)
    if check and result.returncode != 0:
        print("[!] 命令执行失败！")
        sys.exit(1)
    return result.returncode == 0

def download_file(url, dest):
    """下载文件"""
    if not os.path.exists(dest):
        print(f"[*] 下载 {os.path.basename(dest)} ...")
        urllib.request.urlretrieve(url, dest)

def has_pip_installed():
    """安全检测 pip 是否可用"""
    result = subprocess.run(
        [PYTHON_EXE, "-m", "pip", "--version"],
        cwd=HERE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    return result.returncode == 0

def is_torch_gpu_installed():
    """检查 torch 是否为 cu118 版本"""
    try:
        result = subprocess.run(
            [PYTHON_EXE, "-c", "import torch; print(torch.__version__)"],
            capture_output=True,
            text=True,
            cwd=HERE
        )
        if result.returncode == 0:
            return "+cu118" in result.stdout.strip()
    except Exception:
        pass
    return False

def main():
    if not os.path.exists(PYTHON_EXE):
        print(f"[!] 未找到 Python 解释器: {PYTHON_EXE}")
        sys.exit(1)

    # === 关键：检查并安装 pip ===
    if not has_pip_installed():
        print("[*] pip 未安装，正在下载并安装...")
        download_file(GET_PIP_URL, GET_PIP_PATH)
        run([PYTHON_EXE, GET_PIP_PATH, "--no-warn-script-location"])
    else:
        print("[OK] pip 已安装。")

    # 安装所有依赖
    print("[*] 正在安装内嵌依赖列表中的包...")
    pip_install_cmd = [PYTHON_EXE, "-m", "pip", "install", "--no-cache-dir"]
    pip_install_cmd.extend(DEPENDENCIES)
    run(pip_install_cmd)

    # 安装 Playwright 浏览器
    print("[*] 正在安装 Playwright Chromium 浏览器...")
    run([PYTHON_EXE, "-m", "playwright", "install", "chromium"])

    # 安装或跳过 PyTorch GPU 版
    if is_torch_gpu_installed():
        print("[OK] 已检测到 CUDA 11.8 版本的 PyTorch，跳过安装。")
    else:
        print("[*] 尝试安装 CUDA 11.8 版本的 PyTorch（失败将保留 CPU 模式）...")
        success = run([
            PYTHON_EXE, "-m", "pip", "install", "--force-reinstall", "--no-deps",
            "torch", "torchvision", "torchaudio",
            "--index-url", TORCH_INDEX_URL,
            "--trusted-host", "download.pytorch.org",
            "--no-cache-dir"
        ], check=False)

        if success:
            print("[OK] CUDA 11.8 版本 PyTorch 安装成功！GPU 加速已启用。")
        else:
            print("[WARN] CUDA 版本 PyTorch 安装失败，将使用 CPU 模式运行（功能仍可用）。")

    print("\n[OK] 所有组件安装完成！系统已就绪。")

if __name__ == "__main__":
    main()