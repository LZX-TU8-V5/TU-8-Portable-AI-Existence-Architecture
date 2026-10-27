# -*- coding: utf-8 -*-
"""
tu8_toolchain.py — TU-8 本地化工具链 v1.0
日期: 2026-05-23
功能: 为规划器提供本地工具执行能力，将抽象任务映射为具体操作

层级: L4 协作层（本地化工具链集成）
依赖: tu8_planner.py（规划器）、tool adapters（read/write/exec/browser）

核心设计:
  Task(任务) → ToolChain.dispatch(task) → ToolAdapter.execute() → Result
  工具映射: task.tags → 选择合适工具
  结果回写: 执行结果写入 task.result，状态推进

工具清单:
  - file_read:    读取文件（调用 read 工具）
  - file_write:   写入文件（调用 write 工具）
  - file_edit:    编辑文件（调用 edit 工具）
  - shell_exec:   执行Shell命令（调用 exec 工具）
  - browser_ctrl: 浏览器操作（调用 browser 工具）
  - memory_search: 记忆检索（调用 memory_search 工具）
  - web_fetch:    URL内容获取（调用 web_fetch 工具）
"""
# 创作者: 李奥(金木蟾) | TU-8 v5

import os
import sys
import json
import time
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum


# =============================================================================
# 错误分类
# =============================================================================

class ErrorSeverity(Enum):
    """错误严重程度"""
    TRANSIENT = "transient"    # 瞬时错误，重试可能解决（网络超时、文件锁）
    RECOVERABLE = "recoverable"  # 可恢复错误，需降级或调整参数（路径不存在、权限不足）
    FATAL = "fatal"            # 致命错误，重试无意义（参数类型错误、工具不存在）


class ErrorHandler:
    """错误处理引擎：分类 + 退避 + 降级"""

    # 错误关键词 → 严重程度
    _SEVERITY_PATTERNS: Dict[str, ErrorSeverity] = {
        # 瞬时（可重试）
        "timeout": ErrorSeverity.TRANSIENT,
        "timed out": ErrorSeverity.TRANSIENT,
        "connection": ErrorSeverity.TRANSIENT,
        "temporarily": ErrorSeverity.TRANSIENT,
        "rate limit": ErrorSeverity.TRANSIENT,
        "busy": ErrorSeverity.TRANSIENT,
        "locked": ErrorSeverity.TRANSIENT,
        "EAGAIN": ErrorSeverity.TRANSIENT,
        "EWOULDBLOCK": ErrorSeverity.TRANSIENT,
        # 可恢复（需降级）
        "not found": ErrorSeverity.RECOVERABLE,
        "No such file": ErrorSeverity.RECOVERABLE,
        "permission": ErrorSeverity.RECOVERABLE,
        "ENOENT": ErrorSeverity.RECOVERABLE,
        "EACCES": ErrorSeverity.RECOVERABLE,
        "invalid param": ErrorSeverity.RECOVERABLE,
        # 致命（不重试）
        "not implemented": ErrorSeverity.FATAL,
        "unsupported": ErrorSeverity.FATAL,
        "type error": ErrorSeverity.FATAL,
        "null reference": ErrorSeverity.FATAL,
    }

    # 最大重试次数（按严重程度）
    _MAX_RETRIES: Dict[ErrorSeverity, int] = {
        ErrorSeverity.TRANSIENT: 3,
        ErrorSeverity.RECOVERABLE: 1,
        ErrorSeverity.FATAL: 0,
    }

    # 退避策略（毫秒）— 指数退避 + 抖动
    _BASE_DELAY_MS = 1000
    _MAX_DELAY_MS = 30000
    _JITTER_FACTOR = 0.3

    # 任务级总超时（毫秒）— 单次退避上限30s，但整个任务链路总耗时硬上限
    _TASK_TIMEOUT_MS = 60000

    @classmethod
    def remaining_ms(cls, started_at: float) -> int:
        """计算距离任务总超时还剩多少毫秒，<=0 表示已超时"""
        elapsed_ms = (time.time() - started_at) * 1000
        return max(0, int(cls._TASK_TIMEOUT_MS - elapsed_ms))

    @classmethod
    def is_task_timed_out(cls, started_at: float) -> bool:
        """判断任务是否已超过总超时"""
        return cls.remaining_ms(started_at) <= 0

    @classmethod
    def classify(cls, error: str) -> ErrorSeverity:
        """根据错误信息分类严重程度

        白名单匹配：只有显式命中 _SEVERITY_PATTERNS 的才允许重试。
        未识别错误默认 FATAL，宁可误杀不可放过——避免新型 bug 被当作可恢复错误
        白跑一轮还掩盖真实异常。
        """
        error_lower = error.lower()
        for pattern, severity in cls._SEVERITY_PATTERNS.items():
            if pattern.lower() in error_lower:
                return severity
        return ErrorSeverity.FATAL  # 默认致命，需人工介入

    @classmethod
    def should_retry(cls, severity: ErrorSeverity, attempt: int) -> bool:
        """判断是否应该重试"""
        max_retries = cls._MAX_RETRIES[severity]
        return attempt < max_retries

    @classmethod
    def backoff_ms(cls, attempt: int) -> int:
        """计算退避时间（指数退避 + 随机抖动）"""
        import random
        delay = cls._BASE_DELAY_MS * (2 ** attempt)
        delay = min(delay, cls._MAX_DELAY_MS)
        jitter = delay * cls._JITTER_FACTOR * (random.random() * 2 - 1)
        return max(100, int(delay + jitter))

    @classmethod
    def get_fallback_adapter(cls, current_adapter: str) -> Optional[str]:
        """获取降级适配器名称"""
        return cls._FALLBACK_MAP.get(current_adapter)

    @classmethod
    def get_semantic_check(cls, adapter_name: str) -> 'Optional[Callable]':
        """获取降级语义校验函数

        每条降级路径必须附带校验。降级执行后调用校验函数：
        - 校验通过 → 降级成功，结果可用
        - 校验失败 → 视同 FATAL，不再继续往下跌
        没有校验的降级就是静默数据损坏。
        """
        return cls._FALLBACK_CHECKS.get(adapter_name)

    # 降级映射表：adapter_name → 降级目标
    _FALLBACK_MAP: Dict[str, str] = {
        "browser_ctrl": "web_fetch",   # JS渲染失败 → 简单HTTP抓取
        "web_fetch": "shell_exec",     # 抓取失败 → curl兜底
        "file_write": "shell_exec",    # 写入失败 → tee/echo兜底
    }

    # 语义校验表：降级目标 → 校验函数
    # 校验失败 = 该降级路径 FATAL，不继续往下跌
    _FALLBACK_CHECKS: Dict[str, 'Callable'] = {}

    @classmethod
    def register_semantic_check(cls, adapter_name: str, check_fn: 'Callable'):
        """注册语义校验函数

        check_fn 签名: (ToolResult) -> bool
        返回 True 表示降级结果可用，False 表示校验失败（视同FATAL）
        """
        cls._FALLBACK_CHECKS[adapter_name] = check_fn

    @classmethod
    def register_default_semantic_checks(cls):
        """注册默认语义校验函数（在 Toolchain 初始化时调用）"""

        # web_fetch 降级校验：browser_ctrl → web_fetch
        # 校验逻辑：output 非空，且长度 > 100（排除空壳页面）
        def check_web_fetch(result: 'ToolResult') -> bool:
            if not result.success:
                return False
            output = result.output or ""
            # 至少要有实质性内容
            if len(output) < 100:
                return False
            # 排除明显的错误页面标识
            error_markers = ["404", "not found", "error", "forbidden", "access denied"]
            output_lower = output.lower()
            if any(marker in output_lower for marker in error_markers):
                # 但如果内容够长，可能是正文包含这些词，放行
                if len(output) < 500:
                    return False
            return True

        # shell_exec 降级校验（web_fetch → shell_exec / file_write → shell_exec）
        # 校验逻辑：exit code 成功且 output 非空
        def check_shell_exec(result: 'ToolResult') -> bool:
            if not result.success:
                return False
            output = result.output or ""
            # curl 成功至少要有内容返回
            if len(output) < 50:
                return False
            return True

        cls.register_semantic_check("web_fetch", check_web_fetch)
        cls.register_semantic_check("shell_exec", check_shell_exec)
        # 注意：file_write 降级到 shell_exec 时，校验用同一个 check_shell_exec

    @classmethod
    def build_retry_summary(cls, task_id: str, error: str, attempt: int, severity: ErrorSeverity) -> str:
        """生成人类可读的重试摘要"""
        if severity == ErrorSeverity.FATAL:
            return f"[FATAL] {task_id}: {error} — 不重试"
        return f"[{severity.value.upper()}] {task_id}: {error} — 第{attempt+1}次重试，退避{cls.backoff_ms(attempt)}ms"

# =============================================================================
# 日志
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("TU8.Toolchain")

# =============================================================================
# 数据类
# =============================================================================

@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    output: str = ""
    error: str = ""
    metadata: Dict = field(default_factory=dict)
    duration_ms: int = 0
    # 错误处理增强字段
    severity: str = ""       # 错误严重程度（transient/recoverable/fatal）
    attempt: int = 0          # 当前尝试次数
    retried: bool = False     # 是否经历过重试
    fallback_used: str = ""  # 降级使用的适配器名

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "output": self.output[:500],
            "error": self.error,
            "metadata": self.metadata,
            "duration_ms": self.duration_ms,
            "severity": self.severity,
            "attempt": self.attempt,
            "retried": self.retried,
            "fallback_used": self.fallback_used,
        }


@dataclass
class TaskContext:
    """任务执行上下文"""
    task_id: str
    description: str
    tags: List[str]
    params: Dict = field(default_factory=dict)
    working_dir: str = ""
    env: Dict = field(default_factory=dict)


# =============================================================================
# 工具适配器基类
# =============================================================================

class ToolAdapter:
    """工具适配器基类"""

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"TU8.Toolchain.{name}")

    def execute(self, context: TaskContext) -> ToolResult:
        """执行工具（子类实现）"""
        raise NotImplementedError

    def validate(self, context: TaskContext) -> Optional[str]:
        """验证参数（返回错误信息，None表示通过）"""
        return None


# =============================================================================
# 具体工具适配器
# =============================================================================

class FileReadAdapter(ToolAdapter):
    """文件读取适配器（调用 OpenClaw read 工具）"""

    def __init__(self):
        super().__init__("file_read")

    def validate(self, context: TaskContext) -> Optional[str]:
        if "path" not in context.params:
            return "缺少 path 参数"
        return None

    def execute(self, context: TaskContext) -> ToolResult:
        start = time.time()
        error = self.validate(context)
        if error:
            return ToolResult(success=False, error=error)

        path = context.params["path"]
        offset = context.params.get("offset", 1)
        limit = context.params.get("limit", 50)

        # 注意：此处仅生成工具调用参数，实际执行由上层调度
        # 返回结构化调用信息，由 TU8Agent 或 Planner 发起实际工具调用
        result = ToolResult(success=True)
        result.metadata = {
            "tool": "read",
            "params": {
                "path": path,
                "offset": offset,
                "limit": limit,
            }
        }
        result.duration_ms = int((time.time() - start) * 1000)
        self.logger.info(f"文件读取任务已准备: {path}")
        return result


class FileWriteAdapter(ToolAdapter):
    """文件写入适配器（调用 OpenClaw write 工具）"""

    def __init__(self):
        super().__init__("file_write")

    def validate(self, context: TaskContext) -> Optional[str]:
        if "path" not in context.params:
            return "缺少 path 参数"
        if "content" not in context.params:
            return "缺少 content 参数"
        return None

    def execute(self, context: TaskContext) -> ToolResult:
        start = time.time()
        error = self.validate(context)
        if error:
            return ToolResult(success=False, error=error)

        result = ToolResult(success=True)
        result.metadata = {
            "tool": "write",
            "params": {
                "path": context.params["path"],
                "content": context.params["content"],
            }
        }
        result.duration_ms = int((time.time() - start) * 1000)
        self.logger.info(f"文件写入任务已准备: {context.params['path']}")
        return result


class ShellExecAdapter(ToolAdapter):
    """Shell命令执行适配器（调用 OpenClaw exec 工具）"""

    def __init__(self):
        super().__init__("shell_exec")

    def validate(self, context: TaskContext) -> Optional[str]:
        if "command" not in context.params:
            return "缺少 command 参数"
        return None

    def execute(self, context: TaskContext) -> ToolResult:
        start = time.time()
        error = self.validate(context)
        if error:
            return ToolResult(success=False, error=error)

        result = ToolResult(success=True)
        result.metadata = {
            "tool": "exec",
            "params": {
                "command": context.params["command"],
                "workdir": context.params.get("workdir", context.working_dir),
                "timeout": context.params.get("timeout", 60),
            }
        }
        result.duration_ms = int((time.time() - start) * 1000)
        self.logger.info(f"Shell命令已准备: {context.params['command'][:50]}...")
        return result


class BrowserAdapter(ToolAdapter):
    """浏览器操作适配器（调用 OpenClaw browser 工具）"""

    def __init__(self):
        super().__init__("browser_ctrl")

    def validate(self, context: TaskContext) -> Optional[str]:
        if "action" not in context.params:
            return "缺少 action 参数"
        return None

    def execute(self, context: TaskContext) -> ToolResult:
        start = time.time()
        error = self.validate(context)
        if error:
            return ToolResult(success=False, error=error)

        result = ToolResult(success=True)
        result.metadata = {
            "tool": "browser",
            "params": {
                "action": context.params["action"],
                **{k: v for k, v in context.params.items() if k != "action"}
            }
        }
        result.duration_ms = int((time.time() - start) * 1000)
        self.logger.info(f"浏览器操作已准备: {context.params['action']}")
        return result


class MemorySearchAdapter(ToolAdapter):
    """记忆检索适配器（调用 OpenClaw memory_search 工具）"""

    def __init__(self):
        super().__init__("memory_search")

    def validate(self, context: TaskContext) -> Optional[str]:
        if "query" not in context.params:
            return "缺少 query 参数"
        return None

    def execute(self, context: TaskContext) -> ToolResult:
        start = time.time()
        error = self.validate(context)
        if error:
            return ToolResult(success=False, error=error)

        result = ToolResult(success=True)
        result.metadata = {
            "tool": "memory_search",
            "params": {
                "query": context.params["query"],
                "maxResults": context.params.get("maxResults", 5),
                "corpus": context.params.get("corpus", "memory"),
            }
        }
        result.duration_ms = int((time.time() - start) * 1000)
        self.logger.info(f"记忆检索已准备: {context.params['query']}")
        return result


class WebFetchAdapter(ToolAdapter):
    """URL内容获取适配器（调用 OpenClaw web_fetch 工具）"""

    def __init__(self):
        super().__init__("web_fetch")

    def validate(self, context: TaskContext) -> Optional[str]:
        if "url" not in context.params:
            return "缺少 url 参数"
        return None

    def execute(self, context: TaskContext) -> ToolResult:
        start = time.time()
        error = self.validate(context)
        if error:
            return ToolResult(success=False, error=error)

        result = ToolResult(success=True)
        result.metadata = {
            "tool": "web_fetch",
            "params": {
                "url": context.params["url"],
                "extractMode": context.params.get("extractMode", "markdown"),
                "maxChars": context.params.get("maxChars", 10000),
            }
        }
        result.duration_ms = int((time.time() - start) * 1000)
        self.logger.info(f"URL获取已准备: {context.params['url']}")
        return result


# =============================================================================
# 工具链调度器
# =============================================================================

class TU8Toolchain:
    """
    TU-8 本地化工具链调度器

    功能:
      - 注册工具适配器
      - 根据任务标签分发到对应适配器
      - 执行工具并返回结果
      - 记录执行日志
    """

    def __init__(self, workspace: str = ""):
        self.workspace = Path(workspace) if workspace else Path.cwd()
        self.adapters: Dict[str, ToolAdapter] = {}
        self.execution_log: List[Dict] = []
        self.logger = logging.getLogger("TU8.Toolchain")
        self._register_default_adapters()
        # 注册默认语义校验函数
        ErrorHandler.register_default_semantic_checks()

    def _register_default_adapters(self):
        """注册默认适配器"""
        defaults = [
            FileReadAdapter(),
            FileWriteAdapter(),
            ShellExecAdapter(),
            BrowserAdapter(),
            MemorySearchAdapter(),
            WebFetchAdapter(),
        ]
        for adapter in defaults:
            self.register_adapter(adapter)

    def register_adapter(self, adapter: ToolAdapter):
        """注册工具适配器"""
        self.adapters[adapter.name] = adapter
        self.logger.info(f"已注册适配器: {adapter.name}")

    def dispatch(self, context: TaskContext, attempt: int = 0,
                   task_started_at: Optional[float] = None) -> ToolResult:
        """
        根据任务标签分发到对应适配器

        支持自动重试（指数退避）、降级（fallback适配器）、
        语义校验（降级后验证结果等价性）、任务级总超时。

        Args:
            context: 任务执行上下文
            attempt: 当前尝试次数（用于重试递归）
            task_started_at: 任务首次分发时间戳（用于总超时计算）
        """
        if task_started_at is None:
            task_started_at = time.time()

        # ---- 任务级总超时检查 ----
        if ErrorHandler.is_task_timed_out(task_started_at):
            remaining = ErrorHandler.remaining_ms(task_started_at)
            self.logger.error(
                f"任务总超时: {context.task_id} 已超过{ErrorHandler._TASK_TIMEOUT_MS}ms"
            )
            return ToolResult(
                success=False,
                error=f"任务总超时({ErrorHandler._TASK_TIMEOUT_MS}ms)",
                severity="fatal",
                attempt=attempt,
            )

        adapter = self._select_adapter(context.tags)
        if not adapter:
            return ToolResult(
                success=False,
                error=f"无匹配适配器，可用: {list(self.adapters.keys())}",
                severity="fatal",
                attempt=attempt,
            )

        self.logger.info(f"分发任务 {context.task_id} → {adapter.name} (attempt={attempt})")

        try:
            result = adapter.execute(context)
            result.attempt = attempt

            if result.success:
                self._log_execution(context, adapter.name, result)
                return result

            # ---- 失败处理：分类 → 重试/降级 ----
            severity = ErrorHandler.classify(result.error)
            result.severity = severity.value

            self.logger.warning(
                ErrorHandler.build_retry_summary(context.task_id, result.error, attempt, severity)
            )

            # 1. 尝试重试（检查总超时余量）
            if ErrorHandler.should_retry(severity, attempt):
                remaining = ErrorHandler.remaining_ms(task_started_at)
                delay_ms = min(ErrorHandler.backoff_ms(attempt), remaining - 1000)
                if delay_ms <= 0:
                    self.logger.warning(f"重试被总超时拦截: 剩余{remaining}ms不足")
                    result.severity = "fatal"
                    self._log_execution(context, adapter.name, result)
                    return result
                self.logger.info(f"等待 {delay_ms}ms 后重试...")
                time.sleep(delay_ms / 1000)
                retry_result = self.dispatch(context, attempt + 1, task_started_at)
                retry_result.retried = True
                return retry_result

            # 2. 重试耗尽 → 尝试降级（带语义校验）
            fallback_name = ErrorHandler.get_fallback_adapter(adapter.name)
            if fallback_name and fallback_name in self.adapters:
                # 再次检查总超时
                if ErrorHandler.is_task_timed_out(task_started_at):
                    self.logger.warning(f"降级被总超时拦截: {context.task_id}")
                    result.severity = "fatal"
                    self._log_execution(context, adapter.name, result)
                    return result

                self.logger.info(f"降级: {adapter.name} → {fallback_name}")
                fallback_adapter = self.adapters[fallback_name]
                fallback_context = TaskContext(
                    task_id=context.task_id,
                    description=f"[降级-{fallback_name}] {context.description}",
                    tags=[fallback_name],
                    params=context.params,
                    working_dir=context.working_dir,
                    env=context.env,
                )
                fallback_result = fallback_adapter.execute(fallback_context)
                fallback_result.fallback_used = fallback_name
                fallback_result.attempt = attempt
                fallback_result.severity = severity.value

                # ---- 语义校验：降级结果是否可用 ----
                check_fn = ErrorHandler.get_semantic_check(fallback_name)
                if check_fn is not None:
                    if not check_fn(fallback_result):
                        self.logger.error(
                            f"语义校验失败: {fallback_name} 降级结果不可用，视同FATAL"
                        )
                        fallback_result.success = False
                        fallback_result.error = (
                            f"降级语义校验失败: {fallback_name} 结果未通过校验"
                        )
                        fallback_result.severity = "fatal"
                        self._log_execution(fallback_context, fallback_name, fallback_result)
                        return fallback_result
                    else:
                        self.logger.info(f"语义校验通过: {fallback_name}")

                self._log_execution(fallback_context, fallback_name, fallback_result)
                return fallback_result

            # 3. 无降级 → 返回失败
            self._log_execution(context, adapter.name, result)
            return result

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            severity = ErrorHandler.classify(error_msg)
            self.logger.error(f"适配器异常: {adapter.name} - {error_msg}")

            result = ToolResult(
                success=False,
                error=error_msg,
                severity=severity.value,
                attempt=attempt,
            )

            # 异常也尝试重试（受总超时约束）
            if ErrorHandler.should_retry(severity, attempt):
                remaining = ErrorHandler.remaining_ms(task_started_at)
                if remaining > 2000:
                    delay_ms = min(ErrorHandler.backoff_ms(attempt), remaining - 1000)
                    time.sleep(max(0, delay_ms) / 1000)
                    return self.dispatch(context, attempt + 1, task_started_at)

            self._log_execution(context, adapter.name, result)
            return result

    def _select_adapter(self, tags: List[str]) -> Optional[ToolAdapter]:
        """根据标签选择合适的适配器"""
        tag_map = {
            "file_read": ["file_read", "read", "读取", "读取文件"],
            "file_write": ["file_write", "write", "写入", "写入文件"],
            "shell_exec": ["shell", "exec", "执行", "运行命令"],
            "browser_ctrl": ["browser", "浏览器", "网页"],
            "memory_search": ["memory", "search", "检索", "记忆"],
            "web_fetch": ["web", "fetch", "url", "网页内容"],
        }

        for tag in tags:
            tag_lower = tag.lower()
            for adapter_name, keywords in tag_map.items():
                if any(kw in tag_lower for kw in keywords):
                    return self.adapters.get(adapter_name)

        # 默认：根据任务描述猜测
        return self._guess_adapter(tags)

    def _guess_adapter(self, tags: List[str]) -> Optional[ToolAdapter]:
        """猜测适配器（兜底）"""
        if not tags:
            return None
        desc = " ".join(tags).lower()
        if "读" in desc or "read" in desc:
            return self.adapters.get("file_read")
        if "写" in desc or "write" in desc:
            return self.adapters.get("file_write")
        if "执行" in desc or "exec" in desc or "运行" in desc:
            return self.adapters.get("shell_exec")
        if "浏览器" in desc or "browser" in desc:
            return self.adapters.get("browser_ctrl")
        if "检索" in desc or "search" in desc:
            return self.adapters.get("memory_search")
        if "http" in desc or "www" in desc or "url" in desc:
            return self.adapters.get("web_fetch")
        return None

    def _log_execution(self, context: TaskContext, adapter_name: str, result: ToolResult):
        """记录执行日志（含重试/降级信息）"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "task_id": context.task_id,
            "adapter": adapter_name,
            "success": result.success,
            "duration_ms": result.duration_ms,
            "error": result.error,
            "severity": result.severity,
            "attempt": result.attempt,
            "retried": result.retried,
            "fallback_used": result.fallback_used,
        }
        self.execution_log.append(log_entry)

        # 限制日志大小
        if len(self.execution_log) > 1000:
            self.execution_log = self.execution_log[-500:]

    def get_error_stats(self) -> Dict[str, Any]:
        """获取错误统计（用于复盘）"""
        if not self.execution_log:
            return {"total": 0}

        total = len(self.execution_log)
        failures = [e for e in self.execution_log if not e["success"]]
        retried = [e for e in self.execution_log if e.get("retried")]
        fallbacks = [e for e in self.execution_log if e.get("fallback_used")]

        by_severity = {}
        for e in failures:
            sev = e.get("severity", "unknown")
            by_severity[sev] = by_severity.get(sev, 0) + 1

        return {
            "total_executions": total,
            "success_rate": f"{(total - len(failures)) / total * 100:.1f}%" if total else "N/A",
            "failures": len(failures),
            "retried_count": len(retried),
            "fallback_count": len(fallbacks),
            "by_severity": by_severity,
        }

    def get_execution_log(self, limit: int = 20) -> List[Dict]:
        """获取执行日志"""
        return self.execution_log[-limit:]

    def clear_log(self):
        """清空执行日志"""
        self.execution_log.clear()
        self.logger.info("执行日志已清空")


# =============================================================================
# 与 Planner 集成
# =============================================================================

def create_task_context(task: Any, plan: Any, workspace: str = "") -> TaskContext:
    """
    从 Plan/Task 创建 TaskContext

    将 tu8_planner.py 的 Task 对象转换为 Toolchain 可处理的 TaskContext
    """
    # 解析任务描述，提取参数
    params = _parse_task_params(task.description, task.tags)

    return TaskContext(
        task_id=task.id,
        description=task.description,
        tags=task.tags,
        params=params,
        working_dir=str(workspace) if workspace else os.getcwd(),
    )


def _parse_task_params(description: str, tags: List[str]) -> Dict:
    """
    从任务描述和标签中提取参数

    简单启发式解析，实际应由 LLM 辅助提取
    """
    params = {}

    # 提取路径（简单启发）
    if "文件" in description or "file" in " ".join(tags).lower():
        # 尝试从描述中提取路径
        words = description.split()
        for i, word in enumerate(words):
            if word.endswith((".py", ".md", ".json", ".txt")):
                params["path"] = word.strip(".,;:")
                break

    # 提取命令（简单启发）
    if "执行" in description or "运行" in description:
        # 取描述中"执行"或"运行"后的部分
        for keyword in ["执行", "运行", "execute", "run"]:
            if keyword in description:
                idx = description.index(keyword) + len(keyword)
                cmd = description[idx:].strip(" :：")
                if cmd:
                    params["command"] = cmd
                break

    # 提取URL
    if "http" in description:
        import re
        urls = re.findall(r'https?://[^\s]+', description)
        if urls:
            params["url"] = urls[0]

    return params


# =============================================================================
# 命令行测试
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TU-8 本地化工具链测试")
    parser.add_argument("--test", action="store_true", help="运行内置测试")
    args = parser.parse_args()

    if args.test:
        print("=" * 60)
        print("TU-8 Toolchain 测试")
        print("=" * 60)

        toolchain = TU8Toolchain()

        # 测试1：文件读取任务
        print("\n[测试1] 文件读取任务")
        ctx1 = TaskContext(
            task_id="test_001",
            description="读取 SOUL.md 文件",
            tags=["file_read", "读取"],
            params={"path": "C:/Users/qq366410837/.qclaw/workspace/SOUL.md"}
        )
        result1 = toolchain.dispatch(ctx1)
        print(f"  适配器: {result1.metadata.get('tool')}")
        print(f"  参数: {result1.metadata.get('params')}")

        # 测试2：Shell执行任务
        print("\n[测试2] Shell执行任务")
        ctx2 = TaskContext(
            task_id="test_002",
            description="执行 Python 版本检查",
            tags=["shell", "exec"],
            params={"command": "python --version"}
        )
        result2 = toolchain.dispatch(ctx2)
        print(f"  适配器: {result2.metadata.get('tool')}")
        print(f"  参数: {result2.metadata.get('params')}")

        # 测试3：记忆检索任务
        print("\n[测试3] 记忆检索任务")
        ctx3 = TaskContext(
            task_id="test_003",
            description="检索 TU-8 规划器相关信息",
            tags=["memory", "search"],
            params={"query": "TU-8 规划器"}
        )
        result3 = toolchain.dispatch(ctx3)
        print(f"  适配器: {result3.metadata.get('tool')}")
        print(f"  参数: {result3.metadata.get('params')}")

        # 测试4：参数提取
        print("\n[测试4] 参数提取（从描述）")
        from tu8_planner import Task, TaskStatus
        fake_task = Task(
            id="t1",
            description="读取 D:/test.py 文件内容",
            tags=["file_read"]
        )
        params = _parse_task_params(fake_task.description, fake_task.tags)
        print(f"  提取参数: {params}")

        # 日志
        print("\n[执行日志]")
        log = toolchain.get_execution_log()
        for entry in log:
            print(f"  {entry['timestamp']} | {entry['task_id']} | {entry['adapter']} | {'[OK]' if entry['success'] else '[X]'}")

        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)
    else:
        parser.print_help()


# =============================================================================
# Planner→Toolchain 桥接
# =============================================================================

class PlannerToolchainBridge:
    """
    Planner 与 Toolchain 的桥接器
    
    将 tu8_planner.Task 转换为 toolchain.TaskContext 并执行。
    作为 execute_plan() 的 agent_callback 使用。
    """
    
    def __init__(self, workspace: str = ""):
        self.toolchain = TU8Toolchain(workspace)
        self.logger = logging.getLogger("TU8.Bridge")
        # 存储每个 Task 对应的实际工具调用参数（供 Agent 真正执行）
        self.pending_tool_calls: Dict[str, Dict] = {}
    
    def __call__(self, task) -> str:
        """
        作为 agent_callback 被调用
        
        Args:
            task: tu8_planner.Task 对象
            
        Returns:
            执行结果摘要（字符串）
        """
        # 1. 将 Task 转换为 TaskContext
        context = self._task_to_context(task)
        
        # 2. 调用 Toolchain.dispatch
        result = self.toolchain.dispatch(context)
        
        # 3. 存储 pending tool call（如果有）
        if result.success and result.metadata.get("tool"):
            self.pending_tool_calls[task.id] = result.metadata
        
        # 4. 返回结果摘要
        if result.success:
            tool_name = result.metadata.get("tool", "unknown")
            return f"[Toolchain] 准备调用 {tool_name}: {result.metadata.get('params', {})}"
        else:
            return f"[Toolchain] 失败: {result.error}"
    
    def _task_to_context(self, task) -> TaskContext:
        """将 Planner.Task 转换为 Toolchain.TaskContext"""
        params = _parse_task_params(task.description, task.tags)
        
        # 如果 params 没有提取到，尝试从 task.result 恢复（假设之前执行过）
        if not params and hasattr(task, "params"):
            params = task.params
        
        return TaskContext(
            task_id=task.id,
            description=task.description,
            tags=task.tags,
            params=params,
            working_dir=str(self.toolchain.workspace),
        )
    
    def get_pending_tool_calls(self) -> Dict[str, Dict]:
        """获取所有待执行的工具调用"""
        return self.pending_tool_calls.copy()
    
    def clear_pending_tool_calls(self):
        """清空待执行的工具调用"""
        self.pending_tool_calls.clear()
    
    def get_toolchain_stats(self) -> Dict:
        """获取工具链执行统计"""
        return self.toolchain.get_error_stats()


def create_planner_toolchain_bridge(workspace: str = "") -> PlannerToolchainBridge:
    """创建 Planner-Toolchain 桥接器"""
    return PlannerToolchainBridge(workspace)
