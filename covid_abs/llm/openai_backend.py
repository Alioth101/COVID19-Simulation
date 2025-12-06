"""
OpenAI backend implementation
Adapted from AgentReview project
"""

import os
import json
import re
from typing import List, Dict
from tenacity import retry, stop_after_attempt, wait_random_exponential

from .base import IntelligenceBackend


class OpenAIBackend(IntelligenceBackend):
    """
    OpenAI API backend
    
    Supports:
    - Standard OpenAI API
    - Azure OpenAI
    - Third-party OpenAI-compatible APIs (OpenRouter, DeepSeek, etc.)
    """
    
    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        api_key: str = None,
        base_url: str = None,
        azure_endpoint: str = None,
        azure_deployment: str = None
    ):
        """
        Initialize OpenAI backend
        
        Args:
            model_name: Model to use (e.g., "gpt-4o-mini", "gpt-4o", "deepseek-chat")
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Max response tokens
            api_key: API key (OpenAI/Azure/third-party)
            base_url: Custom API base URL (for third-party providers)
                Examples:
                - OpenRouter: "https://openrouter.ai/api/v1"
                - DeepSeek: "https://api.deepseek.com"
                - Local proxy: "http://localhost:8000/v1"
            azure_endpoint: Azure OpenAI endpoint (for Azure only)
            azure_deployment: Azure deployment name (for Azure only)
        
        Environment variables (auto-detected if not provided):
            - OPENAI_API_KEY: API key
            - OPENAI_BASE_URL: Base URL
            - AZURE_ENDPOINT: Azure endpoint
            - AZURE_DEPLOYMENT: Azure deployment
        """
        super().__init__(model_name, temperature, max_tokens)
        
        # Get configuration from environment if not provided
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.azure_endpoint = azure_endpoint or os.getenv("AZURE_ENDPOINT")
        self.azure_deployment = azure_deployment or os.getenv("AZURE_DEPLOYMENT")
        
        if not self.api_key:
            raise ValueError(
                "API key not provided. Please either:\n"
                "  1. Set OPENAI_API_KEY environment variable, or\n"
                "  2. Pass api_key parameter when creating backend"
            )
        
        # Initialize OpenAI client
        self._init_client()
    
    def _init_client(self):
        """Initialize OpenAI, Azure OpenAI, or third-party client"""
        try:
            from openai import OpenAI, AzureOpenAI
        except ImportError:
            raise ImportError(
                "openai package not installed. Run: pip install openai>=1.0.0"
            )
        
        if self.azure_endpoint:
            # Azure OpenAI
            print(f"[OpenAI Backend] Using Azure OpenAI: {self.azure_endpoint}")
            self.client = AzureOpenAI(
                api_key=self.api_key,
                api_version="2024-02-15-preview",
                azure_endpoint=self.azure_endpoint
            )
            self.model = self.azure_deployment
        
        elif self.base_url:
            # Third-party OpenAI-compatible API
            print(f"[OpenAI Backend] Using custom base URL: {self.base_url}")
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            self.model = self.model_name
        
        else:
            # Standard OpenAI API
            print(f"[OpenAI Backend] Using standard OpenAI API")
            self.client = OpenAI(api_key=self.api_key)
            self.model = self.model_name
    
    def query(
        self,
        prompt: str = None,
        agent_name: str = None,
        role_desc: str = None,
        history_messages: List[Dict[str, str]] = None,
        global_prompt: str = None,
        request_msg: str = None,
        temperature: float = None,
        max_tokens: int = None
    ) -> str:
        """
        Query OpenAI API
        
        Supports two interfaces:
        1. Simple interface (for GraphSimulation):
           query(prompt, temperature=0.7, max_tokens=300)
        
        2. Complex interface (for AgentReview):
           query(agent_name, role_desc, history_messages, global_prompt, request_msg)
        
        Returns:
            str: LLM response
        """
        # Use provided temperature/max_tokens or fall back to instance defaults
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        # Construct messages
        messages = []
        
        # Interface 1: Simple prompt-based (for GraphSimulation)
        if prompt:
            messages.append({"role": "user", "content": prompt})
        
        # Interface 2: Complex multi-part (for AgentReview)
        else:
            # System message: combine global prompt + role description
            system_content = f"{global_prompt}\n\n{role_desc}" if global_prompt else role_desc
            messages.append({"role": "system", "content": system_content})
            
            # Add history (recent decisions for context)
            if history_messages:
                for hist in history_messages[-3:]:  # Only keep last 3 for context
                    messages.append({
                        "role": "assistant",
                        "content": hist.get("content", "")
                    })
            
            # Add current request
            messages.append({"role": "user", "content": request_msg})
        
        # Call API with retry
        response = self._get_response_with_retry(messages, temp, tokens)
        return response
    
    @retry(stop=stop_after_attempt(3), wait=wait_random_exponential(min=1, max=10))
    def _get_response_with_retry(self, messages: List[Dict], temperature: float, max_tokens: int) -> str:
        """
        Call OpenAI API with retry logic
        
        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Max response tokens
            
        Returns:
            str: Response content
        """
        try:
            completion = self.client.chat.completions.create(
                timeout=120.0,  # 120 second timeout per request
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Extract response content
            content = completion.choices[0].message.content
            
            # Validate response
            if content is None:
                raise ValueError(
                    "API returned None content. This may indicate:\n"
                    "  1. Model refused to respond (content policy)\n"
                    "  2. API gateway/proxy issue\n"
                    "  3. Token limit exceeded"
                )
            
            return content
            
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            
            # 🔧 [ENHANCED] 详细的错误诊断
            print(f"\n{'='*80}")
            print(f"[OpenAI API ERROR] Request failed")
            print(f"{'='*80}")
            print(f"🔑 API Key: {self.api_key[:10]}...{self.api_key[-4:]}")
            print(f"🏷️  Model: {self.model}")
            print(f"🌐 Base URL: {getattr(self, 'base_url', 'Official OpenAI API')}")
            print(f"❌ Error Type: {error_type}")
            print(f"📝 Error Message: {error_msg}")
            
            # 特殊错误类型诊断
            if "404" in str(e):
                print(f"\n🚨 资源不存在 (404 Not Found)")
                print(f"   可能原因:")
                print(f"     1. Base URL错误: {getattr(self, 'base_url', 'N/A')}")
                print(f"     2. 模型名称不可用: {self.model}")
                print(f"     3. API端点路径错误 (检查是否需要 /v1 后缀)")
                print(f"   解决方案:")
                print(f"     - 使用官方OpenAI: 删除 OPENAI_BASE_URL 环境变量")
                print(f"     - OpenRouter: base_url='https://openrouter.ai/api/v1'")
                print(f"     - DeepSeek: base_url='https://api.deepseek.com'")
            
            elif "401" in str(e) or "Unauthorized" in str(e):
                print(f"\n🚨 认证失败 (401 Unauthorized)")
                print(f"   问题密钥: {self.api_key[:15]}...{self.api_key[-8:]}")
                print(f"   完整密钥（用于检查）: {self.api_key}")
                print(f"   可能原因:")
                print(f"     1. API密钥无效或已过期")
                print(f"     2. 密钥格式错误（检查是否有多余空格/换行符）")
                print(f"     3. 密钥与base_url不匹配")
                print(f"   解决方案:")
                print(f"     - 检查环境变量或llm_config.py中的配置")
                print(f"     - 登录API提供商确认密钥有效性")
                print(f"     - 尝试重新生成密钥")
            
            elif "403" in str(e) or "Forbidden" in str(e):
                print(f"\n🚨 访问被拒绝 (403 Forbidden)")
                print(f"   可能原因:")
                print(f"     1. 账户余额不足")
                print(f"     2. 密钥权限不足（可能是只读密钥）")
                print(f"     3. IP地址被限制")
                print(f"     4. 模型访问权限未开通（如GPT-4需要特殊权限）")
                print(f"   解决方案:")
                print(f"     - 检查账户余额")
                print(f"     - 生成具有完整权限的新密钥")
                print(f"     - 联系API提供商确认访问权限")
            
            elif "429" in str(e):
                print(f"\n⚠️  速率限制 (429 Too Many Requests)")
                print(f"   可能原因:")
                print(f"     1. TPM (Tokens Per Minute) 超限")
                print(f"     2. RPM (Requests Per Minute) 超限")
                print(f"     3. 日配额用尽")
                print(f"   建议:")
                print(f"     - 使用 MultiKeyOpenAIBackend 进行多密钥负载均衡")
                print(f"     - 降低 MAX_CONCURRENT_LLM 参数")
                print(f"     - 等待速率限制窗口重置")
            
            elif "timeout" in error_msg.lower():
                print(f"\n⏱️  请求超时 (Timeout)")
                print(f"   可能原因:")
                print(f"     1. 网络连接不稳定")
                print(f"     2. API服务器响应慢")
                print(f"     3. 请求过于复杂（prompt tokens过多）")
                print(f"   当前超时设置: 120秒")
            
            elif "connection" in error_msg.lower():
                print(f"\n🌐 网络连接错误")
                print(f"   可能原因:")
                print(f"     1. 无法访问API服务器")
                print(f"     2. 防火墙/代理阻止连接")
                print(f"     3. DNS解析失败")
                print(f"   解决方案:")
                print(f"     - 检查网络连接")
                print(f"     - 验证base_url可访问性")
                print(f"     - 检查代理设置")
            
            print(f"{'='*80}\n")
            raise
