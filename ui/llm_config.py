# ui/llm_config.py

LLM_DISPLAY_TO_KEY = {
    "DeepSeek": "deepseek",
    "通义千问（Qwen）": "qwen",
    "智谱（Zhipu）": "zhipu",
    "自定义": "custom"
}

LLM_KEY_TO_DISPLAY = {v: k for k, v in LLM_DISPLAY_TO_KEY.items()}

# 各 LLM 的默认配置
LLM_DEFAULTS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model_name": "deepseek-chat"
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model_name": "qwen-max"
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model_name": "glm-4"
    },
    "custom": {
        "base_url": "",
        "model_name": ""
    }
}