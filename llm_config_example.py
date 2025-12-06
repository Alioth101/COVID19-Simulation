#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM API配置中心 - 集中管理所有API密钥和模型配置
[示例文件 - 请复制为 llm_config.py 并填入真实密钥]

使用说明:
1. 将此文件复制并重命名为 llm_config.py
2. 在 LLM_CONFIGS 中填入您的 API Key
3. 运行 python llm_config.py 验证配置
"""

# ============================================================================
# 🔧 代理生成函数 - 为每个密钥生成不同的代理
# ============================================================================

def get_proxy(index):
    """
    为每个API密钥生成固定的不同代理
    
    Args:
        index: 密钥索引（0, 1, 2, ...）
    
    Returns:
        str: 代理URL，格式 http://u{index}:password@192.168.0.{71+index}:3128
    
    示例:
        get_proxy(0) -> "http://u0:password@192.168.0.71:3128"
    """
    user = index
    num = 71 + index
    # 请根据您的实际代理环境修改此处
    proxy_url = f'http://u{user}:password@192.168.0.{num}:3128'
    return proxy_url

# ============================================================================
# 🔧 API配置区 - 在此配置您的API密钥
# ============================================================================

LLM_CONFIGS = [
    # ========================================================================
    # 配置组1 (必填)
    # ========================================================================
    {
        "name": "Account_1",  # 配置组名称(仅用于显示)
        "api_key": "YOUR_API_KEY_HERE",  # 📝 必改: 第一个API密钥
        "base_url": "https://api.deepseek.com/v1",   # API 基础地址
        "model": "deepseek-chat", # 模型名称
        "proxy": None,  # 如需代理可设置为: get_proxy(0)
    },
    
    # ========================================================================
    # 配置组2 (可选)
    # ========================================================================
    {
        "name": "Account_2",
        "api_key": "",  # 📝 可选: 第二个API密钥
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "proxy": None,
    },
    
    # 您可以继续添加更多配置组...
]

LLM_PARAMETERS = {
    "temperature": 0.6,      # 采样温度 (0.0-2.0)
    "max_concurrent": 50,  # 最大并发数 (None=自动: 有效配置数×10)
}

# ============================================================================
# 🆕 自动密钥轮转配置
# ============================================================================
import os
os.environ["LLM_KEY_ROTATION_INTERVAL"] = "1000"  # 每n次请求自动切换密钥

# ============================================================================
# ⚙️ 以下是内部函数,无需修改
# ============================================================================

def validate_and_deduplicate_configs():
    """
    验证配置并去重
    
    规则:
    1. 至少需要1个有效配置
    2. api_key不能为空或示例值
    3. 自动去重相同的api_key
    
    Returns:
        list: 去重后的有效配置列表
    """
    if not LLM_CONFIGS:
        raise ValueError("LLM_CONFIGS 不能为空,至少需要1个配置")
    
    valid_configs = []
    seen_keys = set()
    
    for i, config in enumerate(LLM_CONFIGS, 1):
        # 检查必填字段
        if "api_key" not in config:
            raise ValueError(f"配置组{i} 缺少 api_key 字段")
        
        api_key = config["api_key"].strip()  # 自动去除首尾空格
        
        # 跳过示例值和空值
        if not api_key or api_key == "YOUR_API_KEY_HERE" or api_key.startswith("sk-xxx"):
            print(f"⚠️  配置组{i} ({config.get('name', f'Config{i}')}) 使用示例密钥,已跳过")
            continue
        
        # 去重
        if api_key in seen_keys:
            print(f"⚠️  配置组{i} ({config.get('name', f'Config{i}')}) 密钥重复,已自动去重")
            continue
        
        # 验证base_url
        base_url = config.get("base_url", "https://api.deepseek.com")
        if not base_url.startswith("http"):
            raise ValueError(f"配置组{i} 的 base_url 格式错误: {base_url}")
        
        # 验证model
        model = config.get("model", "deepseek-ai/DeepSeek-V3.2-Exp")
        if not model:
            raise ValueError(f"配置组{i} 的 model 不能为空")
        
        # 获取代理配置（可选）
        proxy = config.get("proxy", None)
        
        # 添加到有效配置
        valid_configs.append({
            "name": config.get("name", f"Config{i}"),
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
            "proxy": proxy,  # 添加代理配置
        })
        seen_keys.add(api_key)
    
    if not valid_configs:
        # 在示例模式下不抛出错误，只是打印警告
        print("提示: 当前未配置有效API密钥，仅供查看配置结构。")
        return []
    
    return valid_configs


def get_llm_config():
    """
    获取去重后的有效LLM配置
    
    Returns:
        dict: {
            "configs": [...],  # 有效配置列表
            "parameters": {...}  # 全局参数
        }
    """
    valid_configs = validate_and_deduplicate_configs()
    
    # 自动计算并发数
    max_concurrent = LLM_PARAMETERS.get("max_concurrent")
    if max_concurrent is None:
        max_concurrent = len(valid_configs) * 10 if valid_configs else 1
    
    return {
        "configs": valid_configs,
        "parameters": {
            "temperature": LLM_PARAMETERS.get("temperature", 0.6),
            "max_concurrent": max_concurrent,
        }
    }


def print_config_summary():
    """打印配置摘要"""
    try:
        config = get_llm_config()
        valid_configs = config["configs"]
        params = config["parameters"]
        
        if not valid_configs:
            print("当前为示例配置，请修改 llm_config.py 填入真实密钥。")
            return False

        print("\n" + "=" * 80)
        print("  LLM配置验证成功")
        print("=" * 80)
        print()
        
        print(f"✅ 有效配置数: {len(valid_configs)}")
        print()
        
        for i, cfg in enumerate(valid_configs, 1):
            print(f"  配置 {i}: {cfg['name']}")
            print(f"    API Key: {cfg['api_key'][:10]}...{cfg['api_key'][-4:]}")
            print(f"    Base URL: {cfg['base_url']}")
            print(f"    Model: {cfg['model']}")
            print(f"    Proxy: {cfg.get('proxy', 'None')}")
            print()
        
        print(f"⚙️  全局参数:")
        print(f"    Temperature: {params['temperature']}")
        print(f"    并发数: {params['max_concurrent']}")
        print()
        
        return True
        
    except ValueError as e:
        print(f"配置验证错误: {e}")
        return False


if __name__ == "__main__":
    print_config_summary()
