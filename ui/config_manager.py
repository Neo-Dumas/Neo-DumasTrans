# ui/config_manager.py
import os
import json
from pathlib import Path

# 根目录（相对于当前文件）
ROOT_DIR = Path(__file__).parent.parent
SETTINGS_FILE = ROOT_DIR / "last_settings.json"
API_KEYS_FILE = ROOT_DIR / "api_keys.json"


def load_global_settings():
    """加载全局设置：路径、语言、LLM 提供商"""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"读取全局设置失败: {e}")
    return {}


def save_global_settings(settings):
    """保存全局设置"""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存全局设置失败: {e}")


def load_api_config(llm_key):
    """加载指定 LLM 的 API 配置"""
    if API_KEYS_FILE.exists():
        try:
            with open(API_KEYS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get(llm_key, {})
        except Exception as e:
            print(f"读取 API 配置失败: {e}")
    return {}


def save_api_config(llm_key, config):
    """保存指定 LLM 的 API 配置"""
    data = {}
    if API_KEYS_FILE.exists():
        try:
            with open(API_KEYS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            pass
    data[llm_key] = config
    try:
        with open(API_KEYS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存 API 配置失败: {e}")