"""
dream_decay.py - 自然遗忘衰减器
TU-8 深层-浅层架构 P2
依赖: anchor_state_machine / constraint_lifecycle
"""

import json, os, time

AGENT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_agent_memory"
)
STATE_FILE = os.path.join(AGENT, "dream_decay_state.json")

HALF_LIFE = {
    "topology_fragment": 5400,       # 1.5h
    "dream_fragment": 7200,            # 2h（续梦期）
    "post_collapse_residue": 1800,   # 0.5h（崩溃残留）
}
THRESHOLD = 0.15                     # 能量低于此值 → 可剪枝
TYPES = set(HALF_LIFE.keys())


def _snap(raw):
    t = raw.get("type", "topology_fragment")
    return {
        "type": t if t in TYPES else "topology_fragment",
        "tension": max(0.0, min(1.0, raw.get("tension", 0))),
        "energy": max(0.0, min(1.0, raw.get("energy", 1))),
        "created_at": raw.get("created_at", time.time()),
        "updated_at": raw.get("updated_at", time.time()),
        "consolidated_at": raw.get("consolidated_at"),
        "prune_ready": raw.get("prune_ready", False),
        "metadata": raw.get("metadata", {}),
    }


class DreamDecay:
    """自然遗忘衰减器"""

    def __init__(self, path=None):
        self._p = path or STATE_FILE
        self._d = {}
        self._load()

    # ── 公开 API ──

    def register(self, snapshot_id: str,
                 type_: str = "topology_fragment",
                 tension: float = 0.0,
                 energy: float = 1.0,
                 metadata: dict = None) -> str:
        """注册新快照，自动进入衰减队列"""
        s = _snap({"type": type_, "tension": tension, "energy": energy})
        s["created_at"] = s["updated_at"] = time.time()
        if metadata:
            s["metadata"].update(metadata)
        self._d[snapshot_id] = s
        self._save()
        return snapshot_id

    def consolidate(self, snapshot_id: str, metadata: dict = None) -> bool:
        """标记为已加固——停止衰减"""
        s = self._d.get(snapshot_id)
        if not s:
            return False
        s["consolidated_at"] = time.time()
        if metadata:
            s["metadata"].update(metadata)
        s["prune_ready"] = False
        self._save()
        return True

    def reactivate(self, snapshot_id: str) -> bool:
        """重新激活未剪枝快照"""
        s = self._d.get(snapshot_id)
        if not s or s["prune_ready"]:
            return False
        s["energy"] = min(1.0, s["energy"] + 0.3)
        s["updated_at"] = time.time()
        self._save()
        return True

    def apply_decay(self) -> dict:
        """对所有未加固快照执行一次衰减"""
        now = time.time()
        decayed, prune, consolidated, warnings = [], [], [], []

        for sid, s in list(self._d.items()):
            if s["consolidated_at"] is not None:
                consolidated.append(sid)
                continue

            hl = HALF_LIFE.get(s["type"], 5400)
            dt = now - s["updated_at"]
            s["energy"] = max(0.0, s["energy"] * (1 - dt / hl / 2))
            s["updated_at"] = now

            if s["energy"] < THRESHOLD:
                s["prune_ready"] = True
                prune.append(sid)
            decayed.append(sid)

        self._save()
        return {
            "decayed": decayed,
            "prune_ready": prune,
            "consolidated": consolidated,
            "warnings": warnings,
        }

    def get(self, snapshot_id: str) -> dict | None:
        return self._d.get(snapshot_id)

    def get_all(self, type_filter: str = None) -> list:
        if type_filter:
            return [(k, v) for k, v in self._d.items() if v["type"] == type_filter]
        return list(self._d.items())

    def get_prune_ready(self) -> list:
        return [k for k, v in self._d.items() if v["prune_ready"]]

    def get_stats(self) -> dict:
        t = len(self._d)
        ae = sum(v["energy"] for v in self._d.values()) / t if t else 0
        return {
            "total": t,
            "consolidated": sum(1 for v in self._d.values() if v["consolidated_at"]),
            "prune_ready": sum(1 for v in self._d.values() if v["prune_ready"]),
            "avg_energy": round(ae, 3),
            "by_type": {k: sum(1 for v in self._d.values() if v["type"] == k)
                        for k in HALF_LIFE},
        }

    def clear_state(self):
        self._d.clear()
        self._save()

    # ── 持久化 ──

    def _load(self):
        if not os.path.exists(self._p):
            return
        try:
            with open(self._p, encoding="utf-8") as f:
                data = json.load(f)
            for sid, raw in data.get("snapshots", {}).items():
                self._d[sid] = _snap(raw)
        except (json.JSONDecodeError, OSError):
            pass

    def _save(self):
        os.makedirs(os.path.dirname(self._p), exist_ok=True)
        with open(self._p, "w", encoding="utf-8") as f:
            json.dump({
                "snapshots": self._d,
                "version": 2,
                "last_decay_at": time.time(),
            }, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    d = DreamDecay()
    d.clear_state()

    d.register("t1", "topology_fragment", 0.6, 1.0)
    d.register("t2", "dream_fragment", 0.8, 1.0)
    d.register("t3", "post_collapse_residue", 0.3, 0.5)

    d.consolidate("t1")

    # 伪造时间差
    d._d["t2"]["updated_at"] = time.time() - 7200 * 2  # 2个半衰期
    d._d["t3"]["updated_at"] = time.time() - 3600       # 1个半衰期

    r = d.apply_decay()

    assert d.get("t1")["consolidated_at"] is not None, "t1应已加固"
    assert "t2" in r["decayed"], "t2应已衰减"
    assert d.get("t2")["energy"] < 0.6, f"t2能量应显著下降, 实得 {d.get('t2')['energy']}"
    assert "t1" not in r["decayed"], "加固快照不应衰减"

    print(f"[PASS] DreamDecay — decayed={len(r['decayed'])}, "
          f"prune_ready={len(r['prune_ready'])}, "
          f"consolidated={len(r['consolidated'])}")
    d.clear_state()
