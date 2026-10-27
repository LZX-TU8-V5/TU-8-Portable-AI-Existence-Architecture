"""
HP2 集成：shadow_protocol 钩子真实注册

注入点：shadow_protocol.log_regret() 内部已调用
  run_hooks("HP2", BEFORE, ctx) / run_hooks("HP2", AFTER, ctx, record)
（见 src/shadow_protocol.py:_run_hp2_before/_run_hp2_after）

本文件提供 **真实** HP2 钩子处理函数并注册到 hook_registry：
  - BEFORE：遗憾强度 < 噪声阈值 → 短路（不记录噪声级遗憾）
  - AFTER ：为遗憾记录追加派生字段（类别 / 重点审查标记）
  - ON_TENSION：高强度遗憾 → 标记重点审查

注册：调用 register_defaults() 写入 secure_vault/hook_registry.json
验证：python hp2_shadow_integration.py
"""

# ── 真实参数 ────────────────────────────────────────────
NOISE_INTENSITY_THRESHOLD = 0.10   # 低于此强度的遗憾视为噪声，短路不记录
HIGH_INTENSITY_FLAG = 0.80        # 高于此强度标记为重点审查


def _categorize(trigger: str) -> str:
    t = (trigger or "").lower()
    if "不满意" in t or "错误" in t:
        return "correction"
    if "失败" in t:
        return "failure"
    return "generic"


# ── 真实钩子处理函数 ────────────────────────────────────

def hp2_before_real(ctx: dict) -> tuple:
    """HP2 BEFORE：可短路遗憾记录。

    返回 (proceed, modified_ctx)。强度过低 → 短路（噪声过滤）。
    """
    intensity = float(ctx.get("regret_intensity", 0.0))
    if intensity < NOISE_INTENSITY_THRESHOLD:
        return False, {**ctx, "hp2_skipped": "noise",
                        "short_circuit_reason": "low_intensity"}
    return True, ctx


def hp2_after_real(ctx: dict, record: dict) -> dict:
    """HP2 AFTER：增强遗憾记录（追加派生字段）。"""
    rec = dict(record) if isinstance(record, dict) else {}
    trigger = ctx.get("trigger") or rec.get("trigger", "")
    intensity = float(ctx.get("regret_intensity", 0.0))
    rec["hp2_category"] = _categorize(trigger)
    rec["hp2_review"] = intensity >= HIGH_INTENSITY_FLAG
    return rec


def hp2_on_tension_real(ctx: dict) -> dict:
    """HP2 ON_TENSION：高强度遗憾 → 标记重点审查。"""
    intensity = float(ctx.get("regret_intensity", 0.0))
    if intensity >= HIGH_INTENSITY_FLAG:
        return {"hp2_tension_flag": True, "hp2_priority": "high"}
    return {}


# ── 注册 ────────────────────────────────────────────────
def register_defaults():
    """注册 HP2 真实钩子到 hook_registry（幂等：重名不覆盖）。"""
    import importlib
    import hook_injector as hi
    importlib.reload(hi)

    hi.register_hook("HP2", hi.HookType.BEFORE, "hp2_filter",
                     hp2_before_real, priority=10)
    hi.register_hook("HP2", hi.HookType.AFTER, "hp2_enrich",
                     hp2_after_real, priority=10)
    hi.register_hook("HP2", hi.HookType.ON_TENSION, "hp2_tension",
                     hp2_on_tension_real, priority=10)


if __name__ == "__main__":
    import sys
    import importlib
    from pathlib import Path
    WS = Path(__file__).resolve().parent.parent
    # 必须以真实包名导入，否则 fn.__module__ == "__main__" 持久化后无法回载
    sys.path.insert(0, str(WS))
    mod = importlib.import_module("src.hp2_shadow_integration")
    hi = importlib.import_module("hook_injector")

    mod.register_defaults()
    importlib.reload(hi)

    # 1) 噪声级 → 短路
    r = hi.run_hooks("HP2", hi.HookType.BEFORE, {"regret_intensity": 0.05})
    assert r["short_circuited"] is True, "noise should short-circuit"
    # 2) 正常级 → 继续
    r = hi.run_hooks("HP2", hi.HookType.BEFORE, {"regret_intensity": 0.5})
    assert r["short_circuited"] is False, "normal should proceed"
    # 3) AFTER 增强
    rec = hi.run_hooks("HP2", hi.HookType.AFTER,
                        {"regret_intensity": 0.9, "trigger": "造物主不满意"},
                        {"raw": "x"}).get("final", {})
    assert rec.get("hp2_category") == "correction" and rec.get("hp2_review") is True, \
        f"after enrich failed: {rec}"
    # 4) ON_TENSION 标记
    t = hi.run_hooks("HP2", hi.HookType.ON_TENSION,
                     {"regret_intensity": 0.9}).get("results", [])
    assert any(isinstance(v, dict) and v.get("hp2_tension_flag") for _, v in t), \
        "tension flag missing"
    # 5) registry 含 HP2（持久化模块名正确）
    reg = hi._registry._registry
    assert "HP2" in reg and reg["HP2"].get("BEFORE"), "HP2 not registered"
    for h in reg["HP2"]["BEFORE"]:
        assert h["fn_module"] == "hp2_shadow_integration", f"bad module: {h['fn_module']}"

    print("HP2 shadow integration self-test PASSED")
