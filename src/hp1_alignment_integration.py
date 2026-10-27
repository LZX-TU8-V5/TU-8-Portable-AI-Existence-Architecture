"""
HP1 集成：alignment_verify 钩子注入点

注入点：alignment_verify() — TU-8 出件前最后一道校验门

BEFORE 钩子签名：
  fn(ctx: dict) -> (proceed: bool, modified_ctx: dict)
  - 返回 (False, _) = 短路，拒绝输出
  - ctx 携带字段：
      content: str           要输出的内容
      confidence: float      当前置信度
      steel_mark: bool       是否有钢印冲突
      safety_level: str      L0/L1/L2
      output_channel: str    当前输出通道

AFTER 钩子签名：
  fn(ctx: dict, result: bool) -> bool
  - result: alignment 是否通过
  - 返回值覆盖 result

ON_TENSION 钩子签名：
  fn(ctx: dict) -> dict
  - 紧张/冲突上升时触发
  - 返回降压建议写入 ctx

ON_CONFIDENCE 钩子签名：
  fn(ctx: dict, old: float, new: float) -> dict
  - 置信度骤降时触发
  - 返回锚定建议写入 ctx
"""

import sys
from pathlib import Path

# ── 预置空桩（待接入时替换）───────────────────────────────

def hp1_before_stub(ctx: dict) -> tuple:
    """默认实现：直接放行"""
    return True, ctx


def hp1_after_stub(ctx: dict, result: bool) -> bool:
    """默认实现：不做修改"""
    return result


def hp1_on_tension_stub(ctx: dict) -> dict:
    """默认实现：无降压建议"""
    return {}


def hp1_on_confidence_stub(ctx: dict, old: float, new: float) -> dict:
    """默认实现：无锚定建议"""
    return {}


# ── 实际 integration：接入 neural_reflex.py ──────────────
# 做法：neural_reflex.py 的 alignment_verify() 函数末尾加入：
#
#   from src.hook_injector import run_hooks, HP1_ALIGNMENT_VERIFY, HookType
#   hook_result = run_hooks(HP1_ALIGNMENT_VERIFY, HookType.BEFORE, {
#       "content": output_content,
#       "confidence": current_conf,
#       "steel_mark": steel_conflict,
#       "safety_level": safety_level,
#       "output_channel": channel,
#   })
#   if hook_result["short_circuited"]:
#       return False  # 钩子要求短路
#
# AFTER 集成：在返回 True/False 之后调用 run_hooks(HP1, AFTER, ctx, result)


# ── 便捷注册 ────────────────────────────────────────────
def register_defaults():
    """注册默认空桩（可在真实钩子注册前提供基线行为）"""
    import importlib
    import hook_injector as hi
    importlib.reload(hi)

    hi.register_hook(
        "HP1", hi.HookType.BEFORE, "stub_pass",
        hp1_before_stub, priority=999
    )
    hi.register_hook(
        "HP1", hi.HookType.AFTER, "stub_keep",
        hp1_after_stub, priority=999
    )
    hi.register_hook(
        "HP1", hi.HookType.ON_TENSION, "stub_tension",
        hp1_on_tension_stub, priority=999
    )
    hi.register_hook(
        "HP1", hi.HookType.ON_CONFIDENCE, "stub_confidence",
        hp1_on_confidence_stub, priority=999
    )


if __name__ == "__main__":
    register_defaults()
    print("HP1 defaults registered")
