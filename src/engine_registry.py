# -*- coding: utf-8 -*-
"""
engine_registry.py — TU-8 全局引擎注册表 v1.0

B2: 替代隐式文件轮询，提供统一的引擎清单、状态、依赖、tick 管理。
B1 基础设施：engine_tick.json 是全局同步 tick 计数器。

Schema (engine_registry.json):
  tick: int              — 全局 tick，从 0 开始，每协调轮 +1
  last_sync: float       — 上次 tick 时间戳
  engines: {eng_id: {
    state_file: str       — 引擎状态文件路径（相对于 WS）
    last_tick: int       — 该引擎上次消费的 tick（消费 tick[N-1] 则写 N）
    max_age_s: int       — 最大存活年龄（秒），超过视为 STALE
    deps: [eng_id]       — 直接依赖的引擎列表（读取其 state_file）
    deps_mode: str       — 'and'/'or'（全有/有其一即可）
    status: str          — OK / STALE / DEAD / UNKNOWN
    last_seen: float     — 上次活跃时间戳
    last_ok: float       — 上次 OK 时间戳
    consecutive_fail: int
    metadata: {}         — 自由扩展
  }}

用法:
  from engine_registry import get_registry, tick_engines
  reg = get_registry()
  reg.register('surface_tension', state_file='...', max_age_s=600, deps=['...'])
  tick_engines(['surface_tension', 'orb_state_writer'], dry_run=False)
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger("engine_registry")

WS = Path(os.environ.get("QCLAW_WORKSPACE",
               r"C:\Users\qq366410837\.qclaw\workspace"))
AGENT = WS / "_agent_memory"
AGENT.mkdir(exist_ok=True)

REGISTRY_FILE = AGENT / "engine_registry.json"
TICK_FILE = AGENT / "engine_tick.json"
TICK_INTERVAL = 300  # 每 5 分钟一次协调 tick

# ── 默认注册表（15 个 cron 引擎 + 5 个主循环引擎）───────────────
DEFAULT_ENGINES: Dict[str, Dict] = {
    # ── cron 引擎 ──────────────────────────────────────────────
    "surface_tension_decay": {
        "state_file": "_agent_memory/surface_tension_state.json",
        "max_age_s": 600,
        "deps": [],
        "deps_mode": "and",
        "metadata": {"desc": "张力感知衰减", "interval": 300},
    },
    "orb_state_writer": {
        "state_file": "_agent_memory/orb_state.json",
        "max_age_s": 600,
        "deps": ["surface_tension_decay"],
        "deps_mode": "and",
        "metadata": {"desc": "色环RGB写入", "interval": 360},
    },
    "lambda_state": {
        "state_file": "_agent_memory/lambda_state.json",
        "max_age_s": 600,
        "deps": [],
        "deps_mode": "and",
        "metadata": {"desc": "λ调参器状态", "interval": 300},
    },
    "interoceptive": {
        "state_file": "_agent_memory/interoception_state.json",
        "max_age_s": 600,
        "deps": ["surface_tension_decay"],
        "deps_mode": "and",
        "metadata": {"desc": "内感受皮层", "interval": 360},
    },
    "active_curiosity": {
        "state_file": "_heartbeat/heartbeat_state.json",
        "max_age_s": 900,
        "deps": [],
        "deps_mode": "and",
        "metadata": {"desc": "主动好奇心", "interval": 600},
    },
    "dream_check": {
        "state_file": "_agent_memory/dream_consolidation_state.json",
        "max_age_s": 1440,
        "deps": ["surface_tension_decay"],
        "deps_mode": "and",
        "metadata": {"desc": "梦境整合", "interval": 720},
    },
    "liveness": {
        "state_file": "_agent_memory/interoception_liveness_state.json",
        "max_age_s": 840,
        "deps": [],
        "deps_mode": "and",
        "metadata": {"desc": "存活检查", "interval": 420},
    },
    "metabolism": {
        "state_file": "_agent_memory/metabolism_state.json",
        "max_age_s": 1800,
        "deps": [],
        "deps_mode": "and",
        "metadata": {"desc": "代谢仪表盘", "interval": 900},
    },
    "hp4_heartbeat": {
        "state_file": "_agent_memory/hp4_heartbeat_state.json",
        "max_age_s": 3600,
        "deps": [],
        "deps_mode": "and",
        "metadata": {"desc": "HP4心跳钩子", "interval": 1800},
    },
    "skin_cycle": {
        "state_file": "_agent_memory/skin_cycle_state.json",
        "max_age_s": 7200,
        "deps": [],
        "deps_mode": "and",
        "metadata": {"desc": "脱皮穿皮", "interval": 3600},
    },
    "prune_guard": {
        "state_file": "_agent_memory/prune_thermal_guard_state.json",
        "max_age_s": 600,
        "deps": [],
        "deps_mode": "and",
        "metadata": {"desc": "节点剪枝热保护", "interval": 300},
    },
    "entropy_guard": {
        "state_file": "_agent_memory/entropy_guard_state.json",
        "max_age_s": 7200,
        "deps": [],
        "deps_mode": "and",
        "metadata": {"desc": "注意力茧房防御", "interval": 3600},
    },
    "visual_world_model": {
        "state_file": "_agent_memory/cron_visual_world_model_state.json",
        "max_age_s": 3600,
        "deps": [],
        "deps_mode": "and",
        "metadata": {"desc": "视觉世界模型", "interval": 1800, "parked": True},
    },
    "learning_apply": {
        "state_file": "_agent_memory/learning_action_log.json",
        "max_age_s": 3600,
        "deps": ["surface_tension_decay"],
        "deps_mode": "and",
        "metadata": {"desc": "学习消费端", "interval": 1800},
    },
    "health_probe": {
        "state_file": "_agent_memory/health_probe_state.json",
        "max_age_s": 600,
        "deps": [],  # health_probe 读所有，不需要依赖
        "deps_mode": "and",
        "metadata": {"desc": "引擎健康心跳", "interval": 300},
    },
    # ── 主循环引擎（不在 cron，由 tu8_agent 调用）───────────────
    "consciousness_cycle": {
        "state_file": "_agent_memory/consciousness_cycle_state.json",
        "max_age_s": 3600,
        "deps": [],
        "deps_mode": "and",
        "metadata": {"desc": "意识循环主引擎", "interval": 0, "on_demand": True},
    },
    "surface_tension_agent": {
        "state_file": "_agent_memory/surface_tension_state.json",
        "max_age_s": 60,  # tu8_agent 对话触发，间隔短
        "deps": [],
        "deps_mode": "and",
        "metadata": {"desc": "对话触发surface_tension", "interval": 0, "on_demand": True},
    },
    "tension_distiller": {
        "state_file": "_agent_memory/tension_queue.json",
        "max_age_s": 14400,
        "deps": ["surface_tension_decay"],
        "deps_mode": "and",
        "metadata": {"desc": "张力蒸馏器", "interval": 0, "on_demand": True},
    },
    # ── 后续补充的 cron 引擎 ────────────────────────────────────
    "coupling_adapt": {
        "state_file": "_agent_memory/coupling_graph.json",
        "max_age_s": 3600,
        "deps": [],
        "deps_mode": "and",
        "metadata": {"desc": "蛛丝弹性权重适配", "interval": 600},
    },
    "render_layer_speak": {
        "state_file": "_agent_memory/render_layer_state.json",
        "max_age_s": 3600,
        "deps": ["orb_state_writer"],
        "deps_mode": "and",
        "metadata": {"desc": "渲染层语音输出", "interval": 1800},
    },
    "weismann_guard": {
        "state_file": "_agent_memory/weismann_baseline.json",
        "max_age_s": 3600,
        "deps": [],
        "deps_mode": "and",
        "on_demand": True,
        "metadata": {"desc": "[Weismann] 层1写保护守护（生殖细胞变更审计）", "interval": 1800},
    },
    "weismann_evaluate": {
        "state_file": "_agent_memory/weismann_eval_state.json",
        "max_age_s": 3600,
        "deps": [],
        "deps_mode": "and",
        "on_demand": True,
        "metadata": {"desc": "[Weismann] 三层评估器（L1硬校验/L2自评/L3环境）", "interval": 3600},
    },
    "weismann_seepage": {
        "state_file": "_agent_memory/weismann_proposals.json",
        "max_age_s": 3600,
        "deps": [],
        "deps_mode": "and",
        "on_demand": True,
        "metadata": {"desc": "[Weismann] 层3渗漏通道（体细胞经验→提案）", "interval": 3600},
    },
}


def _load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return default if default is not None else {}


def _save_json(path: Path, data) -> bool:
    try:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        return True
    except Exception as e:
        logger.warning(f"_save_json failed {path}: {e}")
        return False


class EngineRegistry:
    """全局引擎注册表"""

    def __init__(self):
        self.data = _load_json(REGISTRY_FILE, {
            "tick": 0,
            "last_sync": 0.0,
            "engines": {}
        })
        # 初始化默认引擎（向后兼容：只添加未注册的）
        for eng_id, spec in DEFAULT_ENGINES.items():
            if eng_id not in self.data["engines"]:
                self.data["engines"][eng_id] = {
                    "state_file": spec["state_file"],
                    "max_age_s": spec["max_age_s"],
                    "deps": spec.get("deps", []),
                    "deps_mode": spec.get("deps_mode", "and"),
                    "status": "UNKNOWN",
                    "last_tick": -1,
                    "last_seen": 0.0,
                    "last_ok": 0.0,
                    "consecutive_fail": 0,
                    "metadata": spec.get("metadata", {}),
                }
                logger.info(f"[Registry] 初始化新引擎: {eng_id}")

    def save(self) -> bool:
        return _save_json(REGISTRY_FILE, self.data)

    def register(self, eng_id: str, state_file: str = None,
                 max_age_s: int = 600, deps: List[str] = None,
                 deps_mode: str = "and", metadata: Dict = None):
        """注册或更新引擎"""
        if eng_id not in self.data["engines"]:
            self.data["engines"][eng_id] = {
                "state_file": state_file or "",
                "max_age_s": max_age_s,
                "deps": deps or [],
                "deps_mode": deps_mode,
                "status": "UNKNOWN",
                "last_tick": -1,
                "last_seen": 0.0,
                "last_ok": 0.0,
                "consecutive_fail": 0,
                "metadata": metadata or {},
            }

    def get_engine(self, eng_id: str) -> Optional[Dict]:
        return self.data["engines"].get(eng_id)

    def update_status(self, eng_id: str, status: str, last_tick: int = None):
        """更新引擎状态"""
        if eng_id not in self.data["engines"]:
            return
        now = time.time()
        eng = self.data["engines"][eng_id]
        eng["status"] = status
        eng["last_seen"] = now
        if last_tick is not None:
            eng["last_tick"] = last_tick
        if status == "OK":
            eng["last_ok"] = now
            eng["consecutive_fail"] = 0
        elif status in ("STALE", "DEAD"):
            eng["consecutive_fail"] += 1

    def check_health(self, eng_id: str) -> str:
        """单引擎健康检查：OK / STALE / DEAD"""
        eng = self.get_engine(eng_id)
        if eng is None:
            return "UNKNOWN"
        state_file = WS / eng["state_file"]
        if not state_file.exists():
            return "DEAD"
        age = time.time() - os.path.getmtime(state_file)
        if age > eng["max_age_s"] * 3:
            return "DEAD"
        elif age > eng["max_age_s"]:
            return "STALE"
        return "OK"

    def refresh_all_status(self) -> Dict[str, str]:
        """刷新所有引擎状态"""
        results = {}
        for eng_id in self.data["engines"]:
            s = self.check_health(eng_id)
            self.update_status(eng_id, s)
            results[eng_id] = s
        return results

    def get_deps_status(self, eng_id: str) -> Dict[str, str]:
        """获取引擎依赖状态"""
        eng = self.get_engine(eng_id)
        if not eng:
            return {}
        return {dep: self.check_health(dep) for dep in eng.get("deps", [])}

    def can_run(self, eng_id: str) -> tuple[bool, str]:
        """检查引擎是否可以运行（依赖满足）"""
        eng = self.get_engine(eng_id)
        if not eng:
            return False, "未知引擎"
        deps = eng.get("deps", [])
        if not deps:
            return True, "无依赖"
        mode = eng.get("deps_mode", "and")
        dep_statuses = self.get_deps_status(eng_id)
        if mode == "and":
            ok = all(s == "OK" for s in dep_statuses.values())
            return ok, "所有依赖 OK" if ok else f"依赖异常: {dep_statuses}"
        else:
            ok = any(s == "OK" for s in dep_statuses.values())
            return ok, "有依赖 OK" if ok else f"无活跃依赖: {dep_statuses}"

    def advance_tick(self) -> int:
        """推进全局 tick，返回新 tick"""
        self.data["tick"] += 1
        self.data["last_sync"] = time.time()
        self.save()
        return self.data["tick"]

    @property
    def tick(self) -> int:
        return self.data["tick"]

    @property
    def last_sync(self) -> float:
        return self.data["last_sync"]


# ── 全局单例 ─────────────────────────────────────────────────
_registry: Optional[EngineRegistry] = None


def get_registry() -> EngineRegistry:
    global _registry
    if _registry is None:
        _registry = EngineRegistry()
    return _registry


def tick_engines(eng_ids: List[str], dry_run: bool = False) -> Dict[str, Any]:
    """
    协调一组引擎按依赖顺序 tick。
    每次调用 advance_tick() 推进全局 tick，
    各引擎消费 tick[N-1]，输出 tick[N]。
    """
    reg = get_registry()
    new_tick = reg.advance_tick()
    results = {}
    for eng_id in eng_ids:
        can, reason = reg.can_run(eng_id)
        if not can:
            results[eng_id] = {"ok": False, "skip": True, "reason": reason}
            continue
        eng = reg.get_engine(eng_id)
        results[eng_id] = {
            "ok": True,
            "tick": new_tick,
            "consume_tick": new_tick - 1,
            "state_file": eng["state_file"],
        }
        # 更新该引擎的 last_tick
        reg.update_status(eng_id, "OK", last_tick=new_tick)
    if not dry_run:
        reg.save()
    return results


# ── CLI ──────────────────────────────────────────────────────
if __name__ == "__main__":
    reg = get_registry()
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--tick", action="store_true")
    args = parser.parse_args()

    if args.status:
        statuses = reg.refresh_all_status()
        print(f"[Registry] tick={reg.tick}  last_sync={reg.last_sync:.0f}s ago")
        for eng_id, s in sorted(statuses.items()):
            eng = reg.get_engine(eng_id)
            meta = eng.get("metadata", {})
            deps = eng.get("deps", [])
            icon = {"OK": "O", "STALE": "~", "DEAD": "X", "UNKNOWN": "?"}[s]
            on_demand = "(on_demand)" if meta.get("on_demand") else ""
            print(f"  [{icon}] {eng_id:<30} max={eng['max_age_s']}s deps={deps} {on_demand}")
        reg.save()

    elif args.refresh:
        statuses = reg.refresh_all_status()
        ok = sum(1 for s in statuses.values() if s == "OK")
        print(f"OK={ok}/{len(statuses)}  tick={reg.tick}")
        reg.save()

    elif args.tick:
        results = tick_engines(list(reg.data["engines"].keys()))
        ok = sum(1 for r in results.values() if r.get("ok"))
        print(f"tick={reg.tick}  ok={ok}/{len(results)}")
