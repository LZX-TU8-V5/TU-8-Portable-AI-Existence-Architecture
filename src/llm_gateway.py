"""
llm_gateway.py — 大模型网关 v1.0

核心使命：
  将大模型从"决策者"降级为"推理引擎"，
  调度链只与标准化接口对话，不依赖任何具体模型。

四维解耦：
  1. 接口契约层 —— 统一的 Request/Response Schema
  2. 逻辑与算力 —— 调度链负责纯数学，网关负责神经网
  3. 工具与执行 —— 输出标准化 Intent，不绑定业务逻辑
  4. 记忆与上下文 —— 调度链主动推送 Context，模型阅后即焚

架构：
  consciousness_cycle.tick()
       │
       ▼
  llm_gateway.execute(LLMRequest)
       │
       ├── provider_registry["openai"] → OpenAI API
       ├── provider_registry["qwen"]   → Qwen API
       ├── provider_registry["hy3"]    → Hy3 API
       └── provider_registry["local"]  → 本地小模型兜底

防崩溃设计：
  - 断网时自动降级到 local fallback（返回保守默认值）
  - 所有 provider 执行有 timeout 保护
  - provider 失败自动重试（可配置次数）
  - 调度链永不因网关异常而抛异常

# 创作者: 李奥(金木蟾) | TU-8 v5
"""

import json
import time
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Callable, Type
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# 标准化角色定义
# =============================================================================

class LLMRole(str, Enum):
    """调度链可以向大模型请求的角色类型"""
    NODE_EVALUATOR = "node_evaluator"
    """评估一个 UCT 搜索节点的价值（返回 Value 分数）"""
    ACTION_GENERATOR = "action_generator"
    """在当前状态下生成可行的候选动作"""
    CONTEXT_SUMMARIZER = "context_summarizer"
    """压缩/总结历史上下文"""
    INTENT_PARSER = "intent_parser"
    """将用户原始输入解析为标准化 Intent"""
    PATTERN_RECOGNIZER = "pattern_recognizer"
    """识别历史轨迹中的失败/成功模式"""
    DECISION_ADVISOR = "decision_advisor"
    """在危机期提供非常规解法建议"""


# =============================================================================
# 标准化请求/响应 Schema
# =============================================================================

@dataclass
class LLMRequest:
    """
    调度链发给 LLM Gateway 的标准化请求。
    
    调度链负责组装 prompt 和 context，
    网关负责翻译给具体的模型。
    """
    role: LLMRole
    """请求的角色类型"""
    prompt: str
    """调度链组装的标准化提示"""
    context: Dict[str, Any] = field(default_factory=dict)
    """当前状态、UCT 树的部分展开、任务进度等"""
    max_tokens: int = 1024
    """输出最大 token 数"""
    temperature: float = 0.3
    """生成温度（评估任务用低温，生成任务用中温）"""
    response_schema: Optional[str] = None
    """期望的输出格式（如 'value_score', 'action_list', 'free_text'）"""
    metadata: Dict[str, Any] = field(default_factory=dict)
    """附加元数据（如当前 cycle 编号、调用的调度链环节等）"""

    def to_dict(self) -> dict:
        return {
            "role": self.role.value,
            "prompt": self.prompt[:500],  # 日志截断
            "context_keys": list(self.context.keys()),
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "response_schema": self.response_schema,
        }


@dataclass
class LLMResponse:
    """
    大模型返回给调度链的标准化响应。
    """
    success: bool
    """请求是否成功"""
    content: Any = None
    """解析后的结构化结果（dict 或 list，根据 response_schema 而定）"""
    raw: str = ""
    """原始文本（debug 用）"""
    model: str = ""
    """实际被调用的模型名"""
    provider: str = ""
    """实际被调用的 provider 名"""
    token_usage: int = 0
    """消耗的 token 数"""
    latency_ms: float = 0.0
    """请求耗时（毫秒）"""
    fallback_used: bool = False
    """是否使用了降级/兜底"""
    error: str = ""
    """错误信息（success=False 时填充）"""

    @staticmethod
    def default(role: LLMRole) -> "LLMResponse":
        """默认保守响应（网关降级时使用）"""
        if role == LLMRole.NODE_EVALUATOR:
            return LLMResponse(
                success=True,
                content={"value": 0.5, "confidence": 0.1},
                model="fallback_default",
                provider="fallback",
                fallback_used=True,
            )
        elif role == LLMRole.ACTION_GENERATOR:
            return LLMResponse(
                success=True,
                content={"actions": [], "reason": "fallback_no_actions"},
                model="fallback_default",
                provider="fallback",
                fallback_used=True,
            )
        else:
            return LLMResponse(
                success=True,
                content={},
                model="fallback_default",
                provider="fallback",
                fallback_used=True,
            )


# =============================================================================
# Response Schema 解析器
# =============================================================================

def parse_response_schema(text: str, schema: str) -> Any:
    """
    将模型原始输出解析为结构化内容。
    
    支持的 schema:
      - 'value_score': 提取一个 float 分数
      - 'action_list': 提取动作列表
      - 'free_text': 原样返回
      - 其他: 尝试 JSON 解析，失败则原样返回
    """
    if schema == "free_text":
        return text

    # 尝试提取 JSON
    json_content = text.strip()
    # 处理 markdown 代码块包裹
    if "```json" in text:
        json_content = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        json_content = text.split("```")[1].split("```")[0].strip()

    try:
        parsed = json.loads(json_content)
        return parsed
    except (json.JSONDecodeError, IndexError):
        logger.debug("(json.JSONDecodeError, IndexError) suppressed", exc_info=True)
        pass

    # schema 特定的容错提取
    if schema == "value_score":
        import re
        match = re.search(r"[-+]?\d*\.?\d+", text)
        if match:
            return {"value": float(match.group()), "confidence": 0.5}

    return text


# =============================================================================
# Provider 抽象基类
# =============================================================================

class LLMProvider(ABC):
    """大模型 Provider 抽象基类"""

    def __init__(self, name: str, timeout: float = 30.0):
        self.name = name
        self.timeout = timeout

    @abstractmethod
    def execute(self, request: LLMRequest) -> LLMResponse:
        """
        执行一次 LLM 调用。
        
        必须在 timeout 内返回，不得抛异常。
        异常应捕获并返回 LLMResponse(success=False, error=...)
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查 provider 是否可用（网络、认证等）"""
        pass

    def to_dict(self) -> dict:
        return {"name": self.name, "timeout": self.timeout}


# =============================================================================
# 具体 Provider 实现
# =============================================================================

class OpenAIProvider(LLMProvider):
    """OpenAI / 兼容 API Provider"""

    def __init__(self,
                 api_key: str,
                 model: str = "gpt-4o",
                 base_url: str = "https://api.openai.com/v1",
                 timeout: float = 30.0):
        super().__init__(name=f"openai/{model}", timeout=timeout)
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._session = None

    def _get_session(self):
        """延迟创建 HTTP session"""
        if self._session is None:
            import requests
            self._session = requests.Session()
            self._session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            })
        return self._session

    def execute(self, request: LLMRequest) -> LLMResponse:
        start = time.time()
        try:
            session = self._get_session()
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self._build_system_prompt(request.role)},
                    {"role": "user", "content": self._build_user_prompt(request)},
                ],
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
            }
            resp = session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            content = parse_response_schema(raw, request.response_schema or "free_text")
            return LLMResponse(
                success=True,
                content=content,
                raw=raw,
                model=self.model,
                provider=self.name,
                token_usage=usage.get("total_tokens", 0),
                latency_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            logger.warning(f"[OpenAIProvider] execute failed: {e}")
            return LLMResponse(
                success=False,
                error=str(e),
                model=self.model,
                provider=self.name,
                latency_ms=(time.time() - start) * 1000,
            )

    def is_available(self) -> bool:
        try:
            session = self._get_session()
            resp = session.get(f"{self.base_url}/models", timeout=5)
            return resp.status_code < 500
        except Exception:
            return False

    def _build_system_prompt(self, role: LLMRole) -> str:
        prompts = {
            LLMRole.NODE_EVALUATOR: (
                "你是一个 UCT 搜索树的节点评估器。\n"
                "给定当前状态和候选动作，评估该节点的价值分数。\n"
                "输出格式：JSON，包含 'value' (0.0-1.0) 和 'confidence' (0.0-1.0)。"
            ),
            LLMRole.ACTION_GENERATOR: (
                "你是一个动作生成器。\n"
                "给定当前上下文，生成可行的候选动作列表。\n"
                "输出格式：JSON，包含 'actions' 数组和 'reason' 说明。"
            ),
            LLMRole.CONTEXT_SUMMARIZER: (
                "你是一个上下文压缩器。\n"
                "将给定的对话历史压缩为结构化摘要，保留关键信息。\n"
                "输出格式：JSON，包含 'summary', 'key_points', 'unresolved'。"
            ),
        }
        return prompts.get(role, "请根据用户指令输出 JSON 格式的结果。")

    def _build_user_prompt(self, request: LLMRequest) -> str:
        parts = [request.prompt]
        if request.context:
            parts.append(f"\n上下文：\n```json\n{json.dumps(request.context, ensure_ascii=False, indent=2)}\n```")
        if request.response_schema:
            parts.append(f"\n请严格按 JSON 格式输出（schema: {request.response_schema}）。")
        return "\n".join(parts)


class LocalFallbackProvider(LLMProvider):
    """
    本地兜底 Provider。
    
    断网或所有远程 provider 不可用时使用。
    不调用任何真实模型，返回保守的默认值。
    """

    def __init__(self, timeout: float = 0.1):
        super().__init__(name="local_fallback", timeout=timeout)

    def execute(self, request: LLMRequest) -> LLMResponse:
        logger.info(f"[LocalFallback] 降级处理: role={request.role.value}")
        default = LLMResponse.default(request.role)
        default.provider = self.name
        return default

    def is_available(self) -> bool:
        return True  # 本地永不降级


class QwenProvider(LLMProvider):
    """
    Qwen API Provider（占位实现）
    
    实际使用时需替换为真实的 HTTP 调用。
    接口格式与 OpenAI 兼容时可直接复用 OpenAIProvider。
    """

    def __init__(self,
                 api_key: str,
                 model: str = "qwen3-max",
                 base_url: str = "https://dashscope.aliyuncs.com/api/v1",
                 timeout: float = 30.0):
        super().__init__(name=f"qwen/{model}", timeout=timeout)
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def execute(self, request: LLMRequest) -> LLMResponse:
        # Qwen API 通常兼容 OpenAI 格式
        openai_compat = OpenAIProvider(
            api_key=self.api_key,
            model=self.model,
            base_url=self.base_url,
            timeout=self.timeout,
        )
        return openai_compat.execute(request)

    def is_available(self) -> bool:
        return True  # 简化：实际应做 HTTP 健康检查


class Hy3Provider(LLMProvider):
    """
    Hy3 API Provider（占位实现）

    Hy3 通常是自行部署的 endpoint。
    """

    def __init__(self,
                 endpoint: str,
                 token: str = "",
                 model: str = "hy3-default",
                 timeout: float = 30.0):
        super().__init__(name=f"hy3/{model}", timeout=timeout)
        self.endpoint = endpoint.rstrip("/")
        self.token = token
        self.model = model

    def execute(self, request: LLMRequest) -> LLMResponse:
        logger.info(f"[Hy3Provider] 请求发送到 {self.endpoint}")
        # 占位：返回默认值
        default = LLMResponse.default(request.role)
        default.provider = self.name
        default.model = self.model
        return default

    def is_available(self) -> bool:
        return True  # 占位


# =============================================================================
# LLM Gateway — 核心网关
# =============================================================================

class LLMGateway:
    """
    大模型网关主类。
    
    调度链的唯一对话窗口。
    负责：
      - Provider 注册与查找
      - 自动降级与故障转移
      - 统一日志与监控
      - 限流保护

    用法：
      gateway = LLMGateway()
      gateway.register("openai", OpenAIProvider(api_key="..."))
      gateway.register("local", LocalFallbackProvider())
      gateway.set_default("openai")
      gateway.set_fallback("local")
      
      resp = gateway.execute(LLMRequest(
          role=LLMRole.NODE_EVALUATOR,
          prompt="评估当前状态价值",
          context={"state": "...", "candidates": [...]},
          response_schema="value_score",
      ))
    """

    def __init__(self):
        self._providers: Dict[str, LLMProvider] = {}
        self._default_provider: Optional[str] = None
        self._fallback_provider: Optional[str] = None
        self._max_retries: int = 2
        self._lock = threading.RLock()

        # 监控统计
        self._stats: Dict[str, Any] = {
            "total_calls": 0,
            "success_calls": 0,
            "fallback_calls": 0,
            "failed_calls": 0,
            "total_tokens": 0,
            "total_latency_ms": 0.0,
            "provider_stats": {},
        }

    # --- 配置接口 ---

    def register(self, name: str, provider: LLMProvider) -> None:
        """注册一个 provider"""
        with self._lock:
            self._providers[name] = provider
            self._stats["provider_stats"][name] = {
                "calls": 0, "success": 0, "failed": 0, "fallback": 0,
            }
            logger.info(f"[LLMGateway] 注册 provider: {name} ({type(provider).__name__})")

    def set_default(self, name: str) -> None:
        """设置默认 provider"""
        with self._lock:
            if name not in self._providers:
                raise KeyError(f"Provider '{name}' 未注册")
            self._default_provider = name
            logger.info(f"[LLMGateway] 默认 provider 设为: {name}")

    def set_fallback(self, name: str) -> None:
        """设置降级 provider（所有远程 provider 不可用时的兜底）"""
        with self._lock:
            if name not in self._providers:
                raise KeyError(f"Provider '{name}' 未注册")
            self._fallback_provider = name
            logger.info(f"[LLMGateway] 降级 provider 设为: {name}")

    def set_max_retries(self, count: int) -> None:
        self._max_retries = max(0, count)

    # --- 执行接口 ---

    def execute(self, request: LLMRequest) -> LLMResponse:
        """
        执行一次大模型调用。
        
        执行顺序：
          1. 尝试默认 provider（含重试）
          2. 失败后遍历其他远程 provider
          3. 全部失败后使用 fallback provider
        
        永不抛异常——总是返回 LLMResponse。
        """
        with self._lock:
            self._stats["total_calls"] += 1

        # 1. 尝试默认 provider
        response = self._try_provider(self._default_provider, request)

        # 2. 默认失败 → 尝试其他远程 provider
        if not response or not response.success:
            for name, provider in self._providers.items():
                if name == self._default_provider or name == self._fallback_provider:
                    continue
                if not provider.is_available():
                    continue
                response = self._try_provider(name, request)
                if response and response.success:
                    break

        # 3. 全部失败 → fallback（永不抛异常的最后防线）
        if not response or not response.success:
            response = self._use_fallback(request)

        # 更新统计
        with self._lock:
            self._update_stats(response)

        return response

    def _try_provider(self, name: Optional[str], request: LLMRequest) -> Optional[LLMResponse]:
        """尝试一个 provider（含重试）"""
        if not name or name not in self._providers:
            return None

        provider = self._providers[name]
        if not provider.is_available():
            logger.warning(f"[LLMGateway] provider '{name}' 不可用，跳过")
            return None

        for attempt in range(1 + self._max_retries):
            try:
                response = provider.execute(request)
                return response
            except Exception as e:
                logger.warning(
                    f"[LLMGateway] provider '{name}' 第 {attempt+1} 次失败: {e}"
                )
                if attempt < self._max_retries:
                    time.sleep(0.5 * (attempt + 1))  # 退避

        return None

    def _use_fallback(self, request: LLMRequest) -> LLMResponse:
        """使用 fallback provider 兜底"""
        name = self._fallback_provider
        if name and name in self._providers:
            response = self._providers[name].execute(request)
            response.fallback_used = True
            with self._lock:
                self._stats["fallback_calls"] += 1
            return response
        # 连 fallback 都没有 → 返回硬编码默认值
        with self._lock:
            self._stats["fallback_calls"] += 1
        return LLMResponse.default(request.role)

    # --- 监控与统计 ---

    def _update_stats(self, response: LLMResponse) -> None:
        if response.success:
            self._stats["success_calls"] += 1
        else:
            self._stats["failed_calls"] += 1
        self._stats["total_tokens"] += response.token_usage
        self._stats["total_latency_ms"] += response.latency_ms

        pstats = self._stats["provider_stats"].get(response.provider)
        if pstats:
            pstats["calls"] += 1
            if response.success:
                pstats["success"] += 1
            else:
                pstats["failed"] += 1
            if response.fallback_used:
                pstats["fallback"] += 1

    def stats(self) -> dict:
        with self._lock:
            s = dict(self._stats)
            s["default_provider"] = self._default_provider
            s["fallback_provider"] = self._fallback_provider
            s["avg_latency_ms"] = round(
                s["total_latency_ms"] / max(s["total_calls"], 1), 1
            )
            return s

    # --- 健康检查 ---

    def health(self) -> dict:
        """全局健康状态"""
        status = {}
        with self._lock:
            for name, provider in self._providers.items():
                try:
                    available = provider.is_available()
                except Exception:
                    available = False
                is_default = name == self._default_provider
                is_fallback = name == self._fallback_provider
                status[name] = {
                    "available": available,
                    "is_default": is_default,
                    "is_fallback": is_fallback,
                    "type": type(provider).__name__,
                }
        return {
            "healthy": any(
                s["available"] and not s["is_fallback"] for s in status.values()
            ),
            "providers": status,
        }


# =============================================================================
# 便捷工厂函数
# =============================================================================

def create_llm_gateway(
    openai_api_key: str = "",
    openai_model: str = "gpt-4o",
    openai_base_url: str = "https://api.openai.com/v1",
    default_provider: str = "openai",
) -> LLMGateway:
    """
    创建标准配置的 LLM Gateway。
    
    默认注册三个 provider：
      - openai: 主 provider
      - local: 兜底 provider
    
    用法：
      gateway = create_llm_gateway(openai_api_key="sk-...")
      resp = gateway.execute(LLMRequest(
          role=LLMRole.NODE_EVALUATOR,
          prompt="评估这个状态",
          context={"state": "..."},
          response_schema="value_score",
      ))
    """
    gateway = LLMGateway()

    if openai_api_key:
        gateway.register(
            "openai",
            OpenAIProvider(
                api_key=openai_api_key,
                model=openai_model,
                base_url=openai_base_url,
            ),
        )
        gateway.set_default("openai")

    gateway.register("local", LocalFallbackProvider())
    gateway.set_fallback("local")

    return gateway
