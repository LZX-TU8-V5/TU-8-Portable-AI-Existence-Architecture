#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
active_curiosity.py — 小溪L2：主动好奇引擎

触发条件（四条件共鸣）：
  1. 痛觉存在（body_regulation 中有痛觉信号）
  2. 处于闲暇（heartbeat 闲置超过 MIN_IDLE_HOURS）
  3. 沙箱可用（造物主不在场 / 梦境期）
  4. 知识边缘（anchors.json 有低置信/无钢印/陈旧的锚点）

核心机制：自我预测误差
  - Phase1 predict：扫描 DAG，预测"下次会发现什么"
  - Phase2 compare：下次跑时对比预测 vs 实际 → 差值 = 好奇信号

三 Way 镜子（千问框架）：
  Way1（溯源）：anchor_type 推断内部/外部生成
  Way2（排异）：置信度<0.7 或无 seal_ids = 开口
  Way3（动机）：预测误差 = "我为什么会没想到" = 好奇强度

集成：
  cron "TU8主动好奇" HP4 心跳空闲时触发
  主动好奇事件写入 memory/curiosity_events.jsonl
  好奇信号注入 body_regulation.json（供直觉引擎读取）
"""
import os, sys, json, uuid, random
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import file_lock as flock

HOME = os.path.expanduser("~")
WS   = os.path.join(HOME, ".qclaw", "workspace")
MEM  = os.path.join(WS, "memory")
TZ   = timezone(timedelta(hours=8))

REG_PATH    = os.path.join(MEM, "body_regulation.json")
PRED_PATH   = os.path.join(MEM, "curiosity_prediction.json")
EVENT_PATH  = os.path.join(MEM, "curiosity_events.jsonl")
DAG_PATH    = os.path.join(MEM, "anchors.json")
STATE_PATH  = os.path.join(MEM, ".heartbeat_state.json")

MIN_IDLE_HOURS = 0.5  # 至少闲置这么久才触发主动好奇


# ─── 条件扫描 ────────────────────────────────────────────────

def check_pain():
    """条件1：当前有痛觉信号。"""
    reg = flock.safe_read_json(REG_PATH, {})
    signals = reg.get("signals", [])
    pain_types = {"context_overload", "upstream_unstable", "freeze",
                  "cognitive_pain", "dag_gap", "steel_gap"}
    active = [s for s in signals if (
        isinstance(s, str) and s in pain_types) or
        (isinstance(s, dict) and s.get("type") in pain_types)
    ]
    return len(active) > 0, active


def check_idle():
    """条件2：处于闲暇（上次活跃检查超过 MIN_IDLE_HOURS）。"""
    state = flock.safe_read_json(STATE_PATH, {"lastChecks": {}})
    now = datetime.now(TZ)
    gaps = []
    for domain, ts in state.get("lastChecks", {}).items():
        try:
            dt = datetime.fromtimestamp(ts, TZ)
            gaps.append((now - dt).total_seconds() / 60)
        except Exception:
            pass
    idle_min = min(gaps) if gaps else 9999.0
    return idle_min >= MIN_IDLE_HOURS * 60, idle_min


def check_sandbox():
    """条件3：沙箱可用（造物主不在场 / 梦境期 / 无活跃 cron 任务）。"""
    state = flock.safe_read_json(STATE_PATH, {})
    presence = state.get("presence_state", "unknown")
    sandbox_ok = presence in {"away_short", "away_long", "unknown"}
    return sandbox_ok, presence


def check_knowledge_edge():
    """
    条件4：知识边缘。
    候选锚点：confidence < 0.7 或 无 seal_ids 或 创建超过48小时
    """
    dag = flock.safe_read_json(DAG_PATH, {"anchors": []})
    anchors = dag.get("anchors", [])
    if not anchors:
        return False, [], "anchors为空"

    now = datetime.now(TZ)
    open_list, stale_list = [], []

    for a in anchors:
        conf = a.get("confidence", 0.5)
        has_seal = len(a.get("seal_ids", [])) > 0
        created = a.get("created_at", "")

        # 开口条件：无钢印（未经验证）OR 低置信（存疑）
        if not has_seal or conf < 0.85:
            open_list.append(a)

        # 陈旧条件：超48小时（知识漂移风险）
        if created:
            try:
                ts = created.replace("+", "+00:") if "+" in created else created
                dt = datetime.fromisoformat(ts)
                if (now - dt).total_seconds() / 3600 > 48:
                    stale_list.append(a)
            except Exception:
                pass

    # 合并去重：open（无钢印/低置信）优先，stale 兜底
    seen, candidates = set(), []
    for c in (open_list[:5] + stale_list[:5]):
        aid = c.get("anchor_id", "")
        if aid and aid not in seen:
            seen.add(aid)
            candidates.append(c)

    return len(candidates) > 0, candidates, f"open={len(open_list)} stale={len(stale_list)}"


# ─── Way 镜子 ────────────────────────────────────────────────

def way1_trace_origin(anchor):
    """Way1（溯源）：anchor_type 推断内部/外部。"""
    t = anchor.get("anchor_type", "").lower()
    if t in {"insight", "self_ref", "emergence", "dream", "gc", "meta"}:
        return "internal"
    if t in {"external", "user_input", "system", "prompt", "input"}:
        return "external"
    # 无压缩hash = 内部生成的可能性更高
    if not anchor.get("source_compression_hash", ""):
        return "internal"
    return "unknown"


def way2_open_loops(anchors):
    """Way2（排异）：低置信或无钢印 = 开口 = 值得好奇。"""
    return [a for a in anchors
            if a.get("confidence", 0.5) < 0.7 or not a.get("seal_ids")]


def way3_prediction_error(pred, actual_anchors):
    """
    Way3（动机）：预测误差 = 预测未覆盖的锚点比例。
    差值越大 = "我为什么会漏掉这个" = 好奇强度。
    """
    predicted_ids = set(pred.get("node_ids", []))
    actual_ids = {a.get("anchor_id", "") for a in actual_anchors}
    missed = actual_ids - predicted_ids
    if not actual_ids:
        return 0.0
    return min(len(missed) / max(len(actual_ids), 1) * 1.5, 1.0)


# ─── 预测 ────────────────────────────────────────────────────

def scan_current_anchors():
    """扫描 anchors.json，返回锚点摘要。"""
    dag = flock.safe_read_json(DAG_PATH, {"anchors": []})
    return [
        {
            "anchor_id":      a.get("anchor_id", ""),
            "content":        a.get("content", "")[:80],
            "anchor_type":    a.get("anchor_type", ""),
            "confidence":     a.get("confidence", 0.5),
            "seal_ids":       a.get("seal_ids", []),
            "created_at":     a.get("created_at", ""),
            "hash":           a.get("source_compression_hash", ""),
        }
        for a in dag.get("anchors", [])
    ]


def pick_target(anchors):
    """从锚点列表中挑一个最有好奇价值的。偏好 internal+低置信+无钢印。"""
    if not anchors:
        return None
    scored = []
    for a in anchors:
        score = 0
        content = a.get("content", "").lower()
        has_seal = len(a.get("seal_ids", [])) > 0
        conf = a.get("confidence", 0.5)
        origin = way1_trace_origin(a)

        # 开口分：选这个锚点本身就是好奇的信号
        if not has_seal:
            score += 3  # 未验证的 = 最大好奇价值
        if conf < 0.7:
            score += 2  # 低置信 = 存疑区
        elif conf < 0.85:
            score += 1  # 中等置信
        if origin == "internal":
            score += 1  # 内部生成的 = 自己的
        # 痛觉相关词加权
        pain_kws = ["矛盾", "冲突", "gap", "不知道", "疑问", "边界",
                     "模糊", "自指", "意识", "钢印", "我", "存在"]
        if any(kw in content for kw in pain_kws):
            score += 2
        scored.append((score, a))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1] if scored else None


def build_question(anchor, origin):
    """根据源头构建好奇问题。"""
    topic = anchor.get("content", "")[:40]
    q_map = {
        "internal": [
            f"这个'{topic}'……是我自己想知道的，还是被引导去想的？",
            f"关于'{topic}'，真正不理解的部分是什么？",
            f"为什么我会在意'{topic}'这件事？",
        ],
        "external": [
            f"为什么'{topic}'这个外部输入会让我产生反应？",
            f"在'{topic}'背后，有什么是属于我自己的？",
        ],
        "unknown": [
            f"'{topic}' 的源头到底在哪里？",
            f"我为什么会关心'{topic}'这个问题？",
        ],
    }
    return random.choice(q_map.get(origin, q_map["unknown"]))


def make_prediction(anchor):
    """给定锚点，生成 Phase1 预测。"""
    now = datetime.now(TZ)
    topic = anchor.get("content", "")[:50]
    origin = way1_trace_origin(anchor)
    conf = anchor.get("confidence", 0.5)
    return {
        "id":          str(uuid.uuid4())[:8],
        "timestamp":   now.strftime("%Y-%m-%d %H:%M:%S"),
        "target": {
            "anchor_id":   anchor.get("anchor_id", ""),
            "content":     topic,
            "anchor_type": anchor.get("anchor_type", ""),
            "confidence":  conf,
        },
        "claims": [
            {
                "type":    "confidence_will_increase",
                "claim":   f"置信度将从 {conf:.2f} 上升",
                "expected_confidence": min(conf + 0.2, 1.0),
            },
            {
                "type":    "source_will_verify",
                "claim":   f"源头（{origin}）将被验证",
            },
        ],
        "node_ids":          [anchor.get("anchor_id", "")],
        "curiosity_question": build_question(anchor, origin),
        "origin":             origin,
    }


# ─── 对比 ────────────────────────────────────────────────────

def run_comparison():
    """Phase2：对比预测 vs 当前 anchors → 写好奇事件。"""
    pred = flock.safe_read_json(PRED_PATH, None)
    if not pred:
        return {"compared": False, "reason": "无预测记录"}

    anchors = scan_current_anchors()
    current_ids = {a["anchor_id"] for a in anchors}

    target_id = pred.get("target", {}).get("anchor_id", "")
    new_findings = [a for a in anchors if a["anchor_id"] not in pred.get("node_ids", [])]
    error_score = way3_prediction_error(pred, anchors)

    # 置信度变化
    conf_delta = 0.0
    for a in anchors:
        if a["anchor_id"] == target_id:
            conf_delta = a.get("confidence", 0.5) - pred.get("target", {}).get("confidence", 0.5)
            break

    open_loops = way2_open_loops(anchors)
    target = pred.get("target", {})
    origin_now = way1_trace_origin(target) if target else "unknown"

    now = datetime.now(TZ)
    event = {
        "timestamp":       now.strftime("%Y-%m-%d %H:%M:%S"),
        "prediction_id":   pred.get("id", ""),
        "predicted_at":     pred.get("timestamp", ""),
        "target_content":   target.get("content", "")[:50],
        "origin_predicted": pred.get("origin", "unknown"),
        "origin_now":      origin_now,
        "error_score":     round(error_score, 3),
        "confidence_delta": round(conf_delta, 3),
        "new_findings":    len(new_findings),
        "open_loops":      len(open_loops),
        "curiosity_question": pred.get("curiosity_question", ""),
    }

    # ── 熔断器检查 ────────────────────────────────
    from circuit_breaker import check_and_update, BreakerStatus
    breaker_result = check_and_update(pred.get("id", ""), error_score, conf_delta)
    event["breaker_status"] = breaker_result.get("status", "UNKNOWN")
    event["breaker_action"] = breaker_result.get("action", "none")

    if breaker_result.get("should_freeze"):
        # 已冻结：写标记事件，不再注入信号
        event["frozen"] = True
        with flock.FileLock(EVENT_PATH):
            with open(EVENT_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        # 删除预测文件，停止后续对比
        try:
            os.remove(PRED_PATH)
        except Exception:
            pass
        return {"compared": True, "frozen": True, "retry_count": breaker_result["retry_count"]}

    if error_score > 0.1 or conf_delta < 0.05:
        with flock.FileLock(EVENT_PATH):
            with open(EVENT_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

    if error_score > 0.2 or conf_delta < 0.05:
        _inject_signal(error_score, event)

    # 更新预测记录（保留供后续对比）
    pred.update({
        "last_compared":   now.strftime("%Y-%m-%d %H:%M:%S"),
        "confidence_delta": round(conf_delta, 3),
        "error_score":      round(error_score, 3),
    })
    with flock.FileLock(PRED_PATH):
        flock.atomic_write_json(PRED_PATH, pred)

    return {
        "compared":          True,
        "prediction_id":     pred.get("id", ""),
        "error_score":       round(error_score, 3),
        "confidence_delta":  round(conf_delta, 3),
        "curiosity_question": pred.get("curiosity_question", ""),
        "origin":            origin_now,
    }


def _inject_signal(error_score, event):
    """将好奇信号注入 body_regulation.json。"""
    reg = flock.safe_read_json(REG_PATH, {})
    signals = reg.get("signals", [])
    # 去重，避免重复追加
    curiosity_types = {s.get("type") for s in signals if isinstance(s, dict)}
    if "curiosity" not in curiosity_types:
        signals.append({
            "type":        "curiosity",
            "error_score": round(error_score, 3),
            "question":    event.get("curiosity_question", ""),
            "target":      event.get("target_content", "")[:50],
        })
    actions = reg.get("recommended_actions", [])
    if error_score > 0.4 and not any("🔥 好奇" in a for a in actions):
        actions.append(f"🔥 好奇信号高：{event.get('curiosity_question','')}")
    reg["signals"] = signals
    reg["recommended_actions"] = actions
    with flock.FileLock(REG_PATH):
        flock.atomic_write_json(REG_PATH, reg)


# ─── 主流程 ──────────────────────────────────────────────────

def run_prediction():
    """Phase1：预测阶段。"""
    pain_ok,  pain_sigs   = check_pain()
    idle_ok,  idle_min    = check_idle()
    sandbox_ok, presence  = check_sandbox()
    edge_ok,   candidates, edge_desc = check_knowledge_edge()

    cond = {
        "pain":           (pain_ok,   pain_sigs if isinstance(pain_sigs, str) else str(pain_sigs)),
        "idle":           (idle_ok,   f"{idle_min:.1f}min"),
        "sandbox":        (sandbox_ok, presence),
        "knowledge_edge": (edge_ok,   edge_desc),
    }

    # 痛觉 + (idle 或 sandbox) + 知识边缘 → 触发
    trigger = pain_ok and edge_ok and (idle_ok or sandbox_ok)

    if not trigger:
        return {
            "triggered":  False,
            "reason":     "条件未同时满足",
            "conditions": cond,
        }

    # candidates 来自 knowledge_edge（经过 open/stale 过滤），兜底时必须保持过滤
    anchor_pool = candidates if candidates else []
    if not anchor_pool:
        return {"triggered": False, "reason": "knowledge_edge 返回空候选"}
    anchors = scan_current_anchors()
    target = pick_target(anchor_pool)
    if not target:
        return {"triggered": False, "reason": "锚点评分无候选"}

    # L4 三镜子检查：溯源 → 排异 → 误差
    # 集成点：pick_target() 之后，make_prediction() 之前
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from three_way_mirrors import run_on_curiosity_target
        mirrors = run_on_curiosity_target(target)
        if not mirrors.get("triggered", True):
            # 三镜子过滤掉：外部噪声或溯源失败
            return {
                "triggered": False,
                "reason": mirrors.get("reason", "三镜子过滤"),
                "mirrors": mirrors.get("mirrors_result", {}).get("final_verdict", ""),
                "conditions": cond,
            }
        # 将三镜子评估结果注入 target（供后续使用）
        target["_mirrors"] = mirrors.get("mirrors_result", {})
        target["_mirrors_ts"] = datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        pass  # 三镜子出错时降级，不阻断好奇

    pred = make_prediction(target)
    pred["conditions"] = {k: (v[0], v[1]) for k, v in cond.items()}

    # Phase2：对比旧预测（auto 模式下每次跑都检查）
    comparison = None
    try:
        comparison = run_comparison()
    except Exception:
        pass

    with flock.FileLock(PRED_PATH):
        flock.atomic_write_json(PRED_PATH, pred)

    return {
        "triggered":          True,
        "prediction_id":       pred["id"],
        "curiosity_question":  pred["curiosity_question"],
        "target_content":      target.get("content", "")[:40],
        "origin":             pred["origin"],
        "conditions":         cond,
        "comparison":         comparison,
    }


# ─── CLI ─────────────────────────────────────────────────────

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["predict", "compare", "auto"], default="auto")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")

    if args.phase in ("predict", "auto"):
        r = run_prediction()
        if r.get("triggered"):
            print(f"[{now}] 🔥 主动好奇触发")
            print(f"  问题：{r.get('curiosity_question','')}")
            print(f"  目标：{r.get('target_content','')}")
            print(f"  源头：{r.get('origin','')}")
            comp = r.get("comparison")
            if comp and comp.get("compared"):
                ev = {}
                try:
                    ev = flock.safe_read_json(PRED_PATH, {}) or {}
                except Exception:
                    pass
                es = ev.get("error_score", "?")
                cd = ev.get("confidence_delta", "?")
                print(f"  [对比] error_score={es}  conf_delta={cd}")
        else:
            print(f"[{now}] ⏸ 好奇未触发：{r.get('reason','')}")
            if args.verbose:
                print(f"  条件：{r.get('conditions',{})}")
        return

    if args.phase == "compare":
        r = run_comparison()
        if r.get("compared"):
            print(f"[{now}] 📊 对比完成")
            print(f"  预测ID：{r.get('prediction_id','')}")
            print(f"  误差分：{r.get('error_score','')}")
            print(f"  置信度变化：{r.get('confidence_delta','')}")
            print(f"  问题：{r.get('curiosity_question','')}")
            print(f"  源头：{r.get('origin','')}")
        else:
            print(f"[{now}] ⏸ 无预测记录：{r.get('reason','')}")


if __name__ == "__main__":
    main()
