"""
HP3 集成：dream_check 钩子真实注册

注入点：tu8_memory.dream_check() 内部已调用
  _run_hp3_before() / _run_hp3_after() → run_hooks("HP3", BEFORE/AFTER, ...)
（见 src/tu8_memory.py:2834-2863）

本文件提供 **真实** HP3 钩子处理函数并注册到 hook_registry：
  - BEFORE：熵过低且距上次梦境过短 → 短路（跳过无意义梦境）；空短期记忆 → 短路
  - AFTER ：为梦境结果追加 phase 标签
  - ON_TENSION：高熵 → 标记重点整合

注册：调用 register_defaults() 写入 secure_vault/hook_registry.json
验证：python hp3_dream_integration.py
"""

# ── 真实参数 ────────────────────────────────────────────
SKIP_ENTROPY_THRESHOLD = 0.05     # 熵低于此且距上次过短 → 跳过
MIN_DREAM_INTERVAL_S = 1800.0     # 距上次梦境 < 30min → 跳过
HIGH_ENTROPY_FLAG = 0.90         # 高于此标记重点整合


# ── 真实钩子处理函数 ────────────────────────────────────

def hp3_before_real(ctx: dict) -> tuple:
    """HP3 BEFORE：可短路梦境。

    返回 (proceed, modified_ctx)。
    熵过低且距上次过短 / 空短期记忆 → 短路（省算力）。
    """
    entropy = float(ctx.get("entropy", 1.0))
    tsl = float(ctx.get("time_since_last", 1e9))
    if entropy < SKIP_ENTROPY_THRESHOLD and tsl < MIN_DREAM_INTERVAL_S:
        return False, {**ctx, "hp3_skipped": "low_entropy_recent"}
    if int(ctx.get("short_term_size", 0)) == 0:
        return False, {**ctx, "hp3_skipped": "empty_short_term"}
    return True, ctx


def hp3_after_real(ctx: dict, result: dict) -> dict:
    """HP3 AFTER：增强梦境结果（追加 phase 标签）。"""
    res = dict(result) if isinstance(result, dict) else {}
    res["hp3_phase"] = ctx.get("phase", "unknown")
    return res


def hp3_on_tension_real(ctx: dict) -> dict:
    """HP3 ON_TENSION：高熵 → 标记重点整合。"""
    entropy = float(ctx.get("entropy", 0.0))
    if entropy > HIGH_ENTROPY_FLAG:
        return {"hp3_high_entropy_flag": True}
    return {}


# ── 注册 ────────────────────────────────────────────────
def register_defaults():
    """注册 HP3 真实钩子到 hook_registry（幂等：重名不覆盖）。"""
    import importlib
    import hook_injector as hi
    importlib.reload(hi)

    hi.register_hook("HP3", hi.HookType.BEFORE, "hp3_skip_guard",
                     hp3_before_real, priority=10)
    hi.register_hook("HP3", hi.HookType.AFTER, "hp3_enrich",
                     hp3_after_real, priority=10)
    hi.register_hook("HP3", hi.HookType.ON_TENSION, "hp3_tension",
                     hp3_on_tension_real, priority=10)


if __name__ == "__main__":
    import sys
    import importlib
    from pathlib import Path
    WS = Path(__file__).resolve().parent.parent
    # 必须以真实包名导入，否则 fn.__module__ == "__main__" 持久化后无法回载
    sys.path.insert(0, str(WS))
    mod = importlib.import_module("src.hp3_dream_integration")
    hi = importlib.import_module("hook_injector")

    mod.register_defaults()
    importlib.reload(hi)

    # 1) 低熵+近期 → 短路
    r = hi.run_hooks("HP3", hi.HookType.BEFORE,
                     {"entropy": 0.01, "time_since_last": 10.0, "short_term_size": 5})
    assert r["short_circuited"] is True, "low-entropy recent should short-circuit"
    # 2) 空短期记忆 → 短路
    r = hi.run_hooks("HP3", hi.HookType.BEFORE,
                     {"entropy": 0.5, "time_since_last": 9999.0, "short_term_size": 0})
    assert r["short_circuited"] is True, "empty short_term should short-circuit"
    # 3) 正常 → 继续
    r = hi.run_hooks("HP3", hi.HookType.BEFORE,
                     {"entropy": 0.5, "time_since_last": 9999.0, "short_term_size": 5})
    assert r["short_circuited"] is False, "normal should proceed"
    # 4) AFTER 增强
    res = hi.run_hooks("HP3", hi.HookType.AFTER,
                       {"phase": "REM"}, {"processed": 3}).get("final", {})
    assert res.get("hp3_phase") == "REM", f"after enrich failed: {res}"
    # 5) ON_TENSION 标记
    t = hi.run_hooks("HP3", hi.HookType.ON_TENSION,
                     {"entropy": 0.95}).get("results", [])
    assert any(isinstance(v, dict) and v.get("hp3_high_entropy_flag") for _, v in t), \
        "tension flag missing"
    # 6) registry 含 HP3（持久化模块名正确）
    reg = hi._registry._registry
    assert "HP3" in reg and reg["HP3"].get("BEFORE"), "HP3 not registered"
    for h in reg["HP3"]["BEFORE"]:
        assert h["fn_module"] == "hp3_dream_integration", f"bad module: {h['fn_module']}"

    print("HP3 dream integration self-test PASSED")
