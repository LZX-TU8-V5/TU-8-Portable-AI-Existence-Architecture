"""
锚点状态机（Anchor State Machine）
=====================================
统一管理所有锚点的生命周期状态转换、能量衰减与深层存储迁移。

状态定义
--------
ACTIVATED   激活态：锚点活跃，可被调用，不衰减
HIBERNATED  休眠态：低功耗，依赖衰减（每小时-10%）
UNLOADED    卸载态：从索引移除，等待整合，暂停衰减
CONSOLIDATED固化态：补丁整合完成，成为背景板（桩实现）

集成
----
- 读取: secure_vault/index.json（深层锚点索引）
- 写入: _agent_memory/anchor_state.json（锚点状态快照）
- 调用: topology_thermal_monitor（卸载建议时调用）
- 触发: constraint_lifecycle（节点卸载时同步）

创建时间: 2026-07-19
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── 路径配置 ────────────────────────────────────────────────────────────────

WORKSPACE = Path("C:/Users/qq366410837/.qclaw/workspace")
AGENT_MEM = WORKSPACE / "_agent_memory"
SECURE_VAULT = WORKSPACE / "secure_vault"
STATE_FILE = AGENT_MEM / "anchor_state.json"
VAULT_INDEX = SECURE_VAULT / "index.json"

# ── 四状态定义 ──────────────────────────────────────────────────────────────

ANCHOR_STATES: dict = {
    "ACTIVATED": {
        "name": "激活",
        "description": "锚点活跃，可被调用",
        "energy_decay_rate": 0.0,        # 已加固，不衰减
        "flags": ["callable", "indexed"],
    },
    "HIBERNATED": {
        "name": "休眠",
        "description": "锚点低功耗，依赖衰减",
        "energy_decay_rate": 0.1,        # 每小时衰减10%
        "flags": ["callable", "slow_index"],
    },
    "UNLOADED": {
        "name": "卸载",
        "description": "锚点从索引移除，等待整合",
        "energy_decay_rate": 0.0,        # 暂停衰减
        "flags": ["uncallable"],
    },
    "CONSOLIDATED": {
        "name": "固化",
        "description": "补丁整合完成，成为背景板",
        "energy_decay_rate": 0.0,        # 不衰减
        "flags": ["callable", "low_resource", "integrated"],
    },
}

# 有效状态列表
VALID_STATES = list(ANCHOR_STATES.keys())

# 衰减触发阈值
ENERGY_HIBERNATE_THRESHOLD = 0.1   # 能量低于此值 → 自动卸载
ENERGY_UNREINFORCED_DECAY = 0.95   # 未加固的ACTIVATED锚点每次衰减
HALF_LIFE_DAYS = 14                # 半衰期（天）

# ── 数据模型 ────────────────────────────────────────────────────────────────


@dataclass
class AnchorState:
    """单个锚点的状态快照"""

    anchor_id: str
    state: str = "ACTIVATED"          # ACTIVATED | HIBERNATED | UNLOADED | CONSOLIDATED
    energy: float = 1.0               # 0.0 ~ 1.0
    priority: int = 5                 # 1(高) ~ 10(低)
    topology: dict = field(default_factory=dict)   # 关联拓扑信息
    created_at: str = ""              # ISO timestamp
    last_reinforced_at: str = ""      # ISO timestamp
    last_decay_at: str = ""           # ISO timestamp
    reinforced_recently: bool = True  # 是否近期被加固
    history: list = field(default_factory=list)   # 状态转换历史
    vault_id: str = ""                # secure_vault 条目ID（迁移后）
    in_vault: bool = False            # 是否已在深层存储

    def to_dict(self) -> dict:
        d = asdict(self)
        d["_class"] = "AnchorState"
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "AnchorState":
        d = {k: v for k, v in d.items() if k != "_class"}
        return cls(**d)

    def add_history(self, event: str, from_state: str = "", to_state: str = "", reason: str = ""):
        """追加状态转换历史"""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "from": from_state,
            "to": to_state,
            "reason": reason,
            "energy": self.energy,
        }
        self.history.append(entry)
        # 最多保留 50 条历史
        if len(self.history) > 50:
            self.history = self.history[-50:]


# ── 报告模型 ────────────────────────────────────────────────────────────────


@dataclass
class DecayReport:
    """衰减报告"""
    decayed_count: int
    unloaded_count: int       # 能量耗尽自动卸载的数量
    still_active: int
    timestamp: str
    details: list = field(default_factory=list)  # [(anchor_id, old_energy, new_energy), ...]


@dataclass
class PruneReport:
    """剪枝报告"""
    pruned_count: int
    pruned_ids: list
    timestamp: str


@dataclass
class AnchorStats:
    """锚点统计"""
    total: int
    by_state: dict            # {"ACTIVATED": N, "HIBERNATED": N, ...}
    avg_energy: float
    callable_count: int
    in_vault_count: int
    timestamp: str


# ── 异常 ────────────────────────────────────────────────────────────────────


class AnchorStateMachineError(Exception):
    """锚点状态机异常"""
    pass


class InvalidStateTransition(AnchorStateMachineError):
    """非法状态转换"""
    pass


# ── 核心状态机 ──────────────────────────────────────────────────────────────


class AnchorStateMachine:
    """
    锚点状态机

    统一管理所有锚点的生命周期状态转换、能量衰减与深层存储迁移。
    """

    def __init__(self, workspace_path: Optional[str] = None):
        self.workspace_path = Path(workspace_path) if workspace_path else WORKSPACE
        self.agent_mem = self.workspace_path / "_agent_memory"
        self.secure_vault = self.workspace_path / "secure_vault"
        self.state_file = self.agent_mem / "anchor_state.json"
        self.vault_index = self.secure_vault / "index.json"

        self.anchors: dict[str, AnchorState] = {}   # anchor_id → AnchorState
        self._initialized = False

        # 初始化
        self._ensure_dirs()
        self._load()
        self._load_vault_index()

        self._initialized = True
        logging.info(f"AnchorStateMachine 初始化完成，共 {len(self.anchors)} 个锚点")

    # ── 路径与初始化 ────────────────────────────────────────────────────────

    def _ensure_dirs(self):
        self.agent_mem.mkdir(parents=True, exist_ok=True)
        self.secure_vault.mkdir(parents=True, exist_ok=True)

    def _state_file_path(self) -> Path:
        return self.state_file

    def _vault_index_path(self) -> Path:
        return self.vault_index

    # ── 持久化 ───────────────────────────────────────────────────────────────

    def _load(self):
        """从 _agent_memory/anchor_state.json 加载状态"""
        if not self.state_file.exists():
            self.anchors = {}
            return

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.anchors = {}
            for anchor_d in data.get("anchors", []):
                anchor = AnchorState.from_dict(anchor_d)
                self.anchors[anchor.anchor_id] = anchor

            logging.info(f"从 {self.state_file} 加载了 {len(self.anchors)} 个锚点状态")

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logging.warning(f"加载锚点状态失败，使用空状态: {e}")
            self.anchors = {}

    def _save(self):
        """保存状态到 _agent_memory/anchor_state.json"""
        if not self._initialized:
            return  # 防止 __init__ 期间重复写入

        data = {
            "version": "1.0",
            "updated": datetime.now(timezone.utc).isoformat(),
            "anchors": [anchor.to_dict() for anchor in self.anchors.values()],
        }

        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"保存锚点状态失败: {e}")

    def _load_vault_index(self):
        """加载 secure_vault/index.json 作为深层锚点索引（只读）"""
        self._vault_entries: dict[str, dict] = {}
        if not self.vault_index.exists():
            return

        try:
            with open(self.vault_index, "r", encoding="utf-8") as f:
                data = json.load(f)

            for entry in data.get("entries", []):
                eid = entry.get("id", "")
                if eid:
                    self._vault_entries[eid] = entry

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logging.warning(f"加载 secure_vault/index.json 失败: {e}")
            self._vault_entries = {}

    # ── 基础查询 ─────────────────────────────────────────────────────────────

    def get_anchor(self, anchor_id: str) -> Optional[AnchorState]:
        """返回锚点状态（不存在返回 None）"""
        return self.anchors.get(anchor_id)

    def get_all_anchors(self, state_filter: Optional[str] = None) -> list[AnchorState]:
        """返回所有锚点，可按状态过滤"""
        anchors = list(self.anchors.values())
        if state_filter is not None:
            anchors = [a for a in anchors if a.state == state_filter]
        return anchors

    def get_anchor_stats(self) -> AnchorStats:
        """返回锚点统计"""
        by_state = {s: 0 for s in VALID_STATES}
        callable_count = 0
        in_vault_count = 0
        total_energy = 0.0

        for anchor in self.anchors.values():
            by_state[anchor.state] = by_state.get(anchor.state, 0) + 1
            total_energy += anchor.energy
            if "callable" in ANCHOR_STATES.get(anchor.state, {}).get("flags", []):
                callable_count += 1
            if anchor.in_vault:
                in_vault_count += 1

        total = len(self.anchors)
        avg_energy = total_energy / total if total > 0 else 0.0

        return AnchorStats(
            total=total,
            by_state=by_state,
            avg_energy=round(avg_energy, 4),
            callable_count=callable_count,
            in_vault_count=in_vault_count,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def get_energy_low_anchors(self, threshold: float = 0.1) -> list[AnchorState]:
        """返回能量低于阈值的锚点"""
        return [a for a in self.anchors.values() if a.energy < threshold]

    # ── 注册与状态转换 ────────────────────────────────────────────────────────

    def register_anchor(
        self,
        anchor_id: str,
        topology: Optional[dict] = None,
        priority: int = 5,
        initial_energy: float = 1.0,
    ) -> str:
        """
        注册新锚点，自动进入 ACTIVATED 状态。

        Returns:
            anchor_id（如果 anchor_id 已存在，返回现有ID，不重复注册）
        """
        if anchor_id in self.anchors:
            logging.info(f"锚点已存在: {anchor_id}")
            return anchor_id

        now = datetime.now(timezone.utc).isoformat()
        anchor = AnchorState(
            anchor_id=anchor_id,
            state="ACTIVATED",
            energy=initial_energy,
            priority=priority,
            topology=topology or {},
            created_at=now,
            last_reinforced_at=now,
            last_decay_at=now,
            reinforced_recently=True,
            history=[],
        )
        anchor.add_history("注册", to_state="ACTIVATED")

        self.anchors[anchor_id] = anchor
        self._save()
        logging.info(f"锚点注册: {anchor_id} → ACTIVATED")
        return anchor_id

    def activate_anchor(self, anchor_id: str) -> str:
        """
        激活锚点（HIBERNATED → ACTIVATED 或 UNLOADED → ACTIVATED）

        不允许: CONSOLIDATED → ACTIVATED（固化锚点不可回退）
        """
        anchor = self.anchors.get(anchor_id)
        if anchor is None:
            raise AnchorStateMachineError(f"锚点不存在: {anchor_id}")

        if anchor.state == "ACTIVATED":
            return anchor.state

        if anchor.state in ("CONSOLIDATED", "UNLOADED"):
            raise InvalidStateTransition(
                f"锚点 {anchor_id} 处于 {anchor.state} 态，不可直接激活"
            )

        if anchor.state != "HIBERNATED":
            raise InvalidStateTransition(
                f"锚点 {anchor_id} 处于 {anchor.state} 态，无法激活"
            )

        from_state = anchor.state
        anchor.state = "ACTIVATED"
        anchor.reinforced_recently = True
        anchor.last_reinforced_at = datetime.now(timezone.utc).isoformat()
        anchor.add_history("激活", from_state=from_state, to_state="ACTIVATED")
        self._save()
        logging.info(f"锚点激活: {anchor_id} {from_state} → ACTIVATED")
        return anchor.state

    def hibernate_anchor(self, anchor_id: str, reason: str = "") -> str:
        """
        休眠锚点（ACTIVATED → HIBERNATED）

        不允许: UNLOADED / CONSOLIDATED → HIBERNATED
        """
        anchor = self.anchors.get(anchor_id)
        if anchor is None:
            raise AnchorStateMachineError(f"锚点不存在: {anchor_id}")

        if anchor.state == "HIBERNATED":
            return anchor.state

        if anchor.state in ("UNLOADED", "CONSOLIDATED"):
            raise InvalidStateTransition(
                f"锚点 {anchor_id} 处于 {anchor.state} 态，不可休眠"
            )

        from_state = anchor.state
        anchor.state = "HIBERNATED"
        anchor.add_history("休眠", from_state=from_state, to_state="HIBERNATED", reason=reason)
        self._save()
        logging.info(f"锚点休眠: {anchor_id} {from_state} → HIBERNATED | reason={reason}")
        return anchor.state

    def unload_anchor(self, anchor_id: str, reason: str = "") -> str:
        """
        卸载锚点（ACTIVATED/HIBERNATED → UNLOADED）

        卸载后锚点不可被调用，等待整合或固化。
        """
        anchor = self.anchors.get(anchor_id)
        if anchor is None:
            raise AnchorStateMachineError(f"锚点不存在: {anchor_id}")

        if anchor.state == "UNLOADED":
            return anchor.state

        if anchor.state == "CONSOLIDATED":
            raise InvalidStateTransition(
                f"锚点 {anchor_id} 已固化(CONSOLIDATED)，不可卸载"
            )

        from_state = anchor.state
        anchor.state = "UNLOADED"
        anchor.add_history("卸载", from_state=from_state, to_state="UNLOADED", reason=reason)
        self._save()
        logging.info(f"锚点卸载: {anchor_id} {from_state} → UNLOADED | reason={reason}")
        return anchor.state

    def consolidate_anchor(self, anchor_id: str) -> str:
        """
        固化锚点（UNLOADED → CONSOLIDATED）

        补丁整合完成，锚点成为背景板。
        CONSOLIDATED 为桩实现：仅记录状态，不做真实补丁整合。
        """
        anchor = self.anchors.get(anchor_id)
        if anchor is None:
            raise AnchorStateMachineError(f"锚点不存在: {anchor_id}")

        if anchor.state == "CONSOLIDATED":
            return anchor.state

        if anchor.state != "UNLOADED":
            raise InvalidStateTransition(
                f"锚点 {anchor_id} 处于 {anchor.state} 态，必须先卸载才能固化"
            )

        from_state = anchor.state
        anchor.state = "CONSOLIDATED"
        anchor.add_history("固化整合", from_state=from_state, to_state="CONSOLIDATED")
        self._save()
        logging.info(f"锚点固化: {anchor_id} {from_state} → CONSOLIDATED")
        return anchor.state

    # ── 遗忘衰减 ────────────────────────────────────────────────────────────

    def apply_decay(self) -> DecayReport:
        """
        应用遗忘衰减（周期性调用，建议每小时一次）

        规则:
        1. HIBERNATED 锚点按 energy_decay_rate 衰减
        2. 能量低于阈值 → 自动卸载
        3. ACTIVATED 锚点未加固 → 轻微衰减 (0.95)
        """
        decayed_count = 0
        unloaded_count = 0
        details: list = []          # [(anchor_id, old_e, new_e), ...]
        now = datetime.now(timezone.utc).isoformat()

        for anchor in self.anchors.values():
            old_energy = anchor.energy
            changed = False

            if anchor.state == "HIBERNATED":
                decay_rate = ANCHOR_STATES["HIBERNATED"]["energy_decay_rate"]
                anchor.energy = max(0.0, anchor.energy * (1 - decay_rate))
                changed = anchor.energy != old_energy

                # 能量耗尽 → 自动卸载
                if anchor.energy < ENERGY_HIBERNATE_THRESHOLD:
                    from_state = anchor.state
                    anchor.state = "UNLOADED"
                    anchor.add_history(
                        "衰减自动卸载",
                        from_state=from_state,
                        to_state="UNLOADED",
                        reason=f"能量耗尽({anchor.energy:.4f} < {ENERGY_HIBERNATE_THRESHOLD})"
                    )
                    unloaded_count += 1
                    logging.warning(
                        f"锚点能量耗尽自动卸载: {anchor.anchor_id} energy={anchor.energy:.4f}"
                    )

            elif anchor.state == "ACTIVATED" and not anchor.reinforced_recently:
                # 未加固的ACTIVATED锚点轻微衰减
                anchor.energy = max(0.0, anchor.energy * ENERGY_UNREINFORCED_DECAY)
                changed = anchor.energy != old_energy

            anchor.last_decay_at = now

            if changed:
                decayed_count += 1
                details.append((anchor.anchor_id, round(old_energy, 4), round(anchor.energy, 4)))

        self._save()

        report = DecayReport(
            decayed_count=decayed_count,
            unloaded_count=unloaded_count,
            still_active=sum(1 for a in self.anchors.values() if a.state == "ACTIVATED"),
            timestamp=now,
            details=details,
        )

        logging.info(
            f"遗忘衰减完成: 衰减{decayed_count}个, 自动卸载{unloaded_count}个, "
            f"仍激活{report.still_active}个"
        )
        return report

    # ── 剪枝 ────────────────────────────────────────────────────────────────

    def prune_energy_depleted(self, threshold: float = 0.0) -> PruneReport:
        """
        剪枝能量耗尽的锚点（能量 ≤ threshold）

        默认 threshold=0.0 表示彻底耗尽。
        """
        pruned_ids = []
        for anchor_id, anchor in list(self.anchors.items()):
            if anchor.energy <= threshold and anchor.state in ("HIBERNATED", "UNLOADED"):
                anchor.add_history("剪枝", reason=f"能量耗尽({anchor.energy})")
                del self.anchors[anchor_id]
                pruned_ids.append(anchor_id)

        self._save()
        logging.info(f"剪枝完成: 移除{len(pruned_ids)}个能量耗尽锚点")
        return PruneReport(
            pruned_count=len(pruned_ids),
            pruned_ids=pruned_ids,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # ── 深层存储迁移 ────────────────────────────────────────────────────────

    def migrate_to_secure_vault(self, anchor_id: str) -> str:
        """
        将锚点迁移到 secure_vault（深层存储）

        实现:
        1. 将锚点信息写入 secure_vault/anchors/{anchor_id}.json
        2. 在 vault_index.json 中添加条目
        3. 标记 anchor_state.json 中的 in_vault=True, vault_id
        """
        anchor = self.anchors.get(anchor_id)
        if anchor is None:
            raise AnchorStateMachineError(f"锚点不存在: {anchor_id}")

        if anchor.in_vault:
            return anchor.vault_id

        vault_dir = self.secure_vault / "anchors"
        vault_dir.mkdir(parents=True, exist_ok=True)

        vault_file = vault_dir / f"{anchor_id}.json"
        with open(vault_file, "w", encoding="utf-8") as f:
            json.dump(anchor.to_dict(), f, indent=2, ensure_ascii=False)

        # 更新 vault_index
        self._load_vault_index()
        vault_entry = {
            "id": anchor_id,
            "path": f"./anchors/{anchor_id}.json",
            "state": anchor.state,
            "energy": anchor.energy,
            "priority": anchor.priority,
            "migrated_at": datetime.now(timezone.utc).isoformat(),
            "role": "L0_retrieval",
            "category": "anchor",
            "tags": ["锚点", anchor.state],
            "hit_count": 0,
            "last_access": None,
            "confidence_score": anchor.energy,
        }

        all_entries = []
        if self.vault_index.exists():
            try:
                with open(self.vault_index, "r", encoding="utf-8") as f:
                    index_data = json.load(f)
                all_entries = index_data.get("entries", [])
            except Exception:
                all_entries = []

        # 替换或追加
        replaced = False
        for i, e in enumerate(all_entries):
            if e.get("id") == anchor_id:
                all_entries[i] = vault_entry
                replaced = True
                break
        if not replaced:
            all_entries.append(vault_entry)

        with open(self.vault_index, "w", encoding="utf-8") as f:
            json.dump({"version": "2.0-redesign", "entries": all_entries}, f, indent=2, ensure_ascii=False)

        anchor.in_vault = True
        anchor.vault_id = anchor_id
        anchor.add_history("迁移到深层存储")
        self._save()

        logging.info(f"锚点迁移到 secure_vault: {anchor_id}")
        return anchor_id

    def restore_from_secure_vault(self, anchor_id: str) -> str:
        """
        从 secure_vault 恢复锚点到主状态文件

        实现:
        1. 从 vault_file 读取锚点数据
        2. 更新 anchor_state.json
        3. 不删除 vault 中的备份（保留备份）
        """
        vault_dir = self.secure_vault / "anchors"
        vault_file = vault_dir / f"{anchor_id}.json"

        if not vault_file.exists():
            raise AnchorStateMachineError(f"secure_vault 中未找到锚点: {anchor_id}")

        with open(vault_file, "r", encoding="utf-8") as f:
            anchor_d = json.load(f)

        anchor = AnchorState.from_dict(anchor_d)
        anchor.in_vault = False
        anchor.add_history("从深层存储恢复")

        self.anchors[anchor_id] = anchor
        self._save()

        logging.info(f"从 secure_vault 恢复锚点: {anchor_id}")
        return anchor.state

    # ── 辅助方法 ────────────────────────────────────────────────────────────

    def reinforce_anchor(self, anchor_id: str, energy_boost: float = 0.1) -> float:
        """
        加固锚点（补充能量，标记为近期加固）

        Returns:
            加固后的能量值
        """
        anchor = self.anchors.get(anchor_id)
        if anchor is None:
            raise AnchorStateMachineError(f"锚点不存在: {anchor_id}")

        anchor.energy = min(1.0, anchor.energy + energy_boost)
        anchor.reinforced_recently = True
        anchor.last_reinforced_at = datetime.now(timezone.utc).isoformat()
        self._save()
        return anchor.energy

    def reset_reinforced_flag(self):
        """
        重置所有锚点的 reinforced_recently 标志

        每次 apply_decay 周期开始时调用，使未及时加固的锚点进入衰减流程。
        """
        for anchor in self.anchors.values():
            anchor.reinforced_recently = False

    def clear_anchor(self, anchor_id: str) -> bool:
        """删除锚点（彻底移除）"""
        if anchor_id in self.anchors:
            del self.anchors[anchor_id]
            self._save()
            logging.info(f"删除锚点: {anchor_id}")
            return True
        return False

    def to_dict(self) -> dict:
        """导出完整状态（供外部快照）"""
        return {
            "version": "1.0",
            "updated": datetime.now(timezone.utc).isoformat(),
            "stats": asdict(self.get_anchor_stats()),
            "anchors": [anchor.to_dict() for anchor in self.anchors.values()],
        }


# ── 验证测试 ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile
    import shutil

    print("=" * 60)
    print("AnchorStateMachine 验证测试")
    print("=" * 60)

    # ── 测试1：注册并激活锚点 ───────────────────────────────────────────────
    print("\n【测试1】注册并激活锚点")
    tmpdir = tempfile.mkdtemp()
    try:
        asm = AnchorStateMachine(workspace_path=tmpdir)

        aid = asm.register_anchor("test_anchor_001", {"type": "insight"}, priority=3)
        print(f"  注册 → anchor_id={aid}")
        assert asm.get_anchor("test_anchor_001").state == "ACTIVATED"

        # 激活已有锚点（已是ACTIVATED）
        state = asm.activate_anchor("test_anchor_001")
        print(f"  激活 → state={state}")
        assert state == "ACTIVATED"

        # 再次注册同一锚点 → 返回现有ID
        aid2 = asm.register_anchor("test_anchor_001", {"type": "insight"})
        assert aid2 == "test_anchor_001"
        print(f"  重复注册 → anchor_id={aid2} (不重复)")

        print("  ✅ 测试1通过")

        # ── 测试2：休眠 → 卸载转换 ─────────────────────────────────────────
        print("\n【测试2】休眠→卸载转换")
        aid2_id = asm.register_anchor("test_anchor_002")
        asm.hibernate_anchor("test_anchor_002", reason="张力超限")
        assert asm.get_anchor("test_anchor_002").state == "HIBERNATED"
        print(f"  休眠 → HIBERNATED")

        asm.unload_anchor("test_anchor_002", reason="等待整合")
        assert asm.get_anchor("test_anchor_002").state == "UNLOADED"
        print(f"  卸载 → UNLOADED")

        # UNLOADED → ACTIVATED 应抛异常（必须走合规流程）
        try:
            asm.activate_anchor("test_anchor_002")
            assert False, "应抛出 InvalidStateTransition"
        except InvalidStateTransition as e:
            print(f"  非法激活 → 正确抛出: {e}")

        print("  ✅ 测试2通过")

        # ── 测试3：遗忘衰减 ────────────────────────────────────────────────
        print("\n【测试3】遗忘衰减")
        aid3 = asm.register_anchor("test_anchor_003", priority=5)
        asm.hibernate_anchor("test_anchor_003", reason="测试衰减")
        orig_energy = asm.get_anchor("test_anchor_003").energy
        print(f"  休眠态能量: {orig_energy:.4f}")

        # 重置加固标志 → 进入衰减路径
        asm.reset_reinforced_flag()
        report = asm.apply_decay()
        new_energy = asm.get_anchor("test_anchor_003").energy
        print(f"  衰减后能量: {new_energy:.4f} (decayed={report.decayed_count}, unloaded={report.unloaded_count})")
        assert new_energy < orig_energy, "休眠锚点能量应下降"
        assert report.decayed_count >= 1

        print("  ✅ 测试3通过")

        # ── 测试4：固化整合 ────────────────────────────────────────────────
        print("\n【测试4】固化整合（桩实现）")
        aid4 = asm.register_anchor("test_anchor_004")
        asm.unload_anchor("test_anchor_004", reason="待整合")
        state = asm.consolidate_anchor("test_anchor_004")
        assert state == "CONSOLIDATED"
        print(f"  卸载→固化: {state}")

        # CONSOLIDATED 不可再卸载
        try:
            asm.unload_anchor("test_anchor_004")
            assert False, "CONSOLDATED不应再卸载"
        except InvalidStateTransition:
            print("  CONSOLIDATED不可卸载 → 正确拒绝")

        print("  ✅ 测试4通过")

        # ── 测试5：统计与查询 ──────────────────────────────────────────────
        print("\n【测试5】统计与查询")
        stats = asm.get_anchor_stats()
        print(f"  总锚点: {stats.total}")
        print(f"  状态分布: {stats.by_state}")
        print(f"  平均能量: {stats.avg_energy}")
        print(f"  可调用: {stats.callable_count}")

        all_act = asm.get_all_anchors(state_filter="ACTIVATED")
        print(f"  ACTIVATED锚点: {len(all_act)}个")

        print("  ✅ 测试5通过")

        # ── 测试6：深层存储迁移 ─────────────────────────────────────────────
        print("\n【测试6】深层存储迁移")
        aid5 = asm.register_anchor("test_anchor_005")
        vault_id = asm.migrate_to_secure_vault("test_anchor_005")
        assert vault_id == "test_anchor_005"
        assert asm.get_anchor("test_anchor_005").in_vault is True
        print(f"  迁移成功 → in_vault=True")

        state = asm.restore_from_secure_vault("test_anchor_005")
        assert state == "ACTIVATED"
        print(f"  恢复成功 → state={state}")

        print("  ✅ 测试6通过")

        # ── 测试7：能量低锚点查询 ──────────────────────────────────────────
        print("\n【测试7】能量低锚点查询")
        # 将一个锚点能量强制设为低
        asm.get_anchor("test_anchor_003").energy = 0.05
        low = asm.get_energy_low_anchors(threshold=0.1)
        print(f"  能量<0.1的锚点: {[a.anchor_id for a in low]}")
        assert len(low) >= 1

        print("  ✅ 测试7通过")

        print("\n" + "=" * 60)
        print("全部测试通过！✅")
        print("=" * 60)

    finally:
        shutil.rmtree(tmpdir)
