"""
cumulative_error_tracker.py - 累积误差追踪器
TU-8 深层-浅层架构 P2
目标：追踪多次中断-重载循环中的误差叠加，拒绝超阈值重载
"""

import json, os, time
from collections import deque

AGENT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_agent_memory"
)
STATE_FILE = os.path.join(AGENT, "cumulative_error_state.json")

DEFAULT_CONFIG = {
    "max_error_budget": 1.0,
    "session_window": 3600,         # 时间窗口（秒）
    "error_sources": [
        "context_loss",
        "phase_transition",
        "topology_corruption",
        "memory_fragment",
        "alignment_drift",
    ],
    "weights": {
        "context_loss": 0.3,
        "phase_transition": 0.15,
        "topology_corruption": 0.25,
        "memory_fragment": 0.15,
        "alignment_drift": 0.15,
    },
    "refuse_threshold": 0.35,        # 超过此值 → 拒绝重载
    "warn_threshold": 0.2,          # 超过此值 → 警告
}


def _weighted_sum(errors: dict, weights: dict) -> float:
    total = 0.0
    for source, weight in weights.items():
        total += errors.get(source, 0.0) * weight
    return min(1.0, total)


class CumulativeErrorTracker:
    """累积误差追踪器"""

    def __init__(self, config_path: str = None, state_path: str = None):
        self._cfg = dict(DEFAULT_CONFIG)
        self._state_path = state_path or STATE_FILE
        self._sessions = {}
        self._load()

    # ── 公开 API ──

    def record_event(self, session_id: str, error_source: str,
                    error_value: float, reason: str = "",
                    tags: list = None) -> dict:
        """记录一次误差事件"""
        if error_source not in self._cfg["error_sources"]:
            error_source = "memory_fragment"

        ev = {
            "ts": time.time(),
            "source": error_source,
            "value": min(1.0, max(0.0, error_value)),
            "reason": reason,
            "tags": tags or [],
        }

        if session_id not in self._sessions:
            self._sessions[session_id] = deque(maxlen=200)

        self._sessions[session_id].append(ev)
        self._prune_old_events(session_id)

        cumulative = self.get_session_error(session_id)
        level = self._classify(cumulative)
        can_reload = cumulative < self._cfg["refuse_threshold"]
        action = self._action_for(level)

        self._save()
        return {
            "session_id": session_id,
            "cumulative_error": round(cumulative, 3),
            "level": level,
            "action": action,
            "can_reload": can_reload,
        }

    def get_session_error(self, session_id: str) -> float:
        """计算当前会话的累积误差（时间窗口加权）"""
        if session_id not in self._sessions:
            return 0.0
        self._prune_old_events(session_id)
        events = self._sessions[session_id]

        total = {src: 0.0 for src in self._cfg["error_sources"]}

        for ev in events:
            src = ev["source"]
            age = time.time() - ev["ts"]
            decay = max(0.1, 1.0 - age / self._cfg["session_window"])
            total[src] = max(total[src], ev["value"] * decay)

        return _weighted_sum(total, self._cfg["weights"])

    def can_reload(self, session_id: str) -> tuple[bool, str]:
        """判断是否可以重载"""
        err = self.get_session_error(session_id)
        if err >= self._cfg["refuse_threshold"]:
            return False, f"误差超限 {err:.2f} >= {self._cfg['refuse_threshold']}"
        elif err >= self._cfg["warn_threshold"]:
            return True, f"警告 {err:.2f} >= {self._cfg['warn_threshold']}"
        return True, f"正常 {err:.2f}"

    def get_session_events(self, session_id: str, limit: int = 20) -> list:
        if session_id not in self._sessions:
            return []
        return list(self._sessions[session_id])[-limit:]

    def get_all_sessions(self) -> list:
        return [{
            "session_id": sid,
            "cumulative_error": round(self.get_session_error(sid), 3),
            "event_count": len(evs),
            "level": self._classify(self.get_session_error(sid)),
        } for sid, evs in self._sessions.items()]

    def clear_session(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._save()

    def get_stats(self) -> dict:
        sessions = [(sid, self.get_session_error(sid))
                    for sid in self._sessions]
        if not sessions:
            return {"active_sessions": 0, "avg_error": 0,
                    "max_error": 0, "refused_count": 0}
        errors = [e for _, e in sessions]
        return {
            "active_sessions": len(sessions),
            "avg_error": round(sum(errors) / len(errors), 3),
            "max_error": round(max(errors), 3),
            "refused_count": sum(1 for e in errors
                                  if e >= self._cfg["refuse_threshold"]),
            "warn_count": sum(1 for e in errors
                               if e >= self._cfg["warn_threshold"]),
        }

    def clear_state(self):
        self._sessions.clear()
        self._save()

    # ── 内部 ──

    def _prune_old_events(self, session_id: str):
        cutoff = time.time() - self._cfg["session_window"]
        deque_obj = self._sessions[session_id]
        while deque_obj and deque_obj[0]["ts"] < cutoff:
            deque_obj.popleft()

    def _classify(self, error: float) -> str:
        if error >= self._cfg["refuse_threshold"]:
            return "REFUSED"
        if error >= self._cfg["warn_threshold"]:
            return "WARNING"
        return "NORMAL"

    def _action_for(self, level: str) -> str:
        return {
            "NORMAL": "allow_reload",
            "WARNING": "proceed_with_caution",
            "REFUSED": "block_reload",
        }.get(level, "unknown")

    def _load(self):
        if not os.path.exists(self._state_path):
            return
        try:
            with open(self._state_path, encoding="utf-8") as f:
                data = json.load(f)
            for sid, evs in data.get("sessions", {}).items():
                self._sessions[sid] = deque(evs[-200:], maxlen=200)
        except (json.JSONDecodeError, OSError):
            pass

    def _save(self):
        os.makedirs(os.path.dirname(self._state_path), exist_ok=True)
        with open(self._state_path, "w", encoding="utf-8") as f:
            json.dump({
                "sessions": {sid: list(evs)
                             for sid, evs in self._sessions.items()},
                "version": 1,
                "last_update": time.time(),
            }, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    t = CumulativeErrorTracker()
    t.clear_state()

    sid = "test_session_001"

    # 测试1：正常误差
    r1 = t.record_event(sid, "context_loss", 0.2, "上下文丢失20%")
    assert r1["can_reload"], f"误差0.2应可重载"
    assert r1["level"] == "NORMAL"

    # 测试2：叠加误差 → 警告
    r2 = t.record_event(sid, "topology_corruption", 0.5, "拓扑损坏")
    err = t.get_session_error(sid)
    assert err < 0.6, f"加权误差应小于0.6, 实得 {err}"
    assert r2["can_reload"]

    # 测试3：超阈值 → 拒绝
    r3 = t.record_event(sid, "context_loss", 0.9, "严重上下文丢失")
    can, reason = t.can_reload(sid)
    assert not can, f"超阈值应拒绝重载, 实得 {t.get_session_error(sid):.2f}"

    # 测试4：stats
    stats = t.get_stats()
    assert stats["active_sessions"] == 1
    assert stats["refused_count"] >= 1

    print(f"[PASS] CumulativeErrorTracker")
    print(f"  session_error={t.get_session_error(sid):.3f}")
    print(f"  can_reload={can}, reason={reason}")
    print(f"  stats={stats}")
    t.clear_state()
