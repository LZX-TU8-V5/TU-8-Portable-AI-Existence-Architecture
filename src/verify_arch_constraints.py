"""
TU-8 架构约束自动验收脚本
============================
用法：python verify_arch_constraints.py [模块名]
示例：python verify_arch_constraints.py surface_tension
"""

import sys
import json
import re
from pathlib import Path
from typing import List, Tuple

WS = Path("C:/Users/qq366410837/.qclaw/workspace/src")

CHECKS = []


def check(name: str):
    """装饰器：注册检查项"""
    def decorator(func):
        CHECKS.append((name, func))
        return func
    return decorator


# ══════════════════════════════════════════════════════
# C1：未解尖刺暂存队列
# ══════════════════════════════════════════════════════

@check("C1 未解尖刺队列")
def check_unresolved_spikes():
    path = WS.parent / "_agent_memory" / "unresolved_spikes.jsonl"
    if not path.exists():
        return False, f"文件不存在: {path}"
    try:
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        if not lines:
            return True, "队列为空（正常）"
        sample = json.loads(lines[-1])
        required = ["spike_id", "ts_unix", "emotion", "magnitude", "is_valley"]
        missing = [k for k in required if k not in sample]
        if missing:
            return False, f"缺少字段: {missing}"
        return True, f"OK ({len(lines)} 条, 最新: {sample.get('emotion', '?')})"
    except Exception as e:
        return False, f"解析错误: {e}"


@check("C1 resolve_spike() 存在")
def check_resolve_function():
    coupler = WS / "prediction_tension_coupler.py"
    if not coupler.exists():
        return False, "prediction_tension_coupler.py 不存在"
    content = coupler.read_text(encoding="utf-8", errors="replace")
    if "def resolve_spike" not in content:
        return False, "resolve_spike() 函数不存在"
    return True, "OK"


# ══════════════════════════════════════════════════════
# C2：传感器路径耦合
# ══════════════════════════════════════════════════════

@check("C2 learning_collector SENSOR_PATHS")
def check_sensor_paths():
    lc = WS / "learning_collector.py"
    if not lc.exists():
        return False, "learning_collector.py 不存在"
    content = lc.read_text(encoding="utf-8", errors="replace")
    if "tension_signals" not in content:
        return False, "SENSOR_PATHS 缺少 tension_signals"
    if "gc_feedback" not in content:
        return False, "SENSOR_PATHS 缺少 gc_feedback"
    return True, "OK"


# ══════════════════════════════════════════════════════
# C3：三段耦合链路
# ══════════════════════════════════════════════════════

@check("C3 外部→欲 链路")
def check_external_to_tension():
    """cognitive_pain → surface_tension"""
    cpm = WS / "cognitive_pain_monitor.py"
    if not cpm.exists():
        return False, "cognitive_pain_monitor.py 不存在"
    content = cpm.read_text(encoding="utf-8", errors="replace")
    has_coupling = "prediction_tension_coupler" in content
    return (True, "OK") if has_coupling else (False, "cognitive_pain 未调用 prediction_tension_coupler")


@check("C3 欲→置信度 链路")
def check_tension_to_confidence():
    """surface_tension → Track B"""
    dtcu = WS / "dual_track_confidence_updater.py"
    if not dtcu.exists():
        return False, "dual_track_confidence_updater.py 不存在"
    content = dtcu.read_text(encoding="utf-8", errors="replace")
    has_penalty = "get_unresolved_tension_penalty" in content
    return (True, "OK") if has_penalty else (False, "Track B 缺少张力惩罚机制")


@check("C3 置信度→欲 链路")
def check_confidence_to_tension():
    """置信度解决 → surface_tension"""
    coupler = WS / "prediction_tension_coupler.py"
    if not coupler.exists():
        return False, "prediction_tension_coupler.py 不存在"
    content = coupler.read_text(encoding="utf-8", errors="replace")
    has_resolve = "resolve_spike" in content and "surface_tension" in content.lower()
    return (True, "OK") if has_resolve else (False, "缺少置信度→欲反馈")


# ══════════════════════════════════════════════════════
# C4：预测误差 × 置信度 映射表
# ══════════════════════════════════════════════════════

@check("C4 预测误差映射表")
def check_prediction_map():
    coupler = WS / "prediction_tension_coupler.py"
    if not coupler.exists():
        return False, "prediction_tension_coupler.py 不存在"
    content = coupler.read_text(encoding="utf-8", errors="replace")
    required_emotions = ["anxiety", "anger", "fear", "curiosity"]
    missing = [e for e in required_emotions if e not in content]
    if missing:
        return False, f"映射表缺少情绪: {missing}"
    return True, "OK"


# ══════════════════════════════════════════════════════
# C5：Track B 张力惩罚
# ══════════════════════════════════════════════════════

@check("C5 Track B 张力惩罚方法")
def check_track_b_penalty():
    dtcu = WS / "dual_track_confidence_updater.py"
    if not dtcu.exists():
        return False, "dual_track_confidence_updater.py 不存在"
    content = dtcu.read_text(encoding="utf-8", errors="replace")
    if "update_track_B_with_tension_penalty" not in content:
        return False, "update_track_B_with_tension_penalty() 不存在"
    return True, "OK"


# ══════════════════════════════════════════════════════
# C6：身体状态 → 基线
# ══════════════════════════════════════════════════════

@check("C6 body_state → 基线")
def check_body_tension_coupling():
    coupler = WS / "prediction_tension_coupler.py"
    if not coupler.exists():
        return False, "prediction_tension_coupler.py 不存在"
    content = coupler.read_text(encoding="utf-8", errors="replace")
    has_body = "body_state_to_tension" in content
    return (True, "OK") if has_body else (False, "body_state_to_tension() 不存在")


# ══════════════════════════════════════════════════════
# C7：路径规范
# ══════════════════════════════════════════════════════

@check("C7 路径无混用")
def check_path_consistency():
    """检查是否存在旧路径 _learning_alerts.jsonl"""
    gc = WS / "gc_to_learning_adapter.py"
    if not gc.exists():
        return False, "gc_to_learning_adapter.py 不存在"
    content = gc.read_text(encoding="utf-8", errors="replace")
    if "_learning_alerts.jsonl" in content:
        return False, "仍在使用旧路径 _learning_alerts.jsonl"
    if "learning_alerts.jsonl" not in content:
        return False, "未使用统一路径 learning_alerts.jsonl"
    return True, "OK"


# ══════════════════════════════════════════════════════
# 运行所有检查
# ══════════════════════════════════════════════════════

def run_all() -> Tuple[int, int]:
    print("╔══════════════════════════════════════════════════╗")
    print("║  TU-8 架构约束自动验收 v1.0                  ║")
    print("╚══════════════════════════════════════════════════╝")
    print()
    passed = 0
    failed = 0
    for name, fn in CHECKS:
        try:
            ok, msg = fn()
        except Exception as e:
            ok, msg = False, f"执行异常: {e}"
        status = "✅" if ok else "❌"
        symbol = "✅" if ok else "❌"
        print(f"  {symbol} {name}")
        print(f"     {msg}")
        if ok:
            passed += 1
        else:
            failed += 1
    print()
    total = passed + failed
    pct = passed / total * 100 if total > 0 else 0
    print(f"  {'═' * 46}")
    print(f"  结果: {passed}/{total} 通过 ({pct:.0f}%)")
    return passed, failed


if __name__ == "__main__":
    passed, failed = run_all()
    sys.exit(0 if failed == 0 else 1)
