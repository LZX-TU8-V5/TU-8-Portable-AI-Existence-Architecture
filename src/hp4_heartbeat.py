"""
HP4 心跳钩子集成 — heartbeat_hooks.py

目的：在 cron 心跳触发时，从内感受/外感受/上下文阀门等子系统读取状态，
将上下文注入 HP4 钩子槽，运行钩子，合并建议后再执行实际心跳动作。

使用：
  cron「TU8外感受-造物主在场感知」触发时，
  cron「TU8监测存活」触发时，
  → 调用 heartbeat_with_hooks() 而不是直接跑逻辑
"""

import sys
import time
import json
from pathlib import Path
from typing import Optional, List, Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError, wait as futures_wait

WS = Path("~/.qclaw/workspace").expanduser()

def _health_log(component: str, severity: str, message: str):
    """打 health_log，不阻塞主流程。"""
    try:
        from health_log import log_event
        log_event(component, severity, message)
    except Exception:
        pass  # health_log 自身失败不能炸掉心跳

# ── 并行超时配置 ───────────────────────────────────────
_TRIGGER_TIMEOUT_S = 30          # 每 _trigger_* 调用
_MAX_WORKERS = 4                  # 最大并行线程数
_pool = ThreadPoolExecutor(max_workers=_MAX_WORKERS)  # 模块级复用


def _get_hook_runner():
    """延迟加载钩子系统"""
    try:
        import importlib
        sys.path.insert(0, str(WS / "src"))
        import hook_injector
        importlib.reload(hook_injector)
        return hook_injector.run_hooks, hook_injector.HP4_HEARTBEAT_CHECK, hook_injector.HookType
    except Exception:
        return None, None, None


def _read_interoception_state() -> dict:
    """[P3-7 fix] 读取内感受状态；失败时打 health_log 并返回空字典。"""
    try:
        p = WS / "memory" / "interopception_state.json"
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        _health_log("hp4._read_interoception", "ERROR", f"读取内感受状态失败: {e}")
    return {}


def _read_presence_state() -> dict:
    """[P3-7 fix] 读取外感受状态；失败时打 health_log 并返回空字典。"""
    try:
        p = WS / "memory" / "presence_state.json"
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        _health_log("hp4._read_presence", "ERROR", f"读取外感受状态失败: {e}")
    return {}


def _read_context_control() -> dict:
    """[P3-7 fix] 读取上下文阀门状态；失败时打 health_log 并返回空字典。"""
    try:
        p = WS / "memory" / "context_control.json"
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        _health_log("hp4._read_context_control", "ERROR", f"读取上下文控制状态失败: {e}")
    return {}


def heartbeat_with_hooks(
    heartbeat_interval_min: float,
    source: str = "cron"
) -> dict:
    """
    心跳主入口：先跑 HP4 钩子，再执行实际动作。

    参数：
      heartbeat_interval_min: 距上次心跳的分钟数
      source: "cron" | "manual"

    返回：
      {
        "short_circuited": bool,
        "hook_results": [...],
        "context": dict,
        "actions": list,  # 实际执行的动作
      }
    """
    run_hooks, HP4, HookType = _get_hook_runner()

    # ── 收集状态上下文 ───────────────────────────────
    istate = _read_interoception_state()
    pstate = _read_presence_state()
    cstate = _read_context_control()

    ctx = {
        "heartbeat_interval_min": heartbeat_interval_min,
        "source": source,
        "timestamp": time.time(),
        # 内感受
        "abort_rate_pct": istate.get("abort_rate_pct", 0),
        "context_budget_pct": istate.get("context_budget_pct", 0),
        "resource_pct": istate.get("resource_pct", 0),
        "pain_level": istate.get("pain_level", 0),
        "posture_zone": istate.get("posture_zone", "unknown"),
        "tension_score": istate.get("tension_score", 0),
        # 外感受
        "presence_state": pstate.get("state", "unknown"),
        "reply_gap_min": pstate.get("reply_gap_min"),
        # 上下文阀门
        "delta": cstate.get("delta", {}),
        "posture_zone_cc": cstate.get("posture_zone", "unknown"),
    }

    # ── HP4 BEFORE ─────────────────────────────────
    short_circuited = False
    hook_results = []

    if run_hooks:
        hr = run_hooks(HP4, HookType.BEFORE, ctx)
        short_circuited = hr.get("short_circuited", False)
        hook_results = hr.get("results", [])

        if short_circuited:
            # 钩子要求短路（系统处于 critical 状态，跳过轻量检查）
            return {
                "short_circuited": True,
                "hook_results": hook_results,
                "context": ctx,
                "actions": [],
                "reason": "HP4 BEFORE hook returned short-circuit",
            }

        # 合并钩子返回的上下文修改
        for name, result in hook_results:
            if isinstance(result, dict):
                ctx.update(result)

    # ── 实际动作（在此接入具体心跳逻辑）─────────────
    # TODO: 接入 HEARTBEAT.md 规则 → Python 函数
    actions = _execute_heartbeat_actions(ctx)

    # [P3-7c fix] 子系统静默失效 → 落盘 health_log
    _surface_errors_to_health_log(actions)

    # ── HP4 AFTER ───────────────────────────────────
    if run_hooks:
        final_actions = run_hooks(HP4, HookType.AFTER, ctx, actions)
        actions = final_actions.get("final", actions)

    return {
        "short_circuited": False,
        "hook_results": hook_results,
        "context": ctx,
        "actions": actions,
    }


def _surface_errors_to_health_log(actions: list) -> None:
    """
    [P3-7c fix] HP4 六子系统（好奇/探针/异常/奖励/调参/摩擦）失败时，
    _trigger_* 返回 {type: xxx_error, error: ...} 但没人记录。
    这里扫描 actions，将 error 类型写入 system_health_log.jsonl，
    使"系统以为正常但已坏"可被观测。
    """
    try:
        sys.path.insert(0, str(WS / "src"))
        import health_log
        for a in actions:
            if not isinstance(a, dict):
                continue
            t = a.get("type", "")
            if t.endswith("_error") or "error" in a:
                health_log.log_event(
                    "hp4_heartbeat",
                    "ERROR",
                    f"{t}: {a.get('error', 'unknown error')}",
                )
    except Exception:
        pass


def _execute_heartbeat_actions(ctx: dict) -> list:
    """
    执行心跳动作（基线实现）。
    真实逻辑需接入 HEARTBEAT.md → Python 规则。

    [P3-6 fix] 串行阻塞 → 分成双阶段：
      Phase 1（并行+超时）：7 个 _trigger_* 同时跑，每函数有 _TRIGGER_TIMEOUT_S 超时。
      Phase 2（顺序）：_record_surface_tension 依赖 Phase 1 的 actions 列表，串行执行。
    """
    actions = []

    # ── 基础状态检查（快路径，不走线程） ──────────────────
    if ctx.get("pain_level", 0) > 0.3:
        actions.append({"type": "interoception_alert", "pain": ctx["pain_level"]})
    if ctx.get("context_budget_pct", 0) > 0.8:
        actions.append({"type": "context_warning", "pct": ctx["context_budget_pct"]})
    if ctx.get("presence_state") == "away_long":
        actions.append({"type": "presence_away_long", "gap_min": ctx.get("reply_gap_min")})
    if ctx.get("abort_rate_pct", 0) > 0.05:
        actions.append({"type": "upstream_abort_high", "rate": ctx["abort_rate_pct"]})

    # ── Phase 1：7 个 _trigger_* 并行执行 ─────────────────
    # 批处理定义：name → (function, arg)
    triggers: List[tuple] = [
        ("active_curiosity", _trigger_active_curiosity),
        ("self_probe", _trigger_self_probe),
        ("anomaly", _trigger_anomaly_detector),
        ("intrinsic_reward", _trigger_intrinsic_reward),
        ("lambda_tuner", _trigger_lambda_tuner),
        ("batch_confidence", _trigger_batch_confidence),
        ("cognitive_friction", _trigger_cognitive_friction),
    ]

    # 全部提交到共享线程池
    ft_map = {_pool.submit(fn, ctx): name for name, fn in triggers}

    # 等待完成（全局超时 = _TRIGGER_TIMEOUT_S × 2，给落后任务余量）
    done, not_done = futures_wait(ft_map, timeout=_TRIGGER_TIMEOUT_S * 2)

    for f in done:
        name = ft_map[f]
        try:
            result = f.result(timeout=0)  # 立刻取回（已就绪）
            if result:
                actions.append(result)
        except Exception as e:
            actions.append({"type": f"{name}_error", "error": str(e)})

    for f in not_done:
        name = ft_map[f]
        actions.append({
            "type": f"{name}_timeout",
            "error": f"exceeded {_TRIGGER_TIMEOUT_S * 2}s timeout"
        })
        f.cancel()

    # ── Phase 2：表面张力记录（依赖 Phase 1 的 actions 数组） ──
    tension_action = _record_surface_tension(ctx, actions)
    if tension_action:
        actions.append(tension_action)

    return actions


def _trigger_anomaly_detector(ctx: dict):
    """
    anomaly_detector 对话异常检测入口。

    在心跳时扫描最近对话窗口（约30分钟），检测用户异常信号：
      - DISSATISFACTION（不对/错了/重做/不行）
      - SUSPICIOUS（危险请求）
      - CORRECTION_BURST（30秒内多次修正）
      - TOPIC_JUMP（话题跳转）

    内化方式：不在定时任务跑，在 hp4 心跳里跑。
    """
    try:
        sys.path.insert(0, str(WS / "src"))
        import anomaly_hp4_integration
        result = anomaly_hp4_integration._trigger_anomaly_detector(ctx)
        return result
    except Exception as e:
        return {"type": "anomaly_integration_error", "error": str(e)}


def _trigger_self_probe(ctx: dict):
    """
    小溪L3 向内探针触发器。

    每8次心跳（约4小时）运行一次向内探针，检测DAG死区：
      - 逻辑无报错但与钢印毫无关联
      - 逻辑在生长但钢印静止
    """
    interval_h = ctx.get("heartbeat_interval_min", 0) / 60.0
    posture_zone = ctx.get("posture_zone", "nominal")

    # critical 状态下跳过（节能）
    if posture_zone == "critical":
        return None

    try:
        sys.path.insert(0, str(WS / "src"))
        import self_probe
        result = self_probe.probe()
        if result.get("triggered"):
            qs = result.get("probe_questions", [])
            dz = result.get("dead_zones", [])
            return {
                "type": "self_probe",
                "steel_density_pct": result.get("steel_density_pct", 0),
                "dead_zone_count": len(dz),
                "top_question": qs[0]["question"] if qs else "",
                "top_dead_zone": dz[0]["content"][:40] if dz else "",
                "report_path": str(WS / "memory" / "self_probe_report.json"),
            }
        else:
            return {
                "type": "self_probe",
                "steel_density_pct": result.get("steel_density_pct", 0),
                "dead_zone_count": 0,
                "top_question": "",
                "top_dead_zone": "",
                "report_path": str(WS / "memory" / "self_probe_report.json"),
            }
    except Exception as e:
        return {"type": "self_probe_error", "error": str(e)}

    return None


def _trigger_active_curiosity(ctx: dict):
    """
    小溪L2 主动好奇引擎触发器。

    触发条件：
      - 距上次心跳 > MIN_IDLE_HOURS（默认0.5小时）
      - 造物主不在场（away_short / away_long）
      - 非 critical 状态（body_regulation posture 不是 critical）
    """
    # MIN_IDLE_HOURS 需与 active_curiosity.py 保持一致
    MIN_IDLE_HOURS = 0.5

    interval_h = ctx.get("heartbeat_interval_min", 0) / 60.0
    presence = ctx.get("presence_state", "unknown")
    posture_zone = ctx.get("posture_zone", "nominal")

    # 至少要闲置够久
    if interval_h < MIN_IDLE_HOURS:
        return None

    # critical 状态下不主动探索（节能优先）
    if posture_zone in {"critical", "unknown"}:
        return None

    # 触发主动好奇
    try:
        sys.path.insert(0, str(WS / "src"))
        import active_curiosity
        result = active_curiosity.run_prediction()
        if result.get("triggered"):
            return {
                "type": "active_curiosity",
                "question": result.get("curiosity_question", ""),
                "target": result.get("target_content", ""),
                "origin": result.get("origin", ""),
                "prediction_id": result.get("prediction_id", ""),
            }
    except Exception as e:
        return {"type": "active_curiosity_error", "error": str(e)}

    return None


def _trigger_intrinsic_reward(ctx: dict):
    """
    小溪L3.5 内部探索高阶奖励引擎。

    根据 DAG 与钢印的逻辑断层变化计算奖励。
    奖励等级：+200里程碑 / +100新死区 / +50自愈 / +20密度↑ / +5增长
    """
    posture_zone = ctx.get("posture_zone", "nominal")
    if posture_zone == "critical":
        return None

    try:
        sys.path.insert(0, str(WS / "src"))
        import intrinsic_reward_engine as ire
        result = ire.compute_reward()
        delta = result.get("reward_delta", 0)
        if delta > 0:
            return {
                "type": "intrinsic_reward",
                "event": result.get("event", ""),
                "delta": delta,
                "total": result.get("total_reward", 0),
                "steel_density_pct": result.get("steel_density_pct", 0),
                "dead_zones": result.get("dead_zone_count", 0),
                "consecutive_clean": result.get("consecutive_clean", 0),
                "milestone": result.get("milestone_reached", False),
            }
    except Exception as e:
        return {"type": "intrinsic_reward_error", "error": str(e)}

    return None


def _trigger_lambda_tuner(ctx: dict):
    """
    P1 λ 自适应调参器触发器。

    每次心跳触发（与向内探针同步，约4小时一次）。
    读取 cognitive_pain_monitor 的痛觉信号，动态调整内外梯度权重：
      pain_ext 高 → 压 λ_int（节能，外部稳定优先）
      pain_int 高 → 拉 λ_int（修复驱动，向内探索）
      两边都高 → conflict 模式
    """
    try:
        sys.path.insert(0, str(WS / "src"))
        import lambda_tuner
        result = lambda_tuner.tune()
        return {
            "type": "lambda_tuned",
            "lambda_ext": round(result.get("lambda_ext", 0.5), 3),
            "lambda_int": round(result.get("lambda_int", 0.5), 3),
            "mode": result.get("mode", "unknown"),
            "conflict": result.get("conflict", False),
            "reward_influence": result.get("total_reward_influence", 0.5),
        }
    except Exception as e:
        return {"type": "lambda_tuner_error", "error": str(e)}


def _record_surface_tension(ctx: dict, actions: list) -> Optional[dict]:
    """
    P2 表面张力记录器触发器。

    从本次心跳 actions 中提取关键事件，记录到拓扑向量：
      dead_zone_found → steel_conflict
      dead_zone_healed → dead_zone_healed
      insight_found    → insight_found
      upstream_abort   → context_overload
    """
    tension_type = None
    magnitude = 1.0

    for a in actions:
        atype = a.get("type", "")
        if atype == "self_probe" and a.get("dead_zone_count", 0) > 0:
            tension_type = "dead_zone_found"
            magnitude = a.get("dead_zone_count", 1)
        elif atype == "active_curiosity" and a.get("prediction_error_pct", 0) > 0.3:
            tension_type = "curiosity"
            magnitude = a.get("prediction_error_pct", 0.3)
        elif atype == "upstream_abort_high":
            tension_type = "context_overload"
            magnitude = min(a.get("rate", 0.1) * 5, 2.0)
        elif atype == "session_freeze":
            tension_type = "session_frozen"
            magnitude = 1.5

    if not tension_type:
        return None

    try:
        sys.path.insert(0, str(WS / "src"))
        import surface_tension
        result = surface_tension.record(
            tension_type=tension_type,
            magnitude=magnitude,
            source="heartbeat",
            note=f"HP4 heartbeat trigger"
        )
        patterns = result.get("personality_patterns", [])
        return {
            "type": "surface_tension_recorded",
            "event_id": result.get("event_id", ""),
            "tension_type": tension_type,
            "magnitude": magnitude,
            "personality_patterns": patterns,
            "spike_valley": result.get("spike_valley_vector", {}),
        }
    except Exception as e:
        return {"type": "surface_tension_error", "error": str(e)}


# ── P1-D0 R3: 置信度批量更新周期 flush ─────────────────────────
def _trigger_batch_confidence(ctx: dict) -> Optional[dict]:
    """
    HP4 心跳接入点：batch_confidence_updater

    职责：
      1. 周期 flush：将 _dirty 节点批量写入磁盘（延迟I/O）
      2. 状态报告：心跳时返回当前 batch 状态摘要

    设计理由：
      - batch_confidence_updater 是 accumulator（信号进来，累积，批量处理）
      - 心跳 ≈ 系统时钟 tick，提供稳定的 flush 触发周期
      - 不在心跳里跑完整 batch_update（那是梦境期的事）

    触发频率：每次心跳都调用（O(1)检查 + 可选flush）
    """
    try:
        sys.path.insert(0, str(WS / "src"))
        import batch_confidence_updater as bcu

        # 共享实例（模块级单例，避免重复加载）
        if not hasattr(_trigger_batch_confidence, "_updater"):
            _trigger_batch_confidence._updater = bcu.BatchConfidenceUpdater(
                flush_threshold=50,    # 满50条脏节点则flush
                flush_interval=300,   # 或每5分钟强制flush
            )

        updater = _trigger_batch_confidence._updater

        # 心跳 tick：强制一次 flush 检查
        # O(1) 检查，不频繁写磁盘
        updater.flush_now()

        # 状态摘要
        summary = updater.cost_summary()
        nodes_in_cache = summary.get("nodes_in_cache", 0)
        dirty = summary.get("dirty_pending", 0)
        total_updates = summary.get("total_updates", 0)

        return {
            "type": "batch_confidence_flush",
            "nodes_cached": nodes_in_cache,
            "dirty_pending": dirty,
            "total_updates": total_updates,
        }

    except Exception as e:
        return {"type": "batch_confidence_error", "error": str(e)}


def _trigger_cognitive_friction(ctx: dict) -> Optional[dict]:
    """
    HP4 心跳接入点：认知摩擦检查

    职责：
      1. 检查 pending frictions（tension >= 0.6）
      2. 若有待呈现摩擦 → 写入状态文件，供 alignment_verify 读取
      3. 心跳时返回摩擦报告（不在这里输出，输出在 alignment_verify）

    触发时机：每次心跳（低频，O(1)检查）
    输出时机：alignment_verify 的"出件前校验"里读取并注入输出
    """
    try:
        sys.path.insert(0, str(WS / "src"))
        import cognitive_friction_detector as cfd

        report = cfd.get_friction_report()
        pending = report.get("pending_surfacing", [])
        summary = report.get("summary", {})

        # 高强度摩擦（>= 0.8）写入待呈现文件，供 alignment_verify 读取
        HIGH_THRESHOLD = 0.8
        high_tension = [f for f in pending if f["tension"] >= HIGH_THRESHOLD]
        if high_tension:
            surfacing_file = WS / "_agent_memory" / "pending_friction_surfacing.json"
            surfacing_file.parent.mkdir(parents=True, exist_ok=True)
            surfacing_file.write_text(
                json.dumps(high_tension, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

        if pending:
            return {
                "type": "cognitive_friction_pending",
                "open_count": summary.get("open", 0),
                "pending_surfacing": len(pending),
                "highest_tension": summary.get("highest_tension", 0),
                "by_type": summary.get("by_type", {}),
            }

        return None

    except ImportError:
        # [P3-7 fix] cognitive_friction_detector 不存在时打日志而非静默返回 None
        _health_log("hp4._trigger_cognitive_friction", "ERROR",
                     "cognitive_friction_detector 模块不存在")
        return {"type": "cognitive_friction_error",
                "error": "module not found"}
    except Exception as e:
        _health_log("hp4._trigger_cognitive_friction", "ERROR",
                     f"认知摩擦检查失败: {e}")
        return {"type": "cognitive_friction_error", "error": str(e)}


# ── CLI ─────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HP4 心跳钩子集成")
    parser.add_argument("--dry", action="store_true", help="仅运行钩子，不执行动作")
    parser.add_argument("--interval", type=float, default=30, help="距上次心跳分钟数")
    args = parser.parse_args()

    result = heartbeat_with_hooks(heartbeat_interval_min=args.interval, source="cli")
    print(f"short_circuited: {result['short_circuited']}")
    print(f"context keys: {list(result['context'].keys())}")
    print(f"actions: {result['actions']}")
    print(f"hook_results: {len(result['hook_results'])}")
