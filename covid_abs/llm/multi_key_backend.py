"""
Multi-Key OpenAI Backend - Load balancing across multiple API keys
支持多个API密钥轮询以突破TPM限制
"""

import os
import time
import traceback
import itertools
from typing import List, Dict
from threading import Lock
from datetime import datetime, timedelta

from .openai_backend import OpenAIBackend


class MultiKeyOpenAIBackend(OpenAIBackend):
    """
    Multi-key OpenAI backend with automatic load balancing
    
    Features:
    - Round-robin distribution across multiple API keys
    - Automatic failover to next key on error
    - Thread-safe key rotation
    - 2x-3x throughput improvement with 2-3 keys
    - 🛡️ Global cooldown protection (4th layer of protection)
    
    Protection Layers:
    1. Retry mechanism (max_retries)
    2. Exponential backoff
    3. Multi-key rotation
    4. 🆕 Global cooldown (10 min pause on critical errors)
    
    Usage:
        # Method 1: Environment variables
        export OPENAI_API_KEY_1="sk-xxx-key1"
        export OPENAI_API_KEY_2="sk-xxx-key2"
        
        backend = MultiKeyOpenAIBackend(
            api_keys=None,  # Auto-detect from env
            model_name="deepseek-ai/DeepSeek-V3.2-Exp"
        )
        
        # Method 2: Direct list
        backend = MultiKeyOpenAIBackend(
            api_keys=["sk-xxx-key1", "sk-xxx-key2"],
            model_name="deepseek-ai/DeepSeek-V3.2-Exp"
        )
    """
    
    # ============================================================================
    # 🛡️ 第四重保护机制：全局冷却状态（类级别变量，所有实例共享）
    # ============================================================================
    _global_cooldown_until = None  # 冷却结束时间
    _cooldown_lock = Lock()        # 线程安全锁
    _cooldown_duration = 600       # 冷却时长（秒），默认10分钟
    
    def __init__(
        self,
        api_keys: List[str] = None,
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        base_url: str = None,
        proxies: List = None
    ):
        """
        Initialize multi-key backend
        
        Args:
            api_keys: List of API keys. If None, auto-detect from environment:
                - OPENAI_API_KEY_1, OPENAI_API_KEY_2, ..., OPENAI_API_KEY_N
                - Or OPENAI_API_KEY (fallback to single key)
            model_name: Model to use
            temperature: Sampling temperature
            max_tokens: Max response tokens
            base_url: Custom API base URL (applies to all keys)
            proxies: List of proxy configurations for each API key.
                Format: ["http://user:pass@host:port", ...] or
                        [{"http": "...", "https": "..."}, ...]
                If None, no proxies are used.
                Must match the length of api_keys if provided.
        """
        # Auto-detect API keys from environment
        if api_keys is None:
            api_keys = self._auto_detect_keys()
        
        if not api_keys:
            raise ValueError(
                "No API keys provided. Please either:\n"
                "  1. Set environment variables:\n"
                "     - OPENAI_API_KEY_1='sk-xxx-key1'\n"
                "     - OPENAI_API_KEY_2='sk-xxx-key2'\n"
                "     - ... (add more as needed)\n"
                "  2. Pass api_keys=[key1, key2, ...] parameter"
            )
        
        self.api_keys = api_keys
        self.num_keys = len(api_keys)
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        
        # Proxy configuration
        self.proxies = proxies or [None] * self.num_keys
        if len(self.proxies) != self.num_keys:
            raise ValueError(
                f"Proxies list length ({len(self.proxies)}) must match "
                f"api_keys list length ({self.num_keys})"
            )
        
        # 🔧 [ENHANCED] 为每个API key创建易于识别的标签
        self.key_labels = []
        for i, key in enumerate(api_keys):
            label = f"Key#{i+1}[{key[:10]}...{key[-4:]}]"
            self.key_labels.append(label)
        
        # Initialize with first key
        super().__init__(
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_keys[0],
            base_url=self.base_url
        )
        
        # Create clients for all keys
        self.clients = []
        for i, key in enumerate(api_keys):
            proxy = self.proxies[i]
            proxy_info = ""
            if proxy:
                # 隐藏代理敏感信息用于日志显示
                if isinstance(proxy, dict):
                    proxy_str = proxy.get('http') or proxy.get('https') or str(proxy)
                else:
                    proxy_str = str(proxy)
                if '@' in proxy_str:
                    proxy_display = proxy_str.split('@')[0].split('//')[0] + '//' + '***@' + proxy_str.split('@')[1]
                else:
                    proxy_display = proxy_str
                proxy_info = f" with proxy {proxy_display}"
            
            print(f"[Multi-Key Backend] Initializing {self.key_labels[i]}{proxy_info}")
            client = self._create_client_for_key(key, proxy)
            self.clients.append(client)
        
        # 🔧 [ENHANCED] 密钥使用统计
        self.key_stats = [{'success': 0, 'failed': 0, 'last_error': None} for _ in api_keys]
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 🆕 智能密钥轮转机制 (每N次请求自动切换)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 设计原则:
        #   1. 开始时只使用第1个密钥 (current_key_index = 0)
        #   2. 跟踪当前密钥的请求次数 (current_key_request_count)
        #   3. 当请求次数达到阈值(rotation_interval)时,自动切换到下一个密钥
        #   4. 无可用密钥时循环回第1个 (循环使用)
        # 
        # 优势:
        #   - 主动规避TPM/RPM限制
        #   - 负载均衡更均匀
        #   - 避免等到报错了才切换
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        self._current_key_index = 0  # 当前活跃的密钥索引 (从第1个开始)
        self._current_key_request_count = 0  # 当前密钥已请求次数
        
        # 获取轮转间隔配置，默认为50次（如果环境变量未设置）
        # 如果只有一个密钥，则禁用轮转（interval设为非常大的数）
        if self.num_keys > 1:
            self._rotation_interval = int(os.getenv("LLM_KEY_ROTATION_INTERVAL", "50"))
            print(f"[Multi-Key Backend] 🆕 Automatic Key Rotation Enabled:")
            print(f"                     - Strategy: Rotate every {self._rotation_interval} requests")
        else:
            self._rotation_interval = float('inf')
            print(f"[Multi-Key Backend] ℹ️ Automatic Key Rotation Disabled (Single Key Mode)")
            
        self._consecutive_rate_limit_errors = [0] * self.num_keys  # 每个密钥的连续限流错误次数
        self._rate_limit_threshold = 1  # 立即切换阈值 (遇到限流立即切换)
        self._lock = Lock()  # 线程安全锁
        
        print(f"[Multi-Key Backend] ✓ Initialized {self.num_keys} API keys")
        print(f"                     - Starting with: {self.key_labels[0]}")
        print(f"                     - Error Switch threshold: Immediate switch on rate limit")
        print(f"                     - Auto fallback to Key#1 when all keys exhausted")
        print(f"[Multi-Key Backend] Expected throughput boost: {self.num_keys}x")
    
    def _auto_detect_keys(self) -> List[str]:
        """Auto-detect API keys from environment variables"""
        keys = []
        
        # Try numbered keys: OPENAI_API_KEY_1, OPENAI_API_KEY_2, ...
        i = 1
        while True:
            key = os.getenv(f"OPENAI_API_KEY_{i}")
            if not key:
                break
            keys.append(key)
            i += 1
        
        # Fallback to single key
        if not keys:
            single_key = os.getenv("OPENAI_API_KEY")
            if single_key:
                keys = [single_key]
                print("[Multi-Key Backend] Warning: Only one API key found. "
                      "Add OPENAI_API_KEY_2, OPENAI_API_KEY_3, etc. for load balancing.")
        
        return keys
    
    def _create_client_for_key(self, api_key: str, proxy=None):
        """
        Create OpenAI client for a specific API key with optional proxy
        
        Args:
            api_key: API key
            proxy: Proxy configuration (string or dict)
                - String: "http://user:pass@host:port"
                - Dict: {"http": "...", "https": "..."}
                - None: No proxy
        """
        try:
            from openai import OpenAI
            import httpx
        except ImportError:
            raise ImportError(
                "openai and httpx packages not installed. Run: pip install openai>=1.0.0 httpx"
            )
        
        # Create HTTP client with proxy if configured
        http_client = None
        if proxy:
            # Convert string proxy to dict format if needed
            if isinstance(proxy, str):
                proxy_dict = {
                    "http://": proxy,
                    "https://": proxy
                }
            else:
                proxy_dict = proxy
            
            # Create httpx.Client with proxy configuration
            http_client = httpx.Client(
                proxies=proxy_dict,
                timeout=120.0  # 120 second timeout
            )
        
        # Create OpenAI client
        if self.base_url:
            return OpenAI(
                api_key=api_key, 
                base_url=self.base_url,
                http_client=http_client
            )
        else:
            return OpenAI(
                api_key=api_key,
                http_client=http_client
            )
    
    def _check_and_rotate_key(self):
        """
        检查并执行基于请求次数的自动轮转
        """
        if self.num_keys <= 1:
            return

        with self._lock:
            # 再次检查以防race condition
            if self._current_key_request_count >= self._rotation_interval:
                old_index = self._current_key_index
                
                # 执行切换
                self._current_key_index = (old_index + 1) % self.num_keys
                self._current_key_request_count = 0
                
                print(f"\n🔄 [AUTO ROTATION] 已达到 {self._rotation_interval} 次请求，自动切换到 {self.key_labels[self._current_key_index]}")
            
            # 增加计数
            self._current_key_request_count += 1

    def _get_current_client(self):
        """
        获取当前活跃的密钥客户端 (智能轮转)
        
        每次获取客户端时，检查是否需要基于请求次数进行轮转
        
        Returns:
            tuple: (client, key_index)
        """
        # 1. 先检查是否需要基于次数轮转
        self._check_and_rotate_key()
        
        # 2. 获取当前客户端
        with self._lock:
            key_index = self._current_key_index
        return self.clients[key_index], key_index
    
    def _should_switch_key(self, error: Exception, current_key_index: int) -> bool:
        """
        判断是否应该切换密钥
        
        切换条件:
        - 错误是限流相关 (429, TPM, RPM, quota等)
        - 当前密钥已连续失败3次
        
        Args:
            error: 捕获的异常
            current_key_index: 当前密钥索引
            
        Returns:
            bool: 是否应该切换密钥
        """
        # 检查是否是限流错误
        if not self._is_rate_limit_error(error):
            return False
        
        # 增加连续错误计数
        with self._lock:
            self._consecutive_rate_limit_errors[current_key_index] += 1
            consecutive_errors = self._consecutive_rate_limit_errors[current_key_index]
        
        # 达到阈值时需要切换
        return consecutive_errors >= self._rate_limit_threshold
    
    def _is_rate_limit_error(self, error: Exception) -> bool:
        """
        判断错误是否是限流相关
        
        限流错误包括:
        - 429 Too Many Requests
        - TPM (Tokens Per Minute) 限制
        - RPM (Requests Per Minute) 限制
        - Quota/配额超限
        - Service overloaded
        
        Args:
            error: 捕获的异常
            
        Returns:
            bool: 是否是限流错误
        """
        error_msg = str(error).lower()
        
        rate_limit_patterns = [
            '429',
            'too many requests',
            'rate limit',
            'rate_limit',
            'ratelimit',
            'tpm',
            'rpm',
            'quota',
            'insufficient_quota',
            'overloaded',
            'service overloaded',
            '529',
        ]
        
        return any(pattern in error_msg for pattern in rate_limit_patterns)
    
    def _switch_to_next_key(self, failed_key_index: int, reason: str = ""):
        """
        切换到下一个可用密钥
        
        Args:
            failed_key_index: 触发切换的失败密钥索引
            reason: 切换原因 (用于日志)
        """
        with self._lock:
            # 🛡️ 防止多线程并发导致的重复轮转
            # 如果当前密钥已经不是那个失败的密钥，说明已经被其他线程轮转过了
            if self._current_key_index != failed_key_index:
                # print(f"[Key Rotation] Skipped: Already rotated from {self.key_labels[failed_key_index]} to {self.key_labels[self._current_key_index]}")
                return

            old_index = self._current_key_index
            
            # 切换到下一个密钥 (循环)
            self._current_key_index = (old_index + 1) % self.num_keys
            new_index = self._current_key_index
            
            # 重置旧密钥的连续错误计数 (允许后续恢复使用)
            old_consecutive_errors = self._consecutive_rate_limit_errors[old_index]
            self._consecutive_rate_limit_errors[old_index] = 0
            
            # 重置请求计数
            self._current_key_request_count = 0
        
        # 打印切换日志
        print("\n" + "="*80)
        print("🔄 [KEY ROTATION] 智能密钥轮转触发")
        print("="*80)
        print(f"原因: {reason}")
        print(f"旧密钥: {self.key_labels[old_index]} (连续失败{old_consecutive_errors}次)")
        print(f"新密钥: {self.key_labels[new_index]}")
        
        if new_index == 0 and old_index == self.num_keys - 1:
            print("⚠️  已轮转回第1个密钥 (所有密钥已尝试一轮)")
        
        print(f"\n📊 当前密钥状态:")
        for i in range(self.num_keys):
            consecutive = self._consecutive_rate_limit_errors[i]
            status = "🟢 活跃" if i == new_index else f"⚪ 待命 (连续错误: {consecutive}次)"
            print(f"  {self.key_labels[i]}: {status}")
        
        print("="*80 + "\n")
    
    def _reset_consecutive_errors_on_success(self, key_index: int):
        """
        成功调用后重置该密钥的连续错误计数
        
        这样可以确保只有"连续"失败才会触发切换,
        偶尔的失败不会导致切换。
        
        Args:
            key_index: 密钥索引
        """
        with self._lock:
            if self._consecutive_rate_limit_errors[key_index] > 0:
                self._consecutive_rate_limit_errors[key_index] = 0
    
    # ============================================================================
    # 🛡️ 第四重保护机制：全局冷却相关方法
    # ============================================================================
    
    @classmethod
    def _should_trigger_cooldown(cls, error: Exception) -> bool:
        """
        判断错误是否应该触发全局冷却
        
        触发条件（严重的API限制错误）：
        - 429 Too Many Requests (rate limit)
        - 529 Service overloaded
        - 多次连续的503/502错误
        
        Args:
            error: 捕获的异常
            
        Returns:
            bool: 是否应该触发冷却
        """
        error_msg = str(error).lower()
        error_type = type(error).__name__
        
        # 检查HTTP状态码相关错误
        critical_patterns = [
            '429',  # Rate limit
            'too many requests',
            'rate limit',
            'quota',
            'insufficient_quota',
            '529',  # Service overloaded
            'service overloaded',
            'overloaded',
        ]
        
        for pattern in critical_patterns:
            if pattern in error_msg:
                return True
        
        return False
    
    @classmethod
    def _trigger_global_cooldown(cls, reason: str = "Critical API error"):
        """
        触发全局冷却
        
        Args:
            reason: 触发原因（用于日志）
        """
        with cls._cooldown_lock:
            cls._global_cooldown_until = datetime.now() + timedelta(seconds=cls._cooldown_duration)
            
            print("\n" + "="*80)
            print("🛡️  [GLOBAL COOLDOWN ACTIVATED] 第四重保护机制已触发")
            print("="*80)
            print(f"原因: {reason}")
            print(f"冷却时长: {cls._cooldown_duration}秒 ({cls._cooldown_duration//60}分钟)")
            print(f"恢复时间: {cls._global_cooldown_until.strftime('%H:%M:%S')}")
            print()
            print("📊 保护机制说明:")
            print("  • 所有API调用将暂停，避免触发更严重的限制")
            print("  • 实验不会中止，会在冷却后自动恢复")
            print("  • 这可以保护你的API账户不被封禁")
            print()
            print("⏱️  倒计时开始...")
            print("="*80 + "\n")
    
    @classmethod
    def _wait_for_cooldown(cls):
        """
        等待全局冷却结束
        
        如果当前处于冷却期，阻塞当前线程直到冷却结束。
        显示实时倒计时。
        """
        with cls._cooldown_lock:
            cooldown_until = cls._global_cooldown_until
        
        if cooldown_until is None:
            return  # 没有冷却，直接返回
        
        now = datetime.now()
        if now >= cooldown_until:
            # 冷却已结束
            with cls._cooldown_lock:
                cls._global_cooldown_until = None
            return
        
        # 还在冷却中，需要等待
        remaining = (cooldown_until - now).total_seconds()
        
        print(f"\n⏸️  [WAITING] 全局冷却中，剩余 {int(remaining)}秒...")
        
        # 显示倒计时（每30秒更新一次）
        last_print = 0
        while True:
            now = datetime.now()
            if now >= cooldown_until:
                break
            
            remaining = (cooldown_until - now).total_seconds()
            
            # 每30秒或最后10秒时打印更新
            if int(remaining) % 30 == 0 or remaining <= 10:
                if int(remaining) != last_print:
                    minutes = int(remaining) // 60
                    seconds = int(remaining) % 60
                    if minutes > 0:
                        print(f"  ⏳ 剩余: {minutes}分{seconds}秒...")
                    else:
                        print(f"  ⏳ 剩余: {seconds}秒...")
                    last_print = int(remaining)
            
            time.sleep(1)
        
        # 冷却结束
        with cls._cooldown_lock:
            cls._global_cooldown_until = None
        
        print("\n" + "="*80)
        print("✅ [COOLDOWN COMPLETE] 冷却结束，实验继续")
        print("="*80 + "\n")
    
    @classmethod
    def get_cooldown_status(cls) -> dict:
        """
        获取当前冷却状态（用于监控）
        
        Returns:
            dict: 冷却状态信息
        """
        with cls._cooldown_lock:
            cooldown_until = cls._global_cooldown_until
        
        if cooldown_until is None:
            return {
                'active': False,
                'remaining_seconds': 0
            }
        
        now = datetime.now()
        if now >= cooldown_until:
            return {
                'active': False,
                'remaining_seconds': 0
            }
        
        remaining = (cooldown_until - now).total_seconds()
        return {
            'active': True,
            'remaining_seconds': int(remaining),
            'ends_at': cooldown_until.strftime('%H:%M:%S')
        }
    
    def _query_without_retry(
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
        直接调用API，不使用retry装饰器
        这样可以立即捕获错误，避免底层retry干扰密钥切换
        
        Returns:
            str: LLM response
        """
        # Use provided temperature/max_tokens or fall back to instance defaults
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        # Build messages based on input format
        if prompt is not None:
            # Simple interface
            messages = [{"role": "user", "content": prompt}]
        else:
            # Complex interface (for AgentReview)
            messages = []
            
            # Add system message with role description
            if role_desc:
                messages.append({"role": "system", "content": role_desc})
            
            # Add global prompt if provided
            if global_prompt:
                messages.append({"role": "system", "content": global_prompt})
            
            # Add history messages
            if history_messages:
                for msg in history_messages:
                    messages.append(msg)
            
            # Add current request
            if request_msg:
                messages.append({"role": "user", "content": request_msg})
        
        # 直接调用OpenAI API，不使用retry
        try:
            completion = self.client.chat.completions.create(
                timeout=120.0,  # 120 second timeout per request
                model=self.model,
                messages=messages,
                temperature=temp,
                max_tokens=tokens
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
            # 不打印错误日志，让上层处理
            raise
    
    def query(
        self,
        prompt: str = None,
        agent_name: str = None,
        role_desc: str = None,
        history_messages: List[Dict[str, str]] = None,
        global_prompt: str = None,
        request_msg: str = None,
        temperature: float = None,
        max_tokens: int = None,
        max_retries: int = 10
    ) -> str:
        """
        Query LLM with intelligent key rotation and retry mechanism
        
        🆕 智能密钥轮转策略 (取代旧的round-robin):
        - 开始时只使用第1个密钥
        - 当当前密钥遇到TPM/RPM限流时,立即切换到下一个密钥
        - 成功调用后重置连续错误计数,允许继续使用当前密钥
        - 无可用密钥时循环回第1个密钥
        
        🛡️ 四层保护机制:
        1. 单次请求重试 (DISABLED - 由本类完全控制)
        2. 指数退避 (exponential backoff)
        3. 智能密钥轮转 (本方法实现)
        4. 全局冷却 (global cooldown)
        
        Compatible with OpenAIBackend interface.
        
        Args:
            max_retries: Maximum number of retry attempts (default: 10)
            Other args: See OpenAIBackend.query()
        
        Returns:
            str: LLM response text
        
        Raises:
            Exception: After all retries exhausted
        """
        # 🛡️ 第四重保护：检查全局冷却状态（进入前先等待）
        self._wait_for_cooldown()
        
        last_exception = None
        cooldown_attempts = 0  # 追踪冷却后的重试次数
        MAX_COOLDOWN_CYCLES = 3  # 最多触发3次冷却
        
        while cooldown_attempts < MAX_COOLDOWN_CYCLES:
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 执行一轮完整的重试（前三层保护机制）
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            for attempt in range(max_retries):
                try:
                    # 🆕 使用智能密钥轮转 (总是使用当前活跃的密钥)
                    client, key_idx = self._get_current_client()
                    
                    # Log retry attempt
                    if attempt > 0 or cooldown_attempts > 0:
                        cycle_info = f" [Cooldown cycle {cooldown_attempts + 1}]" if cooldown_attempts > 0 else ""
                        print(f"[LLM Retry] Attempt {attempt + 1}/{max_retries} using {self.key_labels[key_idx]}{cycle_info}")
                    
                    # Temporarily swap client for this call
                    original_client = self.client
                    self.client = client
                    
                    try:
                        # 🔧 [CRITICAL FIX] 直接调用_query_without_retry避免底层retry干扰
                        # 这样可以立即捕获429错误并进行密钥切换
                        result = self._query_without_retry(
                            prompt=prompt,
                            agent_name=agent_name,
                            role_desc=role_desc,
                            history_messages=history_messages,
                            global_prompt=global_prompt,
                            request_msg=request_msg,
                            temperature=temperature,
                            max_tokens=max_tokens
                        )
                        
                        # 🔧 [ENHANCED] 记录成功统计
                        self.key_stats[key_idx]['success'] += 1
                        
                        # 🆕 成功后重置该密钥的连续错误计数
                        self._reset_consecutive_errors_on_success(key_idx)
                        
                        # Success! Log if this was a retry
                        if attempt > 0 or cooldown_attempts > 0:
                            print(f"[LLM Retry] ✓ Success on attempt {attempt + 1} using {self.key_labels[key_idx]}")
                        
                        return result
                        
                    finally:
                        # Restore original client
                        self.client = original_client
                        
                except Exception as e:
                    last_exception = e
                    error_type = type(e).__name__
                    error_msg = str(e)
                    
                    # 🔧 [ENHANCED] 记录密钥错误统计
                    self.key_stats[key_idx]['failed'] += 1
                    self.key_stats[key_idx]['last_error'] = f"{error_type}: {error_msg[:100]}"
                    
                    # 🆕 智能密钥轮转：检查是否应该切换密钥
                    should_switch = self._should_switch_key(e, key_idx)
                    
                    # 🔧 [ENHANCED] 详细的错误日志（包含完整的API密钥标识）
                    print(f"\n{'='*80}")
                    print(f"[LLM API ERROR] Attempt {attempt + 1}/{max_retries} failed")
                    print(f"{'='*80}")
                    print(f"🔑 API Key: {self.key_labels[key_idx]}")
                    print(f"🏷️  Model: {self.model}")
                    print(f"🌐 Base URL: {self.base_url or 'Official OpenAI'}")
                    print(f"❌ Error Type: {error_type}")
                    print(f"📝 Error Message: {error_msg}")
                    
                    # 🆕 [DEBUG] 显示所有密钥的状态
                    print(f"\n📊 密钥状态 (共{self.num_keys}个):")
                    for i in range(self.num_keys):
                        status = "🟢 当前" if i == key_idx else "⚪ 待命"
                        errors = self._consecutive_rate_limit_errors[i]
                        print(f"   {self.key_labels[i]}: {status} (连续错误: {errors}/{self._rate_limit_threshold})")
                    
                    # 🆕 显示是否是限流错误
                    if self._is_rate_limit_error(e):
                        consecutive_errors = self._consecutive_rate_limit_errors[key_idx]
                        print(f"\n⚠️  限流错误检测: 是 (连续{consecutive_errors}次)")
                        if should_switch:
                            print(f"🔄 触发密钥轮转: 连续限流错误已达{self._rate_limit_threshold}次阈值")
                    else:
                        print(f"\n❌ 非限流错误，不计入连续错误计数")
                    
                    # 🔧 [ENHANCED] 特殊错误类型的详细诊断
                    if "401" in str(e) or "Unauthorized" in str(e):
                        print(f"\n🚨 认证失败 (401 Unauthorized)")
                        print(f"   问题密钥: {self.key_labels[key_idx]}")
                        print(f"   完整密钥: {self.api_keys[key_idx][:15]}...{self.api_keys[key_idx][-8:]}")
                        print(f"   可能原因:")
                        print(f"     1. API密钥无效或已过期")
                        print(f"     2. 密钥格式错误（多余空格/换行符）")
                        print(f"     3. 密钥与base_url不匹配")
                        print(f"   解决方案:")
                        print(f"     - 检查 llm_config.py 中该密钥的配置")
                        print(f"     - 登录API提供商确认密钥有效性")
                        print(f"     - 尝试重新生成密钥")
                    
                    elif "403" in str(e) or "Forbidden" in str(e):
                        print(f"\n🚨 访问被拒绝 (403 Forbidden)")
                        print(f"   问题密钥: {self.key_labels[key_idx]}")
                        print(f"   可能原因:")
                        print(f"     1. 账户余额不足")
                        print(f"     2. 密钥权限不足（只读密钥）")
                        print(f"     3. IP地址被限制")
                        print(f"     4. 模型访问权限未开通")
                    
                    elif "429" in str(e) or "rate limit" in error_msg.lower():
                        print(f"\n⚠️  速率限制 (429 Too Many Requests)")
                        print(f"   问题密钥: {self.key_labels[key_idx]}")
                        print(f"   可能原因:")
                        print(f"     1. TPM (Tokens Per Minute) 超限")
                        print(f"     2. RPM (Requests Per Minute) 超限")
                        print(f"     3. 日配额用尽")
                        print(f"   当前策略: 将触发指数退避和多密钥轮询")
                    
                    elif "404" in str(e):
                        print(f"\n🚨 资源不存在 (404 Not Found)")
                        print(f"   问题密钥: {self.key_labels[key_idx]}")
                        print(f"   可能原因:")
                        print(f"     1. Base URL错误: {self.base_url}")
                        print(f"     2. 模型名称错误: {self.model}")
                        print(f"     3. API端点路径错误")
                    
                    elif "timeout" in error_msg.lower():
                        print(f"\n⏱️  请求超时 (Timeout)")
                        print(f"   问题密钥: {self.key_labels[key_idx]}")
                        print(f"   可能原因:")
                        print(f"     1. 网络连接不稳定")
                        print(f"     2. API服务器响应慢")
                        print(f"     3. 请求过于复杂（token过多）")
                    
                    # Log full traceback for first and last attempts
                    if attempt == 0 or attempt == max_retries - 1:
                        print(f"\n📋 完整堆栈跟踪:")
                        for line in traceback.format_exc().split('\n'):
                            if line.strip():
                                print(f"   {line}")
                    
                    print(f"{'='*80}\n")
                    
                    # 🆕 智能密钥轮转：如果应该切换密钥,立即切换
                    if should_switch:
                        self._switch_to_next_key(
                            failed_key_index=key_idx,
                            reason=f"连续{self._rate_limit_threshold}次限流错误: {error_type}"
                        )
                        # 切换密钥后立即重试,不等待
                        continue
                    
                    # 🛡️ 第二层：指数退避
                    # Don't retry immediately - exponential backoff
                    if attempt < max_retries - 1:
                        wait_time = min(2 ** attempt, 10)  # Max 10 seconds
                        print(f"            Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                    else:
                        # All retries exhausted - log final failure
                        print(f"\n{'='*80}")
                        print(f"[LLM ERROR] ✗ All {max_retries} attempts failed!")
                        print(f"{'='*80}")
                        print(f"Final error: {error_type}: {error_msg}")
                        print(f"\n📊 API密钥使用统计:")
                        for i, stats in enumerate(self.key_stats):
                            total = stats['success'] + stats['failed']
                            success_rate = (stats['success'] / total * 100) if total > 0 else 0
                            print(f"  {self.key_labels[i]}:")
                            print(f"    成功: {stats['success']}, 失败: {stats['failed']}, 成功率: {success_rate:.1f}%")
                            if stats['last_error']:
                                print(f"    最后错误: {stats['last_error']}")
                        print(f"{'='*80}\n")
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 🛡️ 第四重保护：前三层全部失败后的判断
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            
            # 所有10次重试都失败了，检查是否应该触发冷却
            if last_exception and self._should_trigger_cooldown(last_exception):
                cooldown_attempts += 1
                
                print(f"\n{'='*80}")
                print(f"⚠️  前三层保护机制已用尽（10次重试 + 75秒等待）")
                print(f"   最后的错误类型: {type(last_exception).__name__}")
                print(f"   错误信息: {str(last_exception)[:100]}")
                
                if cooldown_attempts < MAX_COOLDOWN_CYCLES:
                    print(f"   → 启动第四层保护：全局冷却 ({cooldown_attempts}/{MAX_COOLDOWN_CYCLES})")
                    print(f"{'='*80}\n")
                    
                    # 触发全局冷却
                    self._trigger_global_cooldown(
                        reason=f"{type(last_exception).__name__}: {str(last_exception)[:100]}"
                    )
                    
                    # 等待冷却结束
                    self._wait_for_cooldown()
                    
                    print(f"\n{'='*80}")
                    print(f"🔄 冷却完成，开始新一轮重试（将再次执行10次重试）")
                    print(f"{'='*80}\n")
                    
                    # 继续外层while循环，开始新一轮重试
                    continue
                else:
                    print(f"   ⚠️  已达到最大冷却次数 ({MAX_COOLDOWN_CYCLES}次)")
                    print(f"   → 放弃重试，抛出异常")
                    print(f"{'='*80}\n")
                    break
            else:
                # 不是rate limit类型的错误，或者没有错误
                # 直接退出，不触发冷却
                break
        
        # 所有尝试（包括冷却后的重试）都失败了
        if last_exception is not None:
            raise last_exception
        else:
            raise RuntimeError("All retry attempts failed but no exception was captured")
    
    def get_stats(self) -> Dict:
        """Get usage statistics"""
        with self._lock:
            current_key = self._current_key_index
            consecutive_errors = self._consecutive_rate_limit_errors.copy()
        
        return {
            "num_keys": self.num_keys,
            "keys_preview": [key[:10] + "..." for key in self.api_keys],
            "key_labels": self.key_labels,
            "expected_throughput_boost": f"{self.num_keys}x",
            "key_stats": self.key_stats,
            "current_active_key": current_key,
            "current_active_key_label": self.key_labels[current_key],
            "consecutive_errors_per_key": consecutive_errors,
            "rotation_threshold": self._rate_limit_threshold,
        }
    
    def print_key_stats(self):
        """
        打印详细的API密钥使用统计
        用于实验结束后的总结
        """
        print(f"\n{'='*80}")
        print(f"📊 API密钥使用统计总结")
        print(f"{'='*80}")
        
        # 获取当前状态
        stats_info = self.get_stats()
        current_key = stats_info["current_active_key"]
        
        total_success = 0
        total_failed = 0
        
        for i, stats in enumerate(self.key_stats):
            total = stats['success'] + stats['failed']
            total_success += stats['success']
            total_failed += stats['failed']
            success_rate = (stats['success'] / total * 100) if total > 0 else 0
            
            # 标记当前活跃密钥
            active_marker = " 🟢 [当前活跃]" if i == current_key else ""
            consecutive = stats_info["consecutive_errors_per_key"][i]
            
            print(f"\n{self.key_labels[i]}{active_marker}:")
            print(f"  ✅ 成功调用: {stats['success']} 次")
            print(f"  ❌ 失败调用: {stats['failed']} 次")
            print(f"  📈 成功率: {success_rate:.2f}%")
            print(f"  📊 总调用: {total} 次")
            print(f"  🔄 连续限流错误: {consecutive} 次 (阈值: {self._rate_limit_threshold})")
            
            if stats['last_error']:
                print(f"  🔴 最后错误: {stats['last_error']}")
        
        # 总体统计
        overall_total = total_success + total_failed
        overall_success_rate = (total_success / overall_total * 100) if overall_total > 0 else 0
        
        print(f"\n{'─'*80}")
        print(f"总体统计:")
        print(f"  总成功: {total_success} 次")
        print(f"  总失败: {total_failed} 次")
        print(f"  总成功率: {overall_success_rate:.2f}%")
        print(f"  总调用: {overall_total} 次")
        print(f"\n密钥轮转策略:")
        print(f"  模式: 智能轮转 (基于限流错误)")
        print(f"  切换阈值: 连续{self._rate_limit_threshold}次限流错误")
        print(f"  当前活跃密钥: {self.key_labels[current_key]}")
        print(f"{'='*80}\n")


def create_multi_key_backend(
    model_name: str = "deepseek-ai/DeepSeek-V3.2-Exp",
    temperature: float = 0.6,
    max_tokens: int = 700
) -> MultiKeyOpenAIBackend:
    """
    Convenient factory function to create multi-key backend
    
    Usage:
        # Set environment variables first:
        # export OPENAI_API_KEY_1="sk-xxx-account1"
        # export OPENAI_API_KEY_2="sk-xxx-account2"
        
        backend = create_multi_key_backend()
    """
    return MultiKeyOpenAIBackend(
        api_keys=None,  # Auto-detect
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens
    )


if __name__ == "__main__":
    print("Multi-Key Backend Configuration Test")
    print("=" * 80)
    
    # Test auto-detection
    try:
        backend = create_multi_key_backend()
        stats = backend.get_stats()
        
        print("\n✓ Configuration successful!")
        print(f"  - Number of keys: {stats['num_keys']}")
        print(f"  - Keys preview: {stats['keys_preview']}")
        print(f"  - Expected boost: {stats['expected_throughput_boost']}")
        
    except ValueError as e:
        print(f"\n✗ Configuration failed:")
        print(f"  {e}")
        print("\nPlease set environment variables:")
        print("  export OPENAI_API_KEY_1='your-first-key'")
        print("  export OPENAI_API_KEY_2='your-second-key'")

