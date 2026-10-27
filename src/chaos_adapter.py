# -*- coding: utf-8 -*-
"""
chaos_adapter.py — TU-8 混沌注入代理适配器
日期: 2026-05-23
功能: 在适配器层注入受控故障，验证错误处理/降级/超时逻辑是否扛得住

用法:
    from chaos_adapter import ChaosProxy, ChaosConfig
    # 用混沌代理包装任意适配器
    wrapped = ChaosProxy(real_adapter, ChaosConfig())
    chain.register_adapter(wrapped)

注入概率（可调）:
  - RATE_LIMIT:     30% → 模拟 429 Too Many Requests
  - TRUNCATED_JSON: 20% → 返回截断的 JSON（解析必崩）
  - HANG:           10% → 挂起指定时长不响应（测超时）
  - 正常通过:       40% → 转发给真实适配器
"""
# 创作者: 李奥(金木蟾) | TU-8 v5

import time
import random
import logging
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field

from tu8_toolchain import ToolAdapter, TaskContext, ToolResult


logger = logging.getLogger("TU8.Chaos")


# =============================================================================
# 混沌配置
# =============================================================================

@dataclass
class ChaosConfig:
    """混沌注入配置 — 每项概率独立，总和不必为 1（按优先级依次判定）"""

    # 模拟 429 Rate Limit
    rate_limit_prob: float = 0.30
    rate_limit_error_msg: str = "429 Too Many Requests — rate limit exceeded"

    # 模拟截断 JSON（下游解析必崩）
    truncated_json_prob: float = 0.20
    truncated_json_output: str = '{"data": {"items": [{"id": 1, "name": "test", "va'

    # 模拟挂起（测超时）
    hang_prob: float = 0.10
    hang_seconds: float = 60.0  # 默认挂 60s（超过任务级 60s 总超时）

    # 随机种子（可复现）
    seed: Optional[int] = None

    def __post_init__(self):
        if self.seed is not None:
            random.seed(self.seed)


# =============================================================================
# 混沌代理适配器
# =============================================================================

class ChaosProxy(ToolAdapter):
    """
    代理适配器：包装真实适配器，按概率注入故障
    
    判定顺序（短路）:
      1. 挂起检查（如果命中，线程会阻塞，后面的不再判定）
      2. 429 检查
      3. 截断 JSON 检查
      4. 全部未命中 → 转发真实适配器
    """

    def __init__(self, real_adapter: ToolAdapter, config: ChaosConfig = None):
        super().__init__(f"chaos://{real_adapter.name}")
        self.real_adapter = real_adapter
        self.config = config or ChaosConfig()
        self.inject_log: List[Dict] = []  # 注入记录（供测试断言）

    def execute(self, context: TaskContext) -> ToolResult:
        return self._chaos_dispatch(context)

    def validate(self, context: TaskContext) -> Optional[str]:
        return self.real_adapter.validate(context)

    def _chaos_dispatch(self, context: TaskContext) -> ToolResult:
        """混沌分发：按概率注入故障或转发"""

        rng = random.random()
        injection = None

        # ---- 1. 挂起（优先判定，命中后阻塞）----
        if rng < self.config.hang_prob:
            injection = "hang"
            hang_s = self.config.hang_seconds
            logger.warning(f"[CHAOS:HANG] {context.task_id} 挂起 {hang_s}s")
            self._log_injection(context, "hang", f"blocked_{hang_s}s")
            # 用 event.wait 代替 time.sleep，允许外部中断
            stop_event = threading.Event()
            stop_event.wait(timeout=hang_s)
            # 挂起结束后返回超时错误
            return ToolResult(
                success=False,
                error=f"Chaos: hung for {hang_s}s (simulated timeout)",
                duration_ms=int(hang_s * 1000),
            )

        # ---- 2. 429 Rate Limit ----
        if rng < self.config.hang_prob + self.config.rate_limit_prob:
            injection = "rate_limit"
            logger.warning(f"[CHAOS:429] {context.task_id} → 429")
            self._log_injection(context, "rate_limit", self.config.rate_limit_error_msg)
            return ToolResult(
                success=False,
                error=self.config.rate_limit_error_msg,
                duration_ms=1,
            )

        # ---- 3. 截断 JSON ----
        if rng < self.config.hang_prob + self.config.rate_limit_prob + self.config.truncated_json_prob:
            injection = "truncated_json"
            output = self.config.truncated_json_output
            logger.warning(f"[CHAOS:TRUNC] {context.task_id} → 截断JSON ({len(output)}B)")
            self._log_injection(context, "truncated_json", f"len={len(output)}")
            # 返回"成功"但内容是残废的——这就是静默数据损坏的根源
            return ToolResult(
                success=True,  # 注意：假装成功！
                output=output,
                duration_ms=1,
            )

        # ---- 4. 全部未命中 → 转发真实适配器 ----
        logger.debug(f"[CHAOS:PASS] {context.task_id} → 转发 {self.real_adapter.name}")
        return self.real_adapter.execute(context)

    def _log_injection(self, context: TaskContext, kind: str, detail: str):
        """记录注入事件"""
        self.inject_log.append({
            "task_id": context.task_id,
            "kind": kind,
            "detail": detail,
        })

    def get_inject_stats(self) -> Dict[str, int]:
        """获取注入统计"""
        stats: Dict[str, int] = {}
        for entry in self.inject_log:
            k = entry["kind"]
            stats[k] = stats.get(k, 0) + 1
        stats["total"] = len(self.inject_log)
        return stats

    def reset(self):
        """重置注入日志"""
        self.inject_log.clear()
