"""
带宽配额器 (BandwidthQuota)
对跨相态通道的带宽使用进行配额管理和限流。
"""

import json
import threading
import time
from pathlib import Path

DEFAULT_QUOTA = 5000  # 单位/分钟
RESET_INTERVAL = 60  # 秒（每分钟清零）
STATE_FILE = Path(__file__).parent.parent / "_agent_memory" / "bandwidth_quota_state.json"


class BandwidthQuota:
    """带宽配额管理器"""

    def __init__(self):
        self._lock = threading.Lock()
        self._allocations: dict[str, float] = {}  # channel_id -> quota limit
        self._usage: dict[str, float] = {}       # channel_id -> used amount in current window
        self._window_start: dict[str, float] = {}  # channel_id -> window start timestamp
        self._load_state()

    # ── 持久化 ───────────────────────────────────────────────

    def _load_state(self):
        if not STATE_FILE.exists():
            return
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._allocations = data.get("allocations", {})
            self._usage = data.get("usage", {})
            self._window_start = data.get("window_start", {})
        except Exception:
            pass

    def _save_state(self):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "allocations": self._allocations,
            "usage": self._usage,
            "window_start": self._window_start,
        }
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ── 窗口管理 ─────────────────────────────────────────────

    def _now(self) -> float:
        return time.time()

    def _ensure_window(self, channel_id: str):
        """确保 channel_id 处于当前有效窗口，自动重置过期窗口"""
        now = self._now()
        start = self._window_start.get(channel_id, now)
        if now - start >= RESET_INTERVAL:
            self._usage[channel_id] = 0.0
            self._window_start[channel_id] = now

    # ── 公开 API ─────────────────────────────────────────────

    def allocate(self, channel_id: str, quota: float) -> bool:
        """
        分配带宽配额。
        - channel_id: 通道标识
        - quota:      配额上限（单位/分钟）
        返回 True 表示分配成功。
        """
        with self._lock:
            self._allocations[channel_id] = quota
            self._ensure_window(channel_id)
            self._save_state()
            return True

    def check_quota(self, channel_id: str, size: float) -> tuple[bool, float]:
        """
        检查是否可发送，返回 (允许, 剩余配额)。
        - 窗口过期则自动重置后检查。
        - 不消耗配额，仅查询。
        """
        with self._lock:
            self._ensure_window(channel_id)
            limit = self._allocations.get(channel_id, DEFAULT_QUOTA)
            used = self._usage.get(channel_id, 0.0)
            remaining = max(0.0, limit - used)
            allowed = remaining >= size
            return allowed, remaining

    def consume(self, channel_id: str, size: float) -> float:
        """
        消费带宽，返回实际消耗量。
        - 若配额不足，按剩余配额实际消耗（部分消费）。
        - 若完全无配额，消费量为 0。
        """
        with self._lock:
            self._ensure_window(channel_id)
            limit = self._allocations.get(channel_id, DEFAULT_QUOTA)
            used = self._usage.get(channel_id, 0.0)
            remaining = max(0.0, limit - used)

            if size <= 0:
                return 0.0

            actual = min(size, remaining)
            self._usage[channel_id] = used + actual
            self._save_state()
            return actual

    def release(self, channel_id: str, size: float) -> float:
        """
        释放带宽，返回实际释放量（不超过已消费）。
        """
        with self._lock:
            self._ensure_window(channel_id)
            used = self._usage.get(channel_id, 0.0)
            actual = min(size, used)
            self._usage[channel_id] = used - actual
            self._save_state()
            return actual

    def reset_quota(self, channel_id: str):
        """重置配额（清零使用量，重置窗口）"""
        with self._lock:
            self._usage[channel_id] = 0.0
            self._window_start[channel_id] = self._now()
            self._save_state()

    def get_allocation(self, channel_id: str) -> dict:
        """返回配额分配详情"""
        with self._lock:
            self._ensure_window(channel_id)
            limit = self._allocations.get(channel_id, DEFAULT_QUOTA)
            used = self._usage.get(channel_id, 0.0)
            remaining = max(0.0, limit - used)
            window_start = self._window_start.get(channel_id, self._now())
            return {
                "channel_id": channel_id,
                "quota": limit,
                "used": used,
                "remaining": remaining,
                "default_quota": DEFAULT_QUOTA,
                "window_start": window_start,
            }


if __name__ == "__main__":
    import time as _time

    q = BandwidthQuota()

    # ── 1. 分配配额 ──────────────────────────────────────────
    print("=== 1. 分配配额 ===")
    q.allocate("channel-A", 1000)
    q.allocate("channel-B", 500)
    print(f"channel-A: {q.get_allocation('channel-A')}")
    print(f"channel-B: {q.get_allocation('channel-B')}")

    # ── 2. 消费并验证剩余 ────────────────────────────────────
    print("\n=== 2. 消费并验证剩余 ===")
    consumed = q.consume("channel-A", 300)
    allowed, remaining = q.check_quota("channel-A", 300)
    print(f"消费 300，实际消耗: {consumed}")
    print(f"检查 300，允许={allowed}, 剩余={remaining}")
    alloc = q.get_allocation("channel-A")
    print(f"剩余配额: {alloc['remaining']} / {alloc['quota']} (已用 {alloc['used']})")

    # ── 3. 超配额拒绝 ────────────────────────────────────────
    print("\n=== 3. 超配额拒绝 ===")
    allowed, remaining = q.check_quota("channel-A", 9999)
    print(f"请求 9999，允许={allowed}, 剩余={remaining}")
    consumed = q.consume("channel-A", 9999)
    print(f"请求 9999，实际消耗: {consumed} (应接近剩余配额)")
    print(f"超配额后 get_allocation: {q.get_allocation('channel-A')}")

    # ── 4. 重置验证 ──────────────────────────────────────────
    print("\n=== 4. 重置验证 ===")
    print(f"重置前 remaining: {q.get_allocation('channel-A')['remaining']}")
    q.reset_quota("channel-A")
    print(f"重置后 remaining: {q.get_allocation('channel-A')['remaining']}")
    assert q.get_allocation("channel-A")["remaining"] == 1000, "重置后应恢复到配额上限"
    print("重置验证通过 [OK]")

    print("\n=== 所有测试通过 [OK] ===")
