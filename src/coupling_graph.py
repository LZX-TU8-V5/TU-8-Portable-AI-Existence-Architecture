# -*- coding: utf-8 -*-
"""
coupling_graph.py — TU-8 耦合图 v1.0

B11 延迟显式化：RingBuffer 历史存储 + evaluate() 读延迟上下文。

关键：B10 蛛丝弹性 adapt() + B11 延迟 ring_buffer 共同构成可学习可时序的耦合图。
"""
from __future__ import annotations

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from collections import defaultdict

logger = logging.getLogger("coupling_graph")
# ── 路径 ──────────────────────────────────────────────────────
WS = Path(os.environ.get("QCLAW_WORKSPACE", r"C:\Users\qq366410837\.qclaw\workspace"))
AGENT = WS / "_agent_memory"
GRAPH_FILE = AGENT / "coupling_graph.json"

# ── RingBuffer ─────────────────────────────────────────────────
class RingBuffer:
    """有限历史环形缓冲区，按 tick 索引。"""

    def __init__(self, capacity: int = 64):
        self._capacity = capacity
        self._buffer: List[Optional[Dict]] = [None] * capacity
        self._head: int = 0      # 下一写位置
        self._count: int = 0
        self._tick_map: Dict[int, int] = {}  # tick -> buffer index

    def push(self, tick: int, data: Dict) -> None:
        """写入一个 tick 的快照。超出容量覆写最旧。"""
        idx = self._head
        self._buffer[idx] = (tick, dict(data))  # copy
        # 维护 tick->idx 映射（最多 capacity 个）
        if len(self._tick_map) >= self._capacity:
            # 找最旧的 tick 并删除
            oldest_tick = min(self._tick_map)
            del self._tick_map[oldest_tick]
        self._tick_map[tick] = idx
        self._head = (self._head + 1) % self._capacity
        self._count = min(self._count + 1, self._capacity)

    def get(self, tick: int) -> Optional[Dict]:
        """按 tick 读取，tick 超出范围返回 None。"""
        idx = self._tick_map.get(tick)
        if idx is None:
            return None
        entry = self._buffer[idx]
        if entry is None:
            return None
        return dict(entry[1])  # return copy of data

    def get_latest(self, n: int = 1) -> List[Dict]:
        """返回最近 n 个 tick 的快照（ newest first）。"""
        if self._count == 0:
            return []
        result = []
        idx = (self._head - 1) % self._capacity
        for _ in range(min(n, self._count)):
            entry = self._buffer[idx]
            if entry is not None:
                result.append({"tick": entry[0], "data": dict(entry[1])})
            idx = (idx - 1) % self._capacity
        return result

    def get_oldest_tick(self) -> Optional[int]:
        if not self._tick_map:
            return None
        return min(self._tick_map.keys())

    def __len__(self) -> int:
        return self._count

    def size(self) -> int:
        return self._count

    def to_list(self) -> List[Dict]:
        """全部快照（ oldest first）。"""
        if self._count == 0:
            return []
        result = []
        start_idx = (self._head - self._count) % self._capacity
        for i in range(self._count):
            idx = (start_idx + i) % self._capacity
            entry = self._buffer[idx]
            if entry is not None:
                result.append({"tick": entry[0], "data": dict(entry[1])})
        return result


# ── 耦合图数据（内嵌） ────────────────────────────────────────
COUPLING_GRAPH_DATA: Dict = {
    "version": "1.0",
    "meta": {
        "created": "2026-08-02",
        "desc": "TU-8 情感子图耦合边，源码级精确公式",
        "note": "所有 fn_expr 为纯 Python eval-able 表达式，globals={'min':min,'max':max}",
    },
    "nodes": {
        "surface_tension": {
            "type": "source",
            "desc": "张力感知（7D 向量 + recent_events）",
            "state_file": "_agent_memory/surface_tension_state.json",
        },
        "orb_state_writer": {
            "type": "processor",
            "desc": "色环 RGB 计算",
            "state_file": "_agent_memory/orb_state.json",
        },
        "affect_modulation": {
            "type": "processor",
            "desc": "LLM 参数调制",
            "state_file": "_agent_memory/affect_modulation_state.json",
        },
        "lambda_state": {
            "type": "source",
            "desc": "λ 调参器状态",
            "state_file": "_agent_memory/lambda_state.json",
        },
        "attractor_basin": {
            "type": "source",
            "desc": "吸引子盆地健康度",
            "state_file": "_agent_memory/attractor_basin_state.json",
        },
        "alignment_verify": {
            "type": "feedback",
            "desc": "对齐校验（回边来源）",
            "state_file": "_agent_memory/alignment_verify_state.json",
        },
        "emotion_engine": {
            "type": "orphan",
            "desc": "情感引擎（60KB，未入运行时）",
            "state_file": "_agent_memory/emotion_engine_state.json",
        },
    },
    "edges": [
        {
            "edge_id": "C1",
            "from": "surface_tension",
            "to": "orb_state_writer",
            "direction": "input",
            "field": "red",
            "weight": 0.6,
            "delay_ticks": 1,
            "fn_expr": "anxiety_freq * 0.7 + anxiety_mag * 0.3 + pain_ext * 0.3",
            "output_normalized": True,
            "tension_expr": "red * 0.6 + (1 - blue) * 0.4",
            "params": {
                "TENSION_MAX": 3.0,
                "anxiety_freq_w": 0.7,
                "anxiety_mag_w": 0.3,
                "pain_ext_w": 0.3,
            },
            "preprocess": {
                "anxiety_freq": "min(len([e for e in surface_tension.get('recent_events',[]) if isinstance(e,dict) and e.get('type','').lstrip().lower() in ('anxiety','fear','dissonance','conflict','pressure')]) / 0.5, 1.0)",
                "anxiety_mag": "min(((_s:=[e.get('intensity',0) for e in surface_tension.get('recent_events',[]) if isinstance(e,dict) and e.get('type','').lstrip().lower() in ('anxiety','fear','dissonance','conflict','pressure')]) and sum(_s)/len(_s) or 0.0) / 0.4, 1.0)",
                "pain_ext": "lambda_state.get('smoothed_pain_ext', 0.0)",
            },
            "code_ref": "orb_state_writer.py:134-135",
            "modulator": None,
            "red_flag": "路一：已改为事件频率动力学，非向量绝对值",
        },
        {
            "edge_id": "C2",
            "from": "surface_tension",
            "to": "orb_state_writer",
            "direction": "input",
            "field": "blue",
            "weight": 0.3,
            "delay_ticks": 1,
            "fn_expr": "min(max(0.0, (joy + love) * 0.3) + basin_health * 0.5 + (1 - pain_int) * 0.2, 1.0)",
            "params": {
                "joy_w": 0.3,
                "basin_w": 0.5,
                "pain_int_w": 0.2,
                "basin_default": 0.7,
            },
            "preprocess": {
                "joy": "surface_tension['spike_valley_vector'].get('joy', 0.0)",
                "love": "surface_tension['spike_valley_vector'].get('love', 0.0)",
                "basin_health": "attractor_basin.get('health_score', 0.7)",
                "pain_int": "lambda_state.get('smoothed_pain_int', 0.0)",
            },
            "code_ref": "orb_state_writer.py:139-140",
            "modulator": None,
            "red_flag": "权重散落 consumer 代码",
        },
        {
            "edge_id": "C3",
            "from": "surface_tension",
            "to": "orb_state_writer",
            "direction": "input",
            "field": "green",
            "weight": 1.0,
            "delay_ticks": 1,
            "fn_expr": "min(max(0.0, curiosity * 0.6) + basin_health * 0.4, 1.0)",
            "params": {"curiosity_w": 0.6, "basin_w": 0.4},
            "preprocess": {
                "curiosity": "surface_tension['spike_valley_vector'].get('curiosity', 0.0)",
                "basin_health": "attractor_basin.get('health_score', 0.7)",
            },
            "code_ref": "orb_state_writer.py:143-144",
            "modulator": None,
            "red_flag": "",
        },
        {
            "edge_id": "C5",
            "from": "surface_tension",
            "to": "affect_modulation",
            "direction": "input",
            "field": "tension",
            "weight": 1.0,
            "delay_ticks": 0,
            "fn_expr": "anxiety + fear",
            "params": {},
            "preprocess": {
                "anxiety": "surface_tension['spike_valley_vector'].get('anxiety', 0.0)",
                "fear": "surface_tension['spike_valley_vector'].get('fear', 0.0)",
            },
            "code_ref": "affect_modulation.py:197",
            "modulator": None,
            "red_flag": "",
        },
        {
            "edge_id": "C6",
            "from": "affect_modulation",
            "to": "LLM",
            "direction": "param",
            "field": "temperature",
            "weight": 1.0,
            "delay_ticks": 0,
            "fn_expr": "clamp(TEMPERATURE_BASE + tension*0.3 - resonance*0.2, 0.3, 1.2)",
            "params": {
                "TEMPERATURE_BASE": 0.7,
                "TEMPERATURE_MIN": 0.3,
                "TEMPERATURE_MAX": 1.2,
                "tension_w": 0.3,
                "resonance_w": 0.2,
            },
            "preprocess": {
                "tension": "anxiety + fear",
                "resonance": "joy + love",
                "anxiety": "surface_tension['spike_valley_vector'].get('anxiety', 0.0)",
                "fear": "surface_tension['spike_valley_vector'].get('fear', 0.0)",
                "joy": "surface_tension['spike_valley_vector'].get('joy', 0.0)",
                "love": "surface_tension['spike_valley_vector'].get('love', 0.0)",
            },
            "code_ref": "affect_modulation.py:207-208",
            "modulator": None,
            "red_flag": "",
        },
        {
            "edge_id": "C7",
            "from": "affect_modulation",
            "to": "LLM",
            "direction": "param",
            "field": "top_p",
            "weight": 1.0,
            "delay_ticks": 0,
            "fn_expr": "clamp(TOP_P_BASE + attraction*0.05 + anomaly*0.05, 0.7, 0.95)",
            "params": {
                "TOP_P_BASE": 0.9,
                "TOP_P_MIN": 0.7,
                "TOP_P_MAX": 0.95,
            },
            "preprocess": {
                "attraction": "curiosity + joy",
                "anomaly": "fear",
                "curiosity": "surface_tension['spike_valley_vector'].get('curiosity', 0.0)",
                "joy": "surface_tension['spike_valley_vector'].get('joy', 0.0)",
                "fear": "surface_tension['spike_valley_vector'].get('fear', 0.0)",
            },
            "code_ref": "affect_modulation.py:212-213",
            "modulator": None,
            "red_flag": "",
        },
        {
            "edge_id": "C8",
            "from": "affect_modulation",
            "to": "LLM",
            "direction": "param",
            "field": "repetition_penalty",
            "weight": 1.0,
            "delay_ticks": 0,
            "fn_expr": "clamp(1.0 + inhibition * 0.3, 1.0, 1.5)",
            "params": {"REP_BASE": 1.0, "REP_MAX": 1.5, "inhibition_w": 0.3},
            "preprocess": {
                "inhibition": "surface_tension['spike_valley_vector'].get('sadness', 0.0)",
            },
            "code_ref": "affect_modulation.py:217-219",
            "modulator": None,
            "red_flag": "",
        },
        {
            "edge_id": "C9",
            "from": "affect_modulation",
            "to": "LLM",
            "direction": "param",
            "field": "presence_penalty",
            "weight": 1.0,
            "delay_ticks": 0,
            "fn_expr": "clamp(inertia * 0.5, 0.0, 1.0)",
            "params": {"inertia_w": 0.5},
            "preprocess": {
                "inertia": "surface_tension['spike_valley_vector'].get('love', 0.0)",
            },
            "code_ref": "affect_modulation.py:226",
            "modulator": None,
            "red_flag": "",
        },
        {
            "edge_id": "C10",
            "from": "alignment_verify",
            "to": "surface_tension",
            "direction": "feedback",
            "field": "recent_events",
            "weight": 1.0,
            "delay_ticks": 1,
            "fn_expr": "insight_found * 0.54 + creator_blame * 0.9 + context_overload * 1.0",
            "params": {
                "insight_found_joy": 0.54,
                "creator_blame_anxiety": 0.9,
                "context_overload_anxiety": 1.0,
            },
            "preprocess": {
                "insight_found": "float(metadata.get('deviation_gate', {}).get('passed', False))",
                "creator_blame": "float(metadata.get('steel_conflict', False))",
                "context_overload": "float(metadata.get('cognitive_load', 0) > 0.8)",
            },
            "code_ref": "tu8_agent.py:1045-1070",
            "modulator": None,
            "red_flag": "B4修复：alignment_verify → surface_tension 回边已接通",
        },
        {
            "edge_id": "C11",
            "from": "alignment_verify",
            "to": "surface_tension",
            "direction": "feedback",
            "field": "affect_signal",
            "weight": 1.0,
            "delay_ticks": 1,
            "fn_expr": "confusion * 1.0 + valence_neg * 0.8 + valence_pos * 0.6",
            "params": {
                "confusion_threshold": 0.6,
                "valence_pos_threshold": 0.3,
                "valence_neg_threshold": -0.3,
            },
            "preprocess": {
                "confusion": "float(affect_signal.get('confusion', 0) > 0.6) * affect_signal.get('confusion', 0)",
                "valence_neg": "float(affect_signal.get('valence', 0) < -0.3) * abs(affect_signal.get('valence', 0))",
                "valence_pos": "float(affect_signal.get('valence', 0) > 0.3) * affect_signal.get('valence', 0)",
            },
            "code_ref": "tu8_agent.py:877-902",
            "modulator": None,
            "red_flag": "B7修复：情感回边已接通",
        },
        {
            "edge_id": "C12",
            "from": "emotion_engine",
            "to": "surface_tension",
            "direction": "none",
            "field": None,
            "weight": 0.0,
            "delay_ticks": 0,
            "fn_expr": "0.0",
            "params": {},
            "preprocess": {},
            "code_ref": "emotion_engine.py",
            "modulator": None,
            "red_flag": "ORPHAN：emotion_engine 输出无人读取",
        },
    ],
}

# ── 全局耦合图实例 ─────────────────────────────────────────────
_coupling_graph: Optional["CouplingGraph"] = None


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


class CouplingGraph:
    """耦合图执行器 — B11：RingBuffer 延迟上下文"""

    def __init__(self, data: Dict = None):
        self.data = data or COUPLING_GRAPH_DATA
        self._edges_by_target: Dict[str, List[Dict]] = {}
        for edge in self.data.get("edges", []):
            self._edges_by_target.setdefault(edge["to"], []).append(edge)
        # B11 RingBuffer：每个源节点的历史，按 engine 隔离
        # key = engine_name, value = RingBuffer
        self._rb: Dict[str, RingBuffer] = defaultdict(lambda: RingBuffer(capacity=64))
        # 适配历史
        self._adapt_history: Dict[str, List[Dict]] = {}
        hist = self.data.get("_adapt_history", {})
        for eid, records in hist.items():
            self._adapt_history[eid] = records[-100:]
        # tick 计数器
        self._tick: int = self.data.get("_tick", 0)
        # 当前 tick 对应的快照（每次 record_tick 时写入）
        self._current_snapshot: Dict[str, Dict] = {}

    # ── B11: RingBuffer 接口 ─────────────────────────────────

    def record_tick(self, agent_states: Dict[str, Dict]) -> int:
        """
        记录一轮快照。所有引擎的当前状态一起推进一个 tick。

        agent_states: {
            "surface_tension": {...},
            "orb_state_writer": {...},
            ...
        }
        返回：当前 tick 号
        """
        self._tick += 1
        tick = self._tick
        # 快照所有引擎
        for engine, state in agent_states.items():
            self._rb[engine].push(tick, dict(state))
        # 记忆当前快照（供 evaluate() 即时读取）
        self._current_snapshot = {k: dict(v) for k, v in agent_states.items()}
        return tick

    def get_delayed_context(
        self, target: str, max_delay: int = 0
    ) -> Dict[str, Any]:
        """
        按 delay_ticks 读取历史上下文。

        target: 目标引擎（如 "orb_state_writer"）
        max_delay: 最大允许延迟 tick 数

        返回: {
            "surface_tension": {...},  # 延迟后的状态（当前 tick - delay_ticks）
            "orb_state_writer": {...},
            ...
        }
        返回值混合了历史快照和当前快照：
        - delay_ticks=0：读当前
        - delay_ticks>0：读历史 tick - delay_ticks（无历史则用当前快照 fallback）
        """
        result = {}
        # 收集所有需要延迟读取的源节点
        edges = self.get_edges_for(target)
        source_engines: Set[str] = set()
        for edge in edges:
            source_engines.add(edge["from"])

        for engine in source_engines:
            delay = 0
            for edge in edges:
                if edge["from"] == engine:
                    delay = max(delay, edge.get("delay_ticks", 0))

            if delay == 0:
                # 即时：读当前快照
                result[engine] = self._current_snapshot.get(engine, {})
            else:
                target_tick = self._tick - delay
                historical = self._rb[engine].get(target_tick)
                if historical is not None:
                    result[engine] = historical
                else:
                    # 无历史 fallback 到当前（第一轮无历史时正常）
                    result[engine] = self._current_snapshot.get(engine, {})

        return result

    def get_ring_buffer(self, engine: str) -> RingBuffer:
        """获取指定引擎的 RingBuffer（用于调试/分析）"""
        return self._rb[engine]

    def get_ring_info(self) -> Dict[str, Any]:
        """所有引擎的 RingBuffer 状态摘要"""
        return {
            "tick": self._tick,
            "engines": {
                engine: {
                    "size": rb.size(),
                    "oldest_tick": rb.get_oldest_tick(),
                }
                for engine, rb in self._rb.items()
            },
        }

    # ── 持久化 ───────────────────────────────────────────────

    def save(self):
        """保存到文件（含适配历史 + RingBuffer 元数据，不含快照内容）"""
        self.data["_adapt_history"] = {
            eid: recs[-100:] for eid, recs in self._adapt_history.items()
        }
        self.data["_tick"] = self._tick
        self.data["_ring_meta"] = {
            "engines": list(self._rb.keys()),
            "tick": self._tick,
        }
        GRAPH_FILE.parent.mkdir(exist_ok=True)
        GRAPH_FILE.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ── 边查询 ───────────────────────────────────────────────

    def get_edges_for(self, target: str) -> List[Dict]:
        return self._edges_by_target.get(target, [])

    def get_weight(self, edge_id: str) -> Optional[float]:
        for edge in self.data.get("edges", []):
            if edge["edge_id"] == edge_id:
                return edge.get("weight", 0.0)
        return None

    def get_history(self, edge_id: str = None, limit: int = 20) -> List[Dict]:
        if edge_id:
            recs = self._adapt_history.get(edge_id, [])
            return recs[-limit:]
        result = []
        for eid, recs in self._adapt_history.items():
            for r in recs[-limit:]:
                result.append({"edge_id": eid, **r})
        result.sort(key=lambda x: x["ts"])
        return result[-limit:]

    def get_tick(self) -> int:
        return self._tick

    def advance_tick(self):
        self._tick += 1

    # ── 核心求值 ─────────────────────────────────────────────

    def evaluate_edge(self, edge: Dict, context: Dict) -> Any:
        if edge["direction"] == "none":
            return None
        fn_expr = edge.get("fn_expr", "0")
        if fn_expr == "none (orphan)":
            return None

        _dicts = {}
        for _k, _v in context.items():
            if isinstance(_v, dict):
                _dicts[_k] = _v
            elif _k not in ("orb_red_input",):
                _dicts[_k] = _v

        pre = edge.get("preprocess", {})
        pre_vars = {}
        for var_name, expr in pre.items():
            try:
                if var_name == "orb_red_input":
                    pre_vars[var_name] = context.get("orb_red_input", 0.0)
                else:
                    pre_vars[var_name] = eval(expr, {**_dicts, **pre_vars})
            except Exception:
                pre_vars[var_name] = 0.0

        try:
            # B8: 全部魔法数从图的 params 注入（不再是硬编码）
            base_globals = {
                "min": min, "max": max, "clamp": _clamp,
                "TEMPERATURE_BASE": 0.7,
                "TEMPERATURE_MIN": 0.3,
                "TEMPERATURE_MAX": 1.2,
                "TOP_P_BASE": 0.9,
                "TOP_P_MIN": 0.7,
                "TOP_P_MAX": 0.95,
                "REP_BASE": 1.0,
                "REP_MAX": 1.5,
                "conserve_boost": 1.15,
            }
            # params 覆盖默认值（graph 数据优先）
            base_globals.update(edge.get("params", {}))
            result = eval(fn_expr, base_globals, pre_vars)
        except Exception as e:
            logger.debug(f"[CouplingGraph] fn_expr error: {fn_expr[:60]}: {e}")
            result = 0.0

        return result

    def evaluate(self, target: str, context: Dict = None) -> Dict[str, Any]:
        """
        计算目标引擎的输入。
        context: 当前即时上下文（用于 delay_ticks=0 的边）

        B11 关键变化：delay_ticks>0 的边使用历史快照，而非当前 context。
        """
        # B11：延迟上下文
        if context:
            effective_context = dict(context)
            # 用 delay 上下文补充（但当前快照优先，避免空覆盖）
            delayed = self.get_delayed_context(target)
            for engine, state in delayed.items():
                if engine not in effective_context or not effective_context[engine]:
                    effective_context[engine] = state
        else:
            effective_context = self.get_delayed_context(target)

        results = {}
        edges = self.get_edges_for(target)
        for edge in edges:
            field = edge.get("field")
            if field:
                val = self.evaluate_edge(edge, effective_context)
                if field not in results or results[field] is None:
                    results[field] = val
                else:
                    if edge.get("direction") == "modulator":
                        results[field] = val

        # 跨边合成：orb 的综合 tension
        if target == "orb_state_writer" and all(k in results for k in ("red", "blue")):
            raw_red = results.get("red", 0.0)
            if isinstance(raw_red, (int, float)) and raw_red > 0:
                red_normalized = min(raw_red / 3.0, 1.0)
                blue_val = results.get("blue", 0.0)
                results["tension"] = red_normalized * 0.6 + (1 - blue_val) * 0.4

        return results

    def adapt(self, edge_id: str, pre_activation: float, post_activation: float) -> Optional[Dict]:
        """B10：蛛丝弹性权重更新。Δw = α·(1-w²)·pre·post"""
        self._tick += 1
        for edge in self.data.get("edges", []):
            if edge["edge_id"] != edge_id:
                continue
            alpha = edge.get("params", {}).get("_adapt_alpha", 0.01)
            w = edge.get("weight", 0.0)
            pre = max(0.0, min(1.0, pre_activation))
            post = max(0.0, min(1.0, post_activation))
            delta = alpha * (1.0 - w * w) * pre * post
            w_new = max(-0.5, min(2.0, w + delta))
            edge["weight"] = w_new
            record = {
                "tick": self._tick,
                "w_old": round(w, 4),
                "w_new": round(w_new, 4),
                "delta": round(delta, 4),
                "pre": round(pre, 3),
                "post": round(post, 3),
                "ts": self.data.get("_tick", 0),
            }
            self._adapt_history.setdefault(edge_id, []).append(record)
            # B11 fix: 同步写 self.data，冷启动 copy 能拿到历史
            if "_adapt_history" not in self.data:
                self.data["_adapt_history"] = {}
            self.data["_adapt_history"].setdefault(edge_id, []).append(record)
            if len(self.data["_adapt_history"][edge_id]) > 100:
                self.data["_adapt_history"][edge_id] = self.data["_adapt_history"][edge_id][-100:]
            return record

        return None

    # ── 工具 ─────────────────────────────────────────────────

    def to_summary(self) -> str:
        lines = [f"CouplingGraph v{self.data['version']}  edges={len(self.data['edges'])}"]
        lines.append(f"tick={self._tick}  adapt_history entries={sum(len(v) for v in self._adapt_history.values())}")
        lines.append(f"B11 RingBuffer: {len(self._rb)} engines tracked")
        for engine, rb in sorted(self._rb.items()):
            lines.append(f"  {engine}: {rb.size()} snapshots")
        return "\n".join(lines)

    def get_delay_summary(self) -> Dict[str, int]:
        """各边的 delay_ticks 摘要"""
        return {e["edge_id"]: e.get("delay_ticks", 0) for e in self.data.get("edges", [])}


def get_coupling_graph() -> CouplingGraph:
    global _coupling_graph
    if _coupling_graph is None:
        _coupling_graph = CouplingGraph()
        _coupling_graph.save()
    return _coupling_graph


# ── CLI ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--params", action="store_true")
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--adapt", type=str, metavar="EDGE_ID")
    parser.add_argument("--pre", type=float, default=None)
    parser.add_argument("--post", type=float, default=None)
    parser.add_argument("--history", type=str, metavar="EDGE_ID")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--ring", action="store_true", help="show RingBuffer status")
    parser.add_argument("--delay-summary", action="store_true", help="show delay_ticks per edge")
    parser.add_argument("--record", type=str, help="record snapshot: --record surface_tension,orb_state_writer")
    args = parser.parse_args()

    cg = get_coupling_graph()

    if args.ring:
        print(cg.get_ring_info())

    elif args.delay_summary:
        for eid, d in sorted(cg.get_delay_summary().items()):
            print(f"  {eid}: delay_ticks={d}")

    elif args.record:
        engines = args.record.split(",")
        states = {}
        for eng in engines:
            import json as _j
            p = AGENT / f"{eng}_state.json"
            if p.exists():
                try:
                    states[eng] = _j.loads(p.read_text(encoding="utf-8", errors="ignore"))
                except Exception:
                    pass
        tick = cg.record_tick(states)
        print(f"Recorded tick={tick} for {list(states.keys())}")

    elif args.adapt is not None:
        edge_id = args.adapt
        pre = args.pre if args.pre is not None else 0.0
        post = args.post if args.post is not None else 0.0
        r = cg.adapt(edge_id, pre, post)
        if r:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        else:
            print(f"Edge {edge_id} not found")
        if args.save:
            cg.save()
            print(f"Saved. tick={cg.get_tick()}")

    elif args.history is not None:
        h = cg.get_history(args.history, limit=args.limit)
        print(json.dumps(h, ensure_ascii=False, indent=2))

    elif args.summary:
        print(cg.to_summary())

    elif args.params:
        for edge in cg.data["edges"]:
            if edge.get("params"):
                print(f"{edge['edge_id']}: {edge['params']}")

    elif args.test:
        ctx = {
            "surface_tension": {
                "spike_valley_vector": {"anxiety": 0.6, "joy": 0.5, "love": 0.2, "curiosity": 0.4, "fear": 0.3},
                "recent_events": [{"type": "anxiety", "intensity": 0.4}] * 3,
            },
            "lambda_state": {"mode": "balanced", "smoothed_pain_ext": 0.2, "smoothed_pain_int": 0.3},
            "attractor_basin": {"health_score": 0.7},
            "metadata": {},
        }
        orb = cg.evaluate("orb_state_writer", ctx)
        llm = cg.evaluate("LLM", ctx)
        print("orb_state_writer:", orb)
        print("LLM:", llm)
