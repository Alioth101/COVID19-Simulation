#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM API配置中心 - 集中管理所有API密钥和模型配置

使用说明:
1. 在下面的 LLM_CONFIGS 中配置1-6组API密钥
2. 系统会自动去重相同的密钥
3. 可以配置任意数量(1-6个或更多),系统自动检测
4. 运行 python llm_config.py 验证配置
5. 实验脚本会自动读取这个配置文件

优势:
- 集中管理,修改方便
- 自动去重,避免重复调用
- 支持不同base_url和模型
- 配置验证,防止错误
- 支持动态扩展(可添加更多API keys)
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
        get_proxy(1) -> "http://u1:password@192.168.0.72:3128"
        get_proxy(2) -> "http://u2:password@192.168.0.73:3128"
    """
    user = index
    num = 71 + index
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
        "api_key": "sk-f7a7ba6527064e7e9300646a770bef8a",  # 📝 必改: 第一个API密钥
        "base_url": "https://api.deepseek.com/v1",   # ✅ 修复: 添加 /v1 后缀
        "model": "deepseek-chat", # 模型名称
        "proxy": None,  # ✅ 代理: http://u0:password@192.168.0.71:3128
    },
    
    # ========================================================================
    # 配置组2 (可选)
    # ========================================================================
    {
        "name": "Account_2",  # 配置组名称
        "api_key": "",  # 📝 改为第二个密钥, 或与第1组相同
        "base_url": "https://api.siliconflow.cn/v1",   # 可与第1组不同
        "model": "deepseek-ai/DeepSeek-V3.2-Exp", # 可与第1组不同
        "proxy": None,  # ❌ 代理不可用，暂时禁用
    },
    
    # ========================================================================
    # 配置组3 (可选)
    # =======================================================================
    # =
    {
        "name": "Account_3",  # 配置组名称
        "api_key": "",   # 📝 改为第三个密钥, 或与前面相同
        "base_url": "https://api.siliconflow.cn/v1",   # 可与前面不同
        "model": "deepseek-ai/DeepSeek-V3.2-Exp", # 可与前面不同
        "proxy": None,  # ❌ 代理不可用，暂时禁用
    },
    
    # ========================================================================
    # 配置组4 (可选) - 提升并发性能
    # ========================================================================
    {
        "name": "Account_4",  # 配置组名称
        "api_key": "",   # 📝 改为第四个密钥, 留空或示例值则自动跳过
        "base_url": "https://api.siliconflow.cn/v1",   # 可与前面不同
        "model": "deepseek-ai/DeepSeek-V3.2-Exp", # 可与前面不同
        "proxy": None,  # ❌ 代理不可用，暂时禁用
    },
    
    # ========================================================================
    # 配置组5 (可选) - 进一步提升并发
    # ========================================================================
    {
        "name": "Account_5",  # 配置组名称
        "api_key": "",   # 📝 改为第五个密钥, 留空或示例值则自动跳过
        "base_url": "https://api.siliconflow.cn/v1",   # 可与前面不同
        "model": "deepseek-ai/DeepSeek-V3.2-Exp", # 可与前面不同
        "proxy": None,  # ❌ 代理不可用，暂时禁用
    },
    
    # ========================================================================
    # 配置组6 (可选) - 最大化并发能力
    # ========================================================================
    {
        "name": "Account_6",  # 配置组名称
        "api_key": "",   # 📝 改为第六个密钥, 留空或示例值则自动跳过
        "base_url": "https://api.siliconflow.cn/v1",   # 可与前面不同
        "model": "deepseek-ai/DeepSeek-V3.2-Exp", # 可与前面不同
        "proxy": None,  # 📝 可选: 代理配置
    },
]

LLM_PARAMETERS = {
    "temperature": 0.6,      # 采样温度 (0.0-2.0)
    # "max_tokens": 1200,    # ❌ DEPRECATED: 请在实验脚本中配置（run_graph_llm_batch.py的MAX_TOKENS）
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
        if not api_key or api_key.startswith("sk-xxx"):
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
        raise ValueError(
            "没有找到有效的API配置!\n"
            "请在 LLM_CONFIGS 中至少配置1个有效的api_key\n"
            "(不能是 'sk-xxx-your-xxx' 这样的示例值)"
        )
    
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
        max_concurrent = len(valid_configs) * 10
    
    return {
        "configs": valid_configs,
        "parameters": {
            "temperature": LLM_PARAMETERS.get("temperature", 0.6),
            # max_tokens 已迁移至实验脚本中配置，不再从这里读取
            "max_concurrent": max_concurrent,
        }
    }


def print_config_summary():
    """打印配置摘要"""
    try:
        config = get_llm_config()
        valid_configs = config["configs"]
        params = config["parameters"]
        
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
            if cfg.get('proxy'):
                # 隐藏代理的敏感信息（用户名/密码）
                proxy_str = cfg['proxy']
                if isinstance(proxy_str, dict):
                    proxy_str = proxy_str.get('http') or proxy_str.get('https')
                if '@' in str(proxy_str):
                    # 格式: http://user:pass@host:port -> http://***@host:port
                    proxy_display = str(proxy_str).split('@')[0].split('//')[0] + '//' + '***@' + str(proxy_str).split('@')[1]
                else:
                    proxy_display = proxy_str
                print(f"    Proxy: {proxy_display}")
            else:
                print(f"    Proxy: None (不使用代理)")
            print()
        
        print(f"⚙️  全局参数:")
        print(f"    Temperature: {params['temperature']}")
        print(f"    Max Tokens: 由实验脚本配置（run_graph_llm_batch.py::MAX_TOKENS）")
        print(f"    并发数: {params['max_concurrent']} (推荐值: {len(valid_configs)*8})")
        print()
        
        print(f"🚀 预期提升:")
        if len(valid_configs) == 1:
            print(f"    单密钥模式 (基准速度)")
        else:
            print(f"    {len(valid_configs)}x 速度提升")
        print()
        
        print("=" * 80)
        print()
        
        return True
        
    except ValueError as e:
        print("\n" + "=" * 80)
        print("  ❌ LLM配置验证失败")
        print("=" * 80)
        print()
        print(f"错误: {e}")
        print()
        print("请检查 llm_config.py 中的 LLM_CONFIGS 配置")
        print("=" * 80)
        print()
        return False


# ============================================================================
# 📝 配置示例
# ============================================================================

def show_config_examples():
    """显示配置示例"""
    print("\n" + "=" * 80)
    print("  配置示例")
    print("=" * 80)
    print()
    
    print("示例1: 使用单个API密钥")
    print("-" * 80)
    print("""
LLM_CONFIGS = [
    {
        "name": "MyAccount",
        "api_key": "sk-abc123...",  # 你的真实密钥
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-ai/DeepSeek-V3.2-Exp",
    },
    # 第2、3组设置为与第1组相同(系统自动去重)
    {
        "name": "MyAccount_Copy1",
        "api_key": "sk-abc123...",  # 与第1组相同
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-ai/DeepSeek-V3.2-Exp",
    },
    {
        "name": "MyAccount_Copy2",
        "api_key": "sk-abc123...",  # 与第1组相同
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-ai/DeepSeek-V3.2-Exp",
    },
]
# 结果: 系统检测到3个配置,自动去重后只使用1个
""")
    
    print("示例2: 使用2个不同的API密钥")
    print("-" * 80)
    print("""
LLM_CONFIGS = [
    {
        "name": "Account_1",
        "api_key": "sk-abc123...",  # 第一个密钥
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-ai/DeepSeek-V3.2-Exp",
    },
    {
        "name": "Account_2",
        "api_key": "sk-def456...",  # 第二个密钥(不同)
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-ai/DeepSeek-V3.2-Exp",
    },
    {
        "name": "Account_2_Copy",
        "api_key": "sk-def456...",  # 与第2组相同
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-ai/DeepSeek-V3.2-Exp",
    },
]
# 结果: 系统检测到3个配置,自动去重后使用2个
""")
    
    print("示例3: 使用3个不同的API密钥")
    print("-" * 80)
    print("""
LLM_CONFIGS = [
    {
        "name": "Account_1",
        "api_key": "sk-abc123...",  # 第一个密钥
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-ai/DeepSeek-V3.2-Exp",
    },
    {
        "name": "Account_2",
        "api_key": "sk-def456...",  # 第二个密钥
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-ai/DeepSeek-V3.2-Exp",
    },
    {
        "name": "Account_3",
        "api_key": "sk-ghi789...",  # 第三个密钥
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-ai/DeepSeek-V3.2-Exp",
    },
]
# 结果: 系统使用全部3个配置
""")
    
    print("=" * 80)
    print()


if __name__ == "__main__":
    import sys
    
    if "--help" in sys.argv or "-h" in sys.argv:
        show_config_examples()
    elif "--proxy-example" in sys.argv:
        # 显示代理配置示例
        print("\n" + "=" * 80)
        print("  代理配置示例")
        print("=" * 80)
        print()
        print("示例1: 为每个密钥配置固定代理")
        print("-" * 80)
        print("""
LLM_CONFIGS = [
    {
        "name": "Account_1",
        "api_key": "sk-xxx-key1",
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "deepseek-ai/DeepSeek-V3.2-Exp",
        "proxy": "http://u0:crawl@192.168.0.71:3128"
    },
    {
        "name": "Account_2",
        "api_key": "sk-xxx-key2",
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "deepseek-ai/DeepSeek-V3.2-Exp",
        "proxy": "http://u1:crawl@192.168.0.72:3128"
    },
]
""")
        
        print("\n示例2: 使用函数动态生成代理")
        print("-" * 80)
        print("""
import random

def get_proxy(index):
    user = index
    num = 71 + index
    return f'http://u{user}:crawl@192.168.0.{num}:3128'

LLM_CONFIGS = [
    {
        "name": f"Account_{i+1}",
        "api_key": f"sk-xxx-key{i+1}",
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "deepseek-ai/DeepSeek-V3.2-Exp",
        "proxy": get_proxy(i)
    }
    for i in range(5)
]
""")
        
        print("\n示例3: 随机代理（与您的get_proxy函数类似）")
        print("-" * 80)
        print("""
import random

def get_random_proxy():
    user = random.randint(0, 30)
    num = random.randint(71, 78)
    proxy_url = f'http://u{user}:crawl@192.168.0.{num}:3128'
    return {
        "http": proxy_url,
        "https": proxy_url,
    }

# 注意：每次调用会生成不同的随机代理
LLM_CONFIGS = [
    {
        "name": f"Account_{i+1}",
        "api_key": f"sk-xxx-key{i+1}",
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "deepseek-ai/DeepSeek-V3.2-Exp",
        "proxy": get_random_proxy()
    }
    for i in range(5)
]
""")
        
        print("\n更多示例请查看: proxy_config_example.py")
        print("=" * 80)
        
    else:
        # 验证当前配置
        success = print_config_summary()
        
        if not success:
            print("💡 提示:")
            print("   - 运行 'python llm_config.py --help' 查看配置示例")
            print("   - 运行 'python llm_config.py --proxy-example' 查看代理配置示例")
            sys.exit(1)

