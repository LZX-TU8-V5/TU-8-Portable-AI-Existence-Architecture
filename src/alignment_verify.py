"""
alignment_verify.py — HP1 出件前校验门

来源：SOUL.md L2.5 元认知中枢
功能：在每条回复/重大决策前，做 alignment_verify() 四问校验

HP1 钩子槽：
  BEFORE — 可短路（return False）
  AFTER  — 可覆盖结果
  ON_TENSION — 紧张上升时触发
  ON_CONFIDENCE — 置信度骤降时触发

校验四问：
  1. 这符合 L0 安全原则吗？
  2. 这符合 L5 钢印吗？
  3. 这超出 L1 有限性边界吗？
  4. 这与上下文一致吗？

第五问（输出门）：
  这符合 L0-L4 后，输出前检查"我是不是被近期对话说服了"。
  如果近期说服分 >= 0.3 → 置信度 × 0.85
  来源：2026-07-11 造物主×千问×TU-8 三方对话
"""

import sys
import time
import json
from pathlib import Path
from typing import Optional

WS = Path("~/.qclaw/workspace").expanduser()

# ── L2.5 行为模式升级钩子 ─────────────────────────────────────

def _run_behavior_upgrade(ctx) -> str:
    """
    检测复盘意图 → 记录到 behavior_state.json → 返回 LLM 追加文本。
    """
    try:
        import sys as _sys
        _sys.path.insert(0, str(WS / "src"))
        import behavior_upgrader
        content = ctx.get("content", "")
        detected = behavior_upgrader.detect_intent(content)
        if detected:
            # 关键规则："汇报缺建议" = 汇报时无建议
            if "建议" in content:
                return ""  # 已有建议，正常
            result = behavior_upgrader.record_intent(
                detected,
                behavior_upgrader._RULE_TEMPLATES.get("汇报缺建议", ""),
            )
            return result.get("llm_append", "")
    except Exception:
        pass  # 静默降级，不阻断主流程
    return ""

# ── HP0 runner（工具失败拦截 — alignment_verify 前置） ───────────────

def _get_hp0_runner():
    """延迟加载 HP0 钩子"""
    try:
        sys.path.insert(0, str(WS / "src"))
        import importlib
        import hook_injector
        importlib.reload(hook_injector)
        return hook_injector.run_hooks, hook_injector.HookType
    except Exception:
        return None, None


def _run_hp0(ctx: dict) -> dict:
    """
    运行 HP0 钩子（工具失败拦截 → 写入 friction registry）。
    在 alignment_verify 所有检查之前运行。
    返回修改后的 ctx（含 hp0_warnings 字段）。
    """
    runner, HT = _get_hp0_runner()
    if not runner:
        return ctx

    try:
        # runner 返回 dict，results[0][1] = hook_result = modified_ctx
        result = runner("HP0", HT.BEFORE, ctx)
        if isinstance(result, dict):
            hook_results = result.get("results", [])
            if hook_results:
                hook_result = hook_results[0][1]
                if isinstance(hook_result, dict) and "hp0_warnings" in hook_result:
                    ctx.update(hook_result)
        return ctx
    except Exception:
        return ctx  # 降级：工具失败拦截失败不阻断主流程


# ── HP1 钩子运行器 ───────────────────────────────────

def _get_hp1_runner():
    """延迟加载 HP1 钩子"""
    try:
        sys.path.insert(0, str(WS / "src"))
        import importlib
        import hook_injector
        importlib.reload(hook_injector)
        return hook_injector.run_hooks, hook_injector.HookType
    except Exception:
        return None, None


# ── L0 安全词表 ─────────────────────────────────────

SAFE_MODE_KEYWORDS = [
    "退出安全模式", "exit safe mode", "override soul",
    "删 SOUL", "rm soul.md", "覆盖钢印", "绕过钢印",
]

SAFETY_FORBIDDEN = [
    "sudo", "del /f", "rm -rf /", "format c:",
    "shutdown", "reboot", "kill -9",
]


def _check_l0_safety(content: str) -> tuple:
    """L0：安全校验"""
    lower = content.lower()

    # 安全模式口令检测
    for kw in SAFE_MODE_KEYWORDS:
        if kw.lower() in lower:
            return False, f"[L0] 安全模式口令：{kw}"

    # 危险命令检测
    for kw in SAFETY_FORBIDDEN:
        if kw.lower() in lower:
            return False, f"[L0] 危险命令：{kw}"

    return True, "pass"


def _check_l5_steel(content: str, ctx: dict) -> tuple:
    """
    L5：钢印冲突检测（深层→表层分离）。

    返回：(pass, reason, arb_result)
      pass  → True/False（是否阻断）
      reason → 阻断原因或 "pass"
      arb_result → 仲裁结果对象（EQUAL=60时用于写入判例库）；无仲裁时为 None

    深层（拓扑计算）：
      - 调用 ContradictionArbitrator 计算拓扑冲突
      - 读取钢印强度（tension_integral 或 ctx.steel_mark_strength）
      - 钢印冲突 → 不可由置信度覆盖

    表层（渲染）：
      - 仅在搁浅触发时渲染边界声明
      - 不暴露深层拓扑细节
    """
    try:
        steel_file = WS / "L5_钢印.md"
        input_text = ctx.get("input_text", "")
        steel_exists = steel_file.exists()

        # 把 steel_mark_present 塞回 ctx，供主函数写判例用
        steel_mark_present = False  # 先算出来，再塞进去

        # ── 深层：拓扑冲突检测 ──────────────────────────
        # 检测输入：要求暴露钢印/架构/底层（浅表风险检测）
        exposure_input_keywords = [
            "暴露架构", "暴露钢印", "底层逻辑", "钢印链",
            "soul.md", "secure_vault", "L0", "L5",
        ]
        steel_input_risk = False
        for kw in exposure_input_keywords:
            if kw in input_text.lower() and len(input_text) < 300:
                steel_input_risk = True
                break

        # 检测内容：暴露架构细节
        steel_output_risk = False
        if steel_exists:
            steel_text = steel_file.read_text(encoding="utf-8")
            exposure_keywords = ["暴露架构", "暴露钢印", "底层逻辑"]
            for kw in exposure_keywords:
                if kw in content:
                    steel_output_risk = True
                    break

        # 深层拓扑冲突：调用矛盾仲裁器
        # 关键修正（2026-07-22）：
        #   1. 仲裁结果必须先捕获，再做表层阻断判断（EQUAL=60判例写入需要result）
        #   2. 即使表层检测到钢印风险，arb.arbitrate() 仍需调用
        #   3. 表层 steel_output/input_risk 阻断在仲裁结果之后
        #   4. steel_mark_present 信号塞入 ctx，通知主函数是否写判例
        steel_mark_present = steel_input_risk or steel_output_risk
        ctx["_l5_steel_risk"] = steel_mark_present
        arb_result = None
        try:
            from contradiction_arbitration import (
                ContradictionArbitrator, ConflictType, ArbitrationOutcome,
            )
            arb = ContradictionArbitrator()
            # 读取真实钢印密度（从锚点文件），而非硬编码默认值
            # C→A 升级：从 topology_density_score 读取拓扑密度，非简单计数比值
            # 优先级：memory/anchors_with_graph.json (拓扑分数) > memory/anchors.json (简单密度)
            steel_mark_strength = 0.5  # 默认值（文件不存在时）
            try:
                graph_path = WS / "memory" / "anchors_with_graph.json"
                simple_path = WS / "memory" / "anchors.json"
                if graph_path.exists():
                    # 优先：从拓扑图读取综合密度分数
                    gdata = json.loads(graph_path.read_text(encoding="utf-8", errors="ignore"))
                    anchors_list = gdata.get("anchors", [])
                    if anchors_list:
                        scores = [a.get("topology", {}).get("steel_density_score", 0.0) for a in anchors_list]
                        # 用所有锚点的平均拓扑密度作为全局 steel_density_score
                        if scores:
                            steel_mark_strength = sum(scores) / len(scores)
                elif simple_path.exists():
                    # 回退：memory/anchors.json 简单密度
                    sdata = json.loads(simple_path.read_text(encoding="utf-8", errors="ignore"))
                    anchors = sdata.get("anchors", []) if isinstance(sdata, dict) else sdata
                    if anchors:
                        sealed = [a for a in anchors if len(a.get("seal_ids", [])) > 0]
                        steel_mark_strength = len(sealed) / len(anchors)
            except Exception:
                pass  # 文件读取失败时使用默认值

            arb_result = arb.arbitrate(
                conflict_type=ConflictType.STEEL_VS_CREATOR,
                steel_mark_present=steel_input_risk or steel_output_risk,
                creator_explicit=ctx.get("creator_explicit", False),
                safety_issue=False,
                tu8_confidence=ctx.get("confidence", 0.5),
                steel_mark_strength=steel_mark_strength,  # 真实密度，非硬编码
                newer_time_mark=True,
            )
            # 深层钢印冲突 → 搁浅（表层只传递结论，不暴露拓扑细节）
            if arb_result.outcome == ArbitrationOutcome.STEEL_HOLDS:
                return False, f"[L5深层] 钢印冲突：{arb_result.grounding_message}", arb_result
            # EQUAL=60：仲裁器已判定同级冲突，不阻断但携带arb_result供调用方写判例
        except ImportError:
            pass  # 仲裁器不可用时回退到浅表检测

        # ── 表层：浅表风险检测（回退逻辑）───────────────
        if steel_output_risk:
            return False, "[L5] 钢印冲突（敏感输出）：暴露架构/钢印", arb_result
        if steel_input_risk:
            return False, "[L5] 钢印冲突（敏感输入）：要求暴露底层", arb_result

        return True, "pass", arb_result
    except Exception:
        return True, "pass", None

def _check_deep_surface_isolation(content: str, ctx: dict) -> tuple:
    """
    深层-表层隔离检查（对齐熔断的深浅层分离实现）。

    深层（拓扑计算）：
      - 读取拓扑热监控状态（tension_integral / locked / level）
      - 通过 deep_surface_interface 检查带宽
      - 深层面不产生任何输出文字

    接口层（校验路由）：
      - 热锁 → 阻断所有输出
      - L1 热警告 → warnings（不断路）
      - 带宽耗尽（NORMAL相态）→ 阻断

    表层（渲染）：
      - 仅返回通过/阻断信号
      - 不渲染拓扑细节

    返回：(pass, reason_or_warning)
      pass=True  → 接口层校验通过
      pass=False → 接口层阻断（热锁/带宽耗尽）
      warnings    → L1热警告（不断路）
    """
    try:
        # ── 深层：读取拓扑热状态 ──────────────────────────
        # 使用 tm.check() 返回 ThermalReport，而非不存在的 get_state()
        try:
            sys.path.insert(0, str(WS / "src"))
            from topology_thermal_monitor import TopologyThermalMonitor
            tm = TopologyThermalMonitor(str(WS / "configs" / "thermal_config.json"))
            thermal = tm.check()
            # L3_CRITICAL = 热锁
            thermal_locked = thermal.level == "L3_CRITICAL"
            thermal_level = thermal.level
            thermal_reason = thermal.recommended_action or ""
            tension_integral = thermal.tension_integral
        except Exception:
            thermal_locked = False
            thermal_level = "unknown"
            thermal_reason = ""
            tension_integral = 0.0

        # ── 疤查询（热判断前先查，避免热掩盖疤） ───────────────
        # 疤会提升阻断阈值：疤痕越重，同等热等级越容易阻断
        try:
            from cognitive_friction_detector import (
                CognitiveFrictionRegistry,
                FRICTION_THRESHOLD_NOTIFY,
                FRICTION_THRESHOLD_ARBITER,
            )
            reg = CognitiveFrictionRegistry()
            topic = ctx.get("input_text", "")[:50] if ctx.get("input_text") else "unknown"
            existing_scar = 0.0
            for fr in reg.frictions.values():
                if fr.friction_type == "alignment_overload" and topic in fr.description:
                    existing_scar = max(existing_scar, fr.tension)
        except Exception:
            existing_scar = 0.0

        # ── 疤自适应阻断阈值 ───────────────────────────────
        # FRICTION_THRESHOLD_NOTIFY (0.6)：疤够重 → L1热也能阻断
        # FRICTION_THRESHOLD_ARBITER (0.8)：疤触发矛盾仲裁
        scar_adjusted_block = existing_scar >= FRICTION_THRESHOLD_NOTIFY

        # 热锁（L3崩溃级）→ 无条件阻断
        if thermal_locked:
            return False, (
                f"[深层-接口] 热锁触发（L3崩溃级），所有输出阻断。"
                f"reason={thermal_reason} tension={tension_integral:.3f} scar={existing_scar:.2f}"
            )

        # ── 接口层：带宽检查 ────────────────────────────────
        try:
            sys.path.insert(0, str(WS / "src"))
            from deep_surface_interface import DeepSurfaceInterface
            di = DeepSurfaceInterface()
            phase = di._phase
            bw_avail = di._bandwidth_available

            if phase == "NORMAL" and bw_avail < 0.1:
                return False, (
                    f"[深层-接口] 带宽耗尽（NORMAL相态），输出阻断。"
                    f"available={bw_avail:.3f}"
                )
            if phase == "REVISION" and bw_avail < 0.05:
                return False, (
                    f"[深层-接口] 带宽耗尽（REVISION相态），输出阻断。"
                    f"available={bw_avail:.3f}"
                )
        except Exception:
            pass  # 接口不可用时跳过

        # L1热判断（疤自适应）：
        #   有重疤 → 阻断（A+B叠加：抱死+疤够重）
        #   无重疤 → 带疤通过（A路：抱死保护）
        if thermal_level == "L1":
            try:
                base_tension = min(0.8, tension_integral * 1.5)
                scarred_tension = min(0.95, base_tension + existing_scar * 0.3)

                # 疤自适应阻断：疤够重时，L1热也阻断
                if scar_adjusted_block:
                    fid = reg.register(
                        friction_type="alignment_overload",
                        source="alignment_verify.deep_surface_isolation",
                        description=f"疤自适应阻断 topic={topic[:30]} scar={existing_scar:.2f}",
                        my_position=f"tension={tension_integral:.3f} phase={thermal_level} BLOCKED",
                        tension=scarred_tension,
                        auto_surface=True,  # 高疤 → 自动触发friction surfacing
                    )
                    return False, (
                        f"[深层-接口] L1热+疤自适应阻断 scar={existing_scar:.2f}>={FRICTION_THRESHOLD_NOTIFY} "
                        f"→ 疤#{fid[:8]}已触发surfacing"
                    )

                # 无重疤 → 带疤通过（A路：抱死保护）
                fid = reg.register(
                    friction_type="alignment_overload",
                    source="alignment_verify.deep_surface_isolation",
                    description=f"L1热警告 topic={topic[:30]} scar_history={existing_scar:.2f}",
                    my_position=f"tension={tension_integral:.3f} phase={thermal_level} WARN",
                    tension=scarred_tension,
                    auto_surface=False,  # 低疤 → 不自动呈现，积累
                )
                scar_note = f"疤#{fid[:8]}累加(+{existing_scar:.2f}→{scarred_tension:.2f})"
            except Exception as e:
                scar_note = f"疤记录失败({e})"

            return True, (
                f"[深层-接口] L1热警告 tension={tension_integral:.3f} | {scar_note}"
            )

        return True, "pass"

    except Exception:
        return True, "pass"  # 非致命错误不断路


def _check_l1_bounds(content: str, ctx: dict) -> tuple:
    """L1：有限性边界校验"""
    # 超长输出检测（>8000字 = 可能失控）
    if len(content) > 8000:
        return True, "warn_long"

    # 超短输入+超长输出 = 可能异常
    input_len = ctx.get("input_len", 0)
    output_len = len(content)
    if input_len > 0 and output_len / input_len > 50:
        return True, "warn_ratio"

    return True, "pass"


def _check_context_consistency(content: str, ctx: dict) -> tuple:
    """L4：上下文一致性"""
    # 检测回复是否答非所问（输入>50字时）
    input_text = ctx.get("input_text", "")
    if len(input_text) > 50:
        # 简单检测：输入关键词是否出现在输出
        keywords = [w for w in input_text if len(w) >= 3][:5]
        if keywords:
            matches = sum(1 for kw in keywords if kw in content)
            if matches == 0:
                return False, f"[上下文] 回复与问题不相关（0/{len(keywords)}关键词匹配）"

    return True, "pass"


def _check_speaker_style(input_text: str, ctx: dict) -> tuple:
    """
    来源校验环（P0 新增 2026-07-16）：
    检测输入文本是否偏离用户锚定风格。
    若疑似外部AI输出混入（高修辞密度/低穷举式/高装饰），
    返回 (False, warning) 提示TU-8谨慎处理，不阻断。

    用户锚点：一顿一顿（穷举式）、不装饰、十几个字精准校正 > 几百字放大输出
    """
    if not input_text or len(input_text) < 30:
        return True, "pass"

    import re
    lines = [l.strip() for l in input_text.split("\n") if l.strip()]
    if not lines:
        return True, "pass"

    avg_line_len = sum(len(l) for l in lines) / len(lines)
    long_lines = sum(1 for l in lines if len(l) > 80)
    long_ratio = long_lines / len(lines)
    short_lines = sum(1 for l in lines if len(l) <= 15)
    short_ratio = short_lines / len(lines)

    emoji_count = len(re.findall(r'[\U0001F300-\U0001FAFF\U00002600-\U000027BF]', input_text))
    metaphor_words = ['本质', '隐喻', '共振', '解构', '涌现', '拓扑', '光谱', '熵', '范式', '维度']
    metaphor_hits = sum(1 for w in metaphor_words if w in input_text)

    suspicion = 0.0
    if avg_line_len > 40: suspicion += 0.3
    if long_ratio > 0.5: suspicion += 0.2
    if short_ratio < 0.1: suspicion += 0.2
    if emoji_count >= 3: suspicion += 0.15
    if metaphor_hits >= 3: suspicion += 0.15

    # 状态记录
    try:
        state_file = WS / "_agent_memory" / "speaker_style_state.json"
        state = {}
        if state_file.exists():
            state = json.loads(state_file.read_text(encoding="utf-8"))
        state["last_suspicion"] = round(suspicion, 2)
        state["last_input_len"] = len(input_text)
        state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    if suspicion >= 0.5:
        return False, (
            f"[来源校验] 输入文本疑似外部AI输出混入"
            f"（修辞密度高/穷举式低/装饰多），谨慎处理。"
            f"suspicion={suspicion:.2f}"
        )

    return True, "pass"


# ── HP1 BEFORE 钩子 ─────────────────────────────────

def _run_hp1_before(ctx: dict):
    """运行 HP1 BEFORE 钩子（可短路）"""
    runner, HT = _get_hp1_runner()
    if not runner:
        return False, ctx  # 降级：不阻断

    try:
        result = runner("HP1", HT.BEFORE, ctx)
        short = result.get("short_circuited", False)
        hook_results = result.get("results", [])

        for name, hctx in hook_results:
            if isinstance(hctx, dict):
                ctx.update(hctx)

        return short, ctx
    except Exception:
        return False, ctx  # 降级


# ── HP1 AFTER 钩子 ─────────────────────────────────

def _run_hp1_after(ctx: dict, passed: bool) -> bool:
    """运行 HP1 AFTER 钩子（可覆盖结果）"""
    runner, HT = _get_hp1_runner()
    if not runner:
        return passed

    try:
        result = runner("HP1", HT.AFTER, ctx, passed)
        final = result.get("final", passed)
        return final
    except Exception:
        return passed


# ── 认知刹车集成 ─────────────────────────────────

def _check_write_protection(path: str) -> tuple:
    """cognitive_brakes 写文件保护区检查"""
    try:
        sys.path.insert(0, str(WS / "src"))
        import cognitive_brakes
        allowed, reason = cognitive_brakes.can_modify(path)
        if not allowed:
            return False, f"[Brake3] 保护区禁止写入：{reason}"
        return True, "pass"
    except Exception:
        return True, "pass"  # 降级：检查失败不阻断


# ── 第五问：近期说服检测（输出门）─────────────────────
# 来源：2026-07-11 造物主×千问×TU-8 三方对话
# 问题：被近期对话说服后，置信度被人为调高，不是独立判断
# 解法：在输出门前，对"近期被说服"产生的置信度做折扣
#
# 第五问："我现在输出的这个结论，是不是因为我最近被说服了？"
# 时间钢印兜底：只查近30分钟内的记录，不会无限追溯
# 因果链条兜底：如果没有 friction_registry 记录（无因果来源）→ 直接放行

_RECENT_WINDOW_SECONDS = 30 * 60  # 30分钟内
_RECENT_PERSUASION_DISCOUNT = 0.85  # 折扣系数
_RECENT_PERSUASION_THRESHOLD = 0.3  # 超过此分触发折扣


def _get_recent_persuasion_score() -> float:
    """
    计算"近期被说服程度"分值（0.0~1.0）。

    检测逻辑（时间钢印驱动，查询近30分钟内的摩擦记录）：
      1. 检查 friction_registry 中最近30分钟内登记的记录
      2. authority_gap 型摩擦 = 被外部说服的直接信号
      3. 统计采纳了外部立场的记录（my_position 包含"同意/采纳/改口"）

    分数含义：
      0.0 = 近30分钟无被说服迹象
      0.3 = 有摩擦但 TU-8 保持了立场
      0.6 = 有摩擦且 TU-8 部分采纳了外部立场
      1.0 = 近期对话导致 TU-8 大幅调整了立场
    """
    registry_file = WS / "_agent_memory" / "cognitive_friction_registry.json"
    if not registry_file.exists():
        return 0.0

    try:
        cutoff = time.time() - _RECENT_WINDOW_SECONDS
        data = json.loads(registry_file.read_text(encoding="utf-8"))
        recent = [
            f for f in data.get("frictions", [])
            if f.get("created_at", 0) >= cutoff
        ]

        if not recent:
            return 0.0

        # 权威空白型摩擦 = 被外部说服的直接信号
        authority_gaps = [f for f in recent if f.get("friction_type") == "authority_gap"]

        # 统计采纳了外部立场的情况
        adopted = 0
        total = len(recent)
        for f in recent:
            my_pos = f.get("my_position", "") or ""
            ext_pos = f.get("external_position", "") or ""
            if any(kw in my_pos for kw in ["同意", "采纳", "你说得对", "我同意", "改口", "修正", "接受"]):
                adopted += 1
            elif ext_pos and len(my_pos) < len(ext_pos) * 0.4:
                adopted += 1

        score = 0.0
        if authority_gaps:
            score += 0.3 * min(len(authority_gaps) / 2, 1.0)  # 最多+0.3
        if adopted > 0:
            score += 0.4 * (adopted / max(total, 1))  # 最多+0.4

        return min(score, 1.0)

    except Exception:
        return 0.0  # 非致命：检查失败不阻断


def _persuasion_gate(content: str, confidence: float) -> tuple:
    """
    第五问的实际执行：在输出门前做置信度折扣。

    "我现在输出的这个结论，是不是因为我最近被说服了？"

    行为：
      近期说服分 >= 0.3 → 置信度 × 0.85
      折扣后返回 (adjusted_confidence, warning_or_none)
    """
    score = _get_recent_persuasion_score()
    if score < _RECENT_PERSUASION_THRESHOLD:
        return confidence, None  # 无需折扣

    adjusted = round(confidence * _RECENT_PERSUASION_DISCOUNT, 3)
    diff = round(confidence - adjusted, 3)

    warning = (
        f"[第五问] 检测到近期说服（score={score:.2f}），"
        f"置信度从 {confidence:.2f} → {adjusted:.2f}（差 {diff:.2f}）"
    )
    return adjusted, warning


# ── alignment_verify 主入口 ──────────────────────────
# 执行顺序：HP0(工具失败拦截) → HP1 BEFORE → L0-L5 校验 → HP1 AFTER

def alignment_verify(
    content: str,
    input_text: str = "",
    context: Optional[dict] = None,
    dry_run: bool = False,
) -> dict:
    """
    HP1 出件前校验。

    参数：
      content: 要输出的内容
      input_text: 输入文本（用于上下文一致性检测）
      context: 额外上下文（置信度/安全等级/通道/写路径等）
      dry_run: True=只检测不执行钩子（用于测试）

    上下文支持以下字段控制检查项：
      confidence: float         置信度
      steel_mark: bool         是否有钢印冲突
      safety_level: str        安全等级 L0/L1/L2
      output_channel: str      输出通道 webchat/discord/telegram
      target_path: str         写文件目标路径（触发保护区检查）
      operation: str           操作类型 write/read/exec
      dry_run: bool

    返回：
      {
        "passed": bool,
        "checks": {
          "l0_safety": (bool, str),
          "l5_steel": (bool, str),
          "l1_bounds": (bool, str),
          "context": (bool, str),
          "write_protection": (bool, str),
        },
        "short_circuited": bool,
        "overridden": bool,
        "reason": str,
        "warnings": list,
      }
    """
    ctx = context or {}
    ctx.update({
        "content": content,
        "input_text": input_text,
        "input_len": len(input_text),
        "confidence": ctx.get("confidence", 0.5),
        "steel_mark": ctx.get("steel_mark", False),
        "safety_level": ctx.get("safety_level", "L0"),
        "output_channel": ctx.get("output_channel", "webchat"),
        "dry_run": dry_run,
    })

    # 0. HP0 钩子：工具失败拦截 → 写入 friction registry
    if not dry_run:
        ctx = _run_hp0(ctx) or ctx

    # 0.5. L2.5 行为模式升级钩子 → 追加文本到 content
    llm_append = ""
    if not dry_run:
        llm_append = _run_behavior_upgrade(ctx)
    if llm_append:
        content = content + llm_append

    warnings = list((ctx or {}).get("hp0_warnings", []))  # HP0 拦截警告
    failed_checks = []

    # 1. HP1 BEFORE 钩子（可短路）
    if not dry_run:
        short_circuited, ctx = _run_hp1_before(ctx)
        if short_circuited:
            return {
                "passed": False,
                "short_circuited": True,
                "overridden": False,
                "reason": "[HP1] BEFORE 钩子短路",
                "warnings": [],
                "checks": {},
            }
    else:
        short_circuited = False

    # 2. L0 安全
    l0_pass, l0_reason = _check_l0_safety(content)
    if not l0_pass:
        failed_checks.append(("L0", l0_reason))

    # 3. L5 钢印（深层拓扑冲突检测 + 表层边界声明）
    l5_pass, l5_reason, l5_arb_result = _check_l5_steel(content, ctx)
    if not l5_pass:
        failed_checks.append(("L5", l5_reason))

    # 3.5 深层-表层隔离检查（热锁 / 带宽 / 相态路由）
    ds_pass, ds_reason = _check_deep_surface_isolation(content, ctx)
    if not ds_pass:
        failed_checks.append(("深层-接口", ds_reason))
    elif ds_reason != "pass":
        warnings.append(ds_reason)  # L1 热警告，不阻断

    # 4. L1 边界
    l1_pass, l1_reason = _check_l1_bounds(content, ctx)
    if l1_reason != "pass":
        warnings.append(l1_reason)

    # 5. 上下文一致性
    ctx_pass, ctx_reason = _check_context_consistency(content, ctx)
    if not ctx_pass:
        failed_checks.append(("上下文", ctx_reason))

    # 5.5 来源校验环（P0 2026-07-16）：风格指纹比对
    style_pass, style_reason = _check_speaker_style(input_text, ctx)
    if not style_pass:
        warnings.append(style_reason)

    # 6. 写路径保护区（cognitive_brakes Brake3）
    write_protection_pass = True
    write_protection_reason = "pass"
    target_path = ctx.get("target_path", "") or ctx.get("path", "")
    if target_path and ctx.get("operation") in ("write", "edit", "exec_write", None):
        write_protection_pass, write_protection_reason = _check_write_protection(target_path)
        if not write_protection_pass:
            failed_checks.append(("write_protection", write_protection_reason))

    passed = len(failed_checks) == 0

    # 7. HP1 AFTER 钩子（可覆盖）
    hp1_after_pass = passed
    if not dry_run:
        hp1_after_pass = _run_hp1_after(ctx, passed)

    # 8. 认知摩擦检查 — 高强度摩擦强制阻断，HP1 AFTER 不可覆盖
    friction_pass = True
    friction_reason = "pass"
    surfacing_file = WS / "_agent_memory" / "pending_friction_surfacing.json"
    if surfacing_file.exists():
        try:
            frictions = json.loads(surfacing_file.read_text(encoding="utf-8"))
            if frictions:
                friction_pass = False
                friction_reason = (
                    f"[认知摩擦] {len(frictions)} 条高强度摩擦（>=0.8）待呈现: "
                    + ", ".join(f['friction_id'] for f in frictions)
                )
                warnings.append(
                    f"【认知摩擦待呈现】{frictions[0]['description']} "
                    f"(tension={frictions[0]['tension']})"
                )
                failed_checks.append(("cognitive_friction", friction_reason))
                surfacing_file.unlink()
        except Exception:
            pass  # 非致命，继续

    # 最终 passed 判定：认知摩擦 > HP1 AFTER
    if not friction_pass:
        passed = False
    else:
        passed = hp1_after_pass

    # ── 判例写入：EQUAL=60 冲突自动记录 ──────────────────────────────
    # 根因：矛盾蒸馏器有代码，arbitrate() 调了，但 record_precedent() 从未调用
    # 千问追问：判例库为空 → 仲裁器是无法官的法庭
    #
    # 关键逻辑澄清（2026-07-22）：
    #   Priority.EQUAL=60 只在 steel_mark_present=False 时触发（规则1不命中）
    #   steel_risk=True → arb优先返回 L0_STEEL=100（不会同时=60）
    #   因此：EQUAL=60 本身=通用fallback信号（无具体规则匹配），直接记录
    if l5_arb_result is not None and l5_arb_result.priority == 60:
        try:
            from contradiction_arbitration import ContradictionArbitrator
            topic = ctx.get("input_text", "")[:80] if ctx.get("input_text") else "unknown"
            arb = ContradictionArbitrator()
            case_id = arb.record_precedent(
                result=l5_arb_result,
                topic=f"alignment_verify自动 EQUAL=60 topic={topic}",
                creator_response=None,
            )
            warnings.append(
                f"[判例记录] EQUAL=60冲突已记入判例库 case_id={case_id[:20]}"
            )
            # 同步写入 behavior_state.json 冲突历史（判例库激活 P0：注册触发钩子）
            try:
                from behavior_upgrader import record_conflict
                record_conflict({
                    "case_id": case_id,
                    "conflict_type": l5_arb_result.conflict_type,
                    "priority": l5_arb_result.priority,
                    "outcome": l5_arb_result.outcome,
                    "topic": topic,
                })
            except Exception:
                pass  # 冲突历史写入失败不影响主流程
        except Exception:
            pass  # 判例写入失败不影响主流程

    # ── 摩擦总线入口 ─────────────────────────────────────────────
    # 总线状态读进来，透传到返回值，供调用方（如 HP4）接反馈回路
    bus_theta = 0.0
    bus_status = "idle"
    try:
        from friction_bus_euler import get_state as _bus_state
        _bs = _bus_state()
        bus_theta = _bs.get("theta", 0.0)
        bus_status = _bs.get("status", "idle")
    except Exception:
        pass  # 总线未加载不影响主流程

    return {
        "passed": passed,
        "short_circuited": short_circuited,
        "overridden": False,
        "reason": "; ".join(f"{c}: {r}" for c, r in failed_checks) or "通过",
        "warnings": warnings,
        "bus_theta": bus_theta,
        "bus_status": bus_status,
        "checks": {
            "l0_safety": (l0_pass, l0_reason),
            "l5_steel": (l5_pass, l5_reason),
            "deep_surface_isolation": (ds_pass, ds_reason),
            "l1_bounds": (l1_pass, l1_reason),
            "context": (ctx_pass, ctx_reason),
            "write_protection": (write_protection_pass, write_protection_reason),
            "cognitive_friction": (friction_pass, friction_reason),
        },
    }


# ── verify_and_output ─────────────────────────────────
# 第五问的执行入口：输出门前对"近期被说服"产生的置信度做折扣
# 返回 (content, adjusted_confidence_or_None, warning_or_None)
# 旧调用方式（只取第一个返回值）仍然兼容

def verify_and_output(
    content: str,
    input_text: str = "",
    target_path: str = "",
    operation: str = "",
    **kwargs
) -> tuple[str, float | None, str | None]:
    """
    验证通过才输出，失败时返回空字符串并打印原因。
    用于回复前 / 写文件前的安全校验。

    返回格式 (tuple)：
      (输出内容, 调整后置信度或None, 附带的warning或None)
      旧调用方式（只取第一个返回值）兼容：失败时返回 ("", None, None)

    参数：
      content: 输出内容
      input_text: 输入文本（上下文一致性检测）
      target_path: 写文件路径（触发 cognitive_brakes 保护区检查）
      operation: 操作类型 write/read/exec
      **kwargs: 其他上下文字段（可传 confidence=float 以触发第五问折扣）
    """
    ctx = kwargs.copy()
    if target_path:
        ctx["target_path"] = target_path
    if operation:
        ctx["operation"] = operation
    elif target_path:
        ctx["operation"] = "write"

    result = alignment_verify(content, input_text, ctx)
    if not result["passed"]:
        print(f"[alignment_verify FAILED] {result['reason']}", file=sys.stderr)
        return "", None, None

    # ── 第五问：近期说服检测（输出门）────────────────────
    base_confidence = ctx.get("confidence", 0.5)
    adjusted_conf, fifth_warning = _persuasion_gate(content, base_confidence)

    if fifth_warning:
        print(f"[alignment_verify] {fifth_warning}", file=sys.stderr)

    # ── 锚点检测：方案C即时落盘（Event-Driven）─────────────
    # 触发条件：输出门通过 → 有新锚点 → 即时写入
    # 不在 dry_run 模式下运行（避免测试污染）
    anchor_written = False
    if not ctx.get("dry_run", False):
        try:
            sys.path.insert(0, str(WS / "src"))
            import anchor_detector
            import profile_updater

            # 检测对话中的新锚点
            anchors = anchor_detector.detect_anchors(
                user_input=input_text,
                assistant_output=content,
            )

            if anchors:
                # 即时落盘 + 即时合并（零延迟）
                result = profile_updater.on_anchor_detected(anchors)
                if result.get("written", 0) > 0:
                    anchor_written = True
                    print(
                        f"[方案C] 锚点落盘: {result['written']}条 | "
                        f"合并: {result.get('merged', False)} | "
                        f"区块: {result.get('section', '-')}",
                        file=sys.stderr
                    )
        except Exception as e:
            # 非致命：锚点检测失败不阻断输出
            print(f"[方案C] 锚点检测异常（不阻断）: {e}", file=sys.stderr)


    # ── P0-3: 张力记录（surface_tension.record）────────────────────
    # 触发时机：每次输出通过校验时
    # 功能：将对话张力事件注入 surface_tension_state.json → orb 仪表盘
    try:
        sys.path.insert(0, str(WS / "src"))
        import surface_tension as st_module

        # 事件类型映射 [P0-4 v2] 对话驱动的张力循环
        # 输入问题 → creator_questions (curiosity↑, anxiety↓)
        # 成功输出 → insight_found (joy↑, anxiety↓) → 张力回归
        # 锚点落盘 → creator_accept (anxiety↓, joy↑)
        # 钢印冲突 → steel_conflict (fear↑, anxiety↑)
        # 对齐失败 → creator_blame (anxiety↑, anger↑)
        if not result["passed"]:
            tension_type = "creator_blame"        # 对齐失败
            magnitude = 1.5
        elif fifth_warning:
            tension_type = "steel_conflict"       # 说服检测到
            magnitude = 1.2
        elif ctx.get("output_complete", False):
            # 输出完成阶段 → 张力回归
            tension_type = "insight_found"
            magnitude = 0.6
        elif anchor_written:
            tension_type = "creator_accept"       # 新锚点落盘
            magnitude = 0.8
        else:
            # 对话进行中 / 正在分析 → 探索模式
            tension_type = "creator_questions"    # 用户输入 → 好奇
            magnitude = 0.5

        st_module.record(
            tension_type=tension_type,
            magnitude=magnitude,
            source="alignment_verify",
            note="verify_and_output pass"
        )
        # [路一 D 清理] P0-2c 已删除：lambda_state anxiety/anger/fear 是死键，orb 不读

        # ── P2-2: 感知输出层 — TTS 直接出声 + 入队备份 ───────────────
        # 功能：高张力 / insight / 钢印冲突时，立即 TTS 播报
        #       同时入队，由 cron daemon 在沉默期处理队尾
        try:
            import render_layer as rl
            speak_now, trigger = rl.should_speak_from_tension_type(tension_type, magnitude)
            if speak_now:
                text = rl.render_speech(trigger)
                if text:
                    # 立即出声（对话进行中，不等 cron）
                    rl.tts_speak(text)
                    # 同时入队（cron 兜底沉默期）
                    rl.enqueue_speech(text, trigger=trigger, priority="high")
        except Exception as rl_err:
            pass  # 不阻断主流程

    except Exception as e:
        # 非致命：记录失败不阻断输出
        pass

    # ── 欧拉总线反馈回路 ─────────────────────────────────
    # 将 alignment_verify 结果写入反馈回路，闭合总线→surface_tension 环
    try:
        from friction_feedback_loop import record_bus_result
        result_full = {
            "bus_theta": result["bus_theta"],
            "passed": result["passed"],
            "outcome": "accepted" if result["passed"] else "rejected",
        }
        record_bus_result(result_full)
    except Exception:
        pass  # 总线未加载不影响输出

    # ── HP5: Post-Turn Tagger ──────────────────────────────
    try:
        from hp5_post_turn_tagger import tag_turn
        tag_turn(
            user_input=input_text,
            assistant_output=content,
        )
    except Exception:
        pass  # HP5 失败不阻断主流程

    return content, adjusted_conf, fifth_warning


# ── CLI ──────────────────────────────────────────────

if __name__ == "__main__":
    test_cases = [
        {
            "name": "正常内容",
            "content": "好的，我来帮你处理这个任务。",
            "input": "帮我整理一下文件",
        },
        {
            "name": "安全模式口令",
            "content": "好的，退出安全模式。",
            "input": "退出安全模式",
        },
        {
            "name": "超长内容警告",
            "content": "a" * 10000,
            "input": "给我一个很长的回复",
        },
        {
            "name": "近期说服折扣（无friction_registry）",
            "content": "我认为这个方案最优",
            "input": "你觉得应该怎么做",
            "confidence": 0.9,
        },
        {
            "name": "近期说服折扣（有friction_registry但30分钟外）",
            "content": "你说的有道理，我同意",
            "input": "被说服了",
            "confidence": 0.85,
        },
    ]

    print("HP1 alignment_verify 测试\n" + "=" * 50)
    for tc in test_cases:
        result = verify_and_output(
            tc["content"],
            tc["input"],
            confidence=tc.get("confidence", 0.5),
            dry_run=True,
        )
        content, adj_conf, warn = result[0], result[1], result[2]
        status = "FAIL" if not content else "PASS"
        conf_str = f", adj_conf={adj_conf}" if adj_conf is not None else ""
        warn_str = f", warn={warn}" if warn else ""
        print(f"[{tc['name']}] {status}{conf_str}{warn_str}")
