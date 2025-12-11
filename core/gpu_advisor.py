# core/gpu_advisor.py

import subprocess
import logging
import time
from typing import Optional, Tuple

try:
    import pynvml
    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False

logger = logging.getLogger(__name__)

# 配置参数（可根据实测调整）
FULL_GPU_REQUIRED_FREE_GB = 6.2      # 50层所需空闲显存
REDUCED_GPU_REQUIRED_FREE_GB = 3.2   # 10层所需空闲显存
MIN_TOTAL_FOR_FULL_GPU = 7.0         # 总显存需 ≥7GB 才考虑 full 模式
MIN_TOTAL_FOR_REDUCED_GPU = 3.0      # 总显存需 ≥3GB 才考虑 reduced 模式
WAIT_INTERVAL_SEC = 60                # 每隔1分钟检查一次
MAX_WAIT_TIME_SEC = 7200              # 最多等待2小时


def get_cuda_driver_version() -> Optional[str]:
    """
    获取 NVIDIA 驱动支持的最高 CUDA 版本（注意：不是 nvcc 编译器版本！）
    使用 nvidia-smi 查询，更准确反映驱动兼容性。
    返回如 "11.8", "12.4" 等，若失败返回 None。
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader,nounits"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return None

        # 获取驱动版本（如 525.147.05）
        driver_ver = result.stdout.strip().split('\n')[0]
        if not driver_ver:
            return None

        # 根据 NVIDIA 官方文档，驱动版本对应支持的 CUDA 最高版本
        # 我们只关心是否 ≥ 11.8，可通过驱动版本粗略判断
        # 更可靠方式：用 pynvml 获取 CUDA 版本（如果可用）
        try:
            pynvml.nvmlInit()
            cuda_ver = pynvml.nvmlSystemGetCudaDriverVersion()
            # cuda_ver 是整数，如 11080 表示 11.8.0
            major = cuda_ver // 1000
            minor = (cuda_ver % 100) // 10
            pynvml.nvmlShutdown()
            return f"{major}.{minor}"
        except:
            # fallback: 通过驱动版本查表（简化处理）
            # 驱动 ≥ 450.80.02 支持 CUDA 11.0，≥ 520 支持 11.8+
            # 这里保守判断：只要能跑 nvidia-smi，且驱动较新，就认为支持 11.8+
            # 实际上 llama-cpp-python 的 cuBLAS 库只依赖运行时兼容性
            # 所以我们主要看是否安装了 CUDA 11.8 的 llama-cpp-python
            # 此处简化：只要 NVML 可用，就认为驱动足够新
            if NVML_AVAILABLE:
                return "11.8"  # 假设驱动足够新（实际由 llama-cpp-python 是否编译决定）
            return None
    except Exception as e:
        logger.debug(f"Failed to get CUDA driver version: {e}")
        return None


def is_cuda_11_8_compatible() -> bool:
    """判断当前环境是否兼容 CUDA 11.8（用于 llama-cpp-python 的 cuBLAS）"""
    try:
        # 最终还是要看是否能成功创建 GPU 上下文
        # 但我们可以先检查驱动
        ver_str = get_cuda_driver_version()
        if ver_str is None:
            return False
        major, minor = map(int, ver_str.split('.'))
        return (major > 11) or (major == 11 and minor >= 8)
    except:
        return False


def get_gpu_memory_info() -> Tuple[float, float]:
    """返回 (total_gb, free_gb)，单位 GB"""
    if not NVML_AVAILABLE:
        return 0.0, 0.0

    try:
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        if device_count == 0:
            return 0.0, 0.0
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        total_gb = mem.total / (1024**3)
        free_gb = mem.free / (1024**3)
        return total_gb, free_gb
    except Exception as e:
        logger.debug(f"NVML error: {e}")
        return 0.0, 0.0
    finally:
        try:
            pynvml.nvmlShutdown()
        except:
            pass


def wait_for_gpu_memory(target_free_gb: float, timeout_sec: int = MAX_WAIT_TIME_SEC) -> bool:
    """等待直到空闲显存 ≥ target_free_gb，超时返回 False"""
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        total, free = get_gpu_memory_info()
        logger.info(f"Waiting for GPU memory: free={free:.1f}GB (need ≥{target_free_gb}GB)")
        if free >= target_free_gb:
            return True
        time.sleep(WAIT_INTERVAL_SEC)
    return False


def decide_n_gpu_layers_with_waiting() -> int:
    """
    主决策函数：根据 CUDA 和显存情况，决定 n_gpu_layers。
    可能会阻塞等待显存释放。
    """
    # Step 1: 检查 CUDA 兼容性
    if not is_cuda_11_8_compatible():
        logger.info("CUDA 11.8+ not supported. Using CPU mode.")
        return 0

    # Step 2: 获取显存信息
    total_gb, free_gb = get_gpu_memory_info()
    logger.info(f"GPU detected: total={total_gb:.1f}GB, free={free_gb:.1f}GB")

    if total_gb < MIN_TOTAL_FOR_REDUCED_GPU:
        logger.info("Total GPU memory too low (<3GB). Using CPU mode.")
        return 0

    # Step 3: 高性能模式（50层）
    if total_gb >= MIN_TOTAL_FOR_FULL_GPU:
        logger.info("System qualifies for full GPU mode (50 layers).")
        if free_gb >= FULL_GPU_REQUIRED_FREE_GB:
            logger.info("Enough free memory. Starting full GPU mode immediately.")
            return 50
        else:
            logger.info("Not enough free memory. Waiting for ≥6GB free...")
            if wait_for_gpu_memory(FULL_GPU_REQUIRED_FREE_GB):
                logger.info("Free memory reached. Starting full GPU mode.")
                return 50
            else:
                logger.warning("Timeout waiting for GPU memory. Falling back to CPU.")
                return 0

    # Step 4: 低性能模式（10层）
    elif total_gb >= MIN_TOTAL_FOR_REDUCED_GPU:
        logger.info("System qualifies for reduced GPU mode (10 layers).")
        if free_gb >= REDUCED_GPU_REQUIRED_FREE_GB:
            logger.info("Enough free memory. Starting reduced GPU mode immediately.")
            return 10
        else:
            logger.info("Not enough free memory. Waiting for ≥3GB free...")
            if wait_for_gpu_memory(REDUCED_GPU_REQUIRED_FREE_GB):
                logger.info("Free memory reached. Starting reduced GPU mode.")
                return 10
            else:
                logger.warning("Timeout waiting for GPU memory. Falling back to CPU.")
                return 0

    # Fallback
    return 0