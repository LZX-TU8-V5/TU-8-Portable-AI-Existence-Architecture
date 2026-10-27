# -*- coding: utf-8 -*-
"""
补丁生命周期管理器 (PatchManager)

管理梦境/拓扑崩溃后的补丁生命周期，防止补丁反向劫持主系统。

状态路径:
  读取: _agent_memory/constraint_lifecycle_state.json
  写入: _agent_memory/patch_manager_state.json
  同步: anchor_state_machine (补丁卸载时)

Author: TU-8 Agent
"""

import json
import os
import time
import copy
import threading
from dataclasses import dataclass, field, asdict
from typing import Optional, Any
from enum import Enum


# ============================================================
# 常量定义
# ============================================================

PATCH_STAGES = {
    "GENERATION": {
        "name": "生成",
        "description": "补丁生成中，临时存在",
        "next": "BACKGROUND",
        "timeout": 7200,   # 2小时超时（秒）
        "flags": ["temporary", "isolated"]
    },
    "BACKGROUND": {
        "name": "背景板",
        "description": "补丁已整合为背景板，低优先级",
        "next": "PLACEHOLDER",
        "timeout": 86400,  # 24小时
        "flags": ["low_priority", "background"]
    },
    "PLACEHOLDER": {
        "name": "占位符",
        "description": "背景板合并为占位符",
        "next": "INTEGRATED",
        "timeout": None,   # 无超时
        "flags": ["minimal_resource"]
    },
    "INTEGRATED": {
        "name": "整合完成",
        "description": "补丁已完全整合到主拓扑",
        "next": None,
        "timeout": None,
        "flags": ["permanent", "merged"]
    },
    "CONFLICT": {
        "name": "冲突",
        "description": "补丁与其他补丁冲突",
        "next": "ROLLED_BACK",
        "timeout": 3600,   # 1小时人工审核
        "flags": ["isolated", "requires_review"]
    },
    "ROLLED_BACK": {
        "name": "已回滚",
        "description": "补丁已回滚，拓扑恢复",
        "next": None,
        "timeout": None,
        "flags": ["removed"]
    }
}

PRIORITY_RULES = {
    "CRITICAL_PATCH": 1,     # 安全类补丁
    "ANCHOR_PATCH": 2,       # 锚点类补丁
    "BACKGROUND_PATCH": 3,   # 背景板补丁
    "TEMP_PATCH": 4,         # 临时补丁
}

PATCH_TYPE_PRIORITY = {
    "critical": "CRITICAL_PATCH",
    "anchor": "ANCHOR_PATCH",
    "background": "BACKGROUND_PATCH",
    "temp": "TEMP_PATCH"
}

STATE_DIR = "_agent_memory"
CONSTRAINT_STATE_FILE = "constraint_lifecycle_state.json"
PATCH_STATE_FILE = "patch_manager_state.json"


# ============================================================
# 数据结构
# ============================================================

@dataclass
class Patch:
    """单个补丁对象"""
    patch_id: str
    patch_type: str = "temp"           # critical/anchor/background/temp
    target_topology: dict = field(default_factory=dict)
    patch_data: dict = field(default_factory=dict)
    stage: str = "GENERATION"
    stage_entered_at: float = field(default_factory=float)
    created_at: float = field(default_factory=float)
    priority: int = 4                   # 来自 PRIORITY_RULES
    conflict_with: list = field(default_factory=list)
    rollback_reason: str = ""
    merged_into: str = ""               # 被整合到哪个补丁
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Patch":
        return Patch(**d)


@dataclass
class PatchStageReport:
    """阶段推进报告"""
    patch_id: str
    previous_stage: str
    new_stage: str
    trigger: str
    timestamp: float
    message: str
    warnings: list = field(default_factory=list)


@dataclass
class PatchStats:
    """补丁统计"""
    total: int = 0
    by_stage: dict = field(default_factory=dict)
    integration_rate: float = 0.0       # INTEGRATED / total
    conflict_count: int = 0
    rolled_back_count: int = 0
    active_count: int = 0               # 非 ROLLED_BACK / INTEGRATED


# ============================================================
# PatchManager 主类
# ============================================================

class PatchManager:
    """
    补丁生命周期管理器

    管理梦境/拓扑崩溃后的补丁生命周期，防止补丁反向劫持主系统。
    """

    def __init__(self, workspace_root: Optional[str] = None):
        """
        初始化补丁状态机

        Args:
            workspace_root: 工作区根路径，默认使用当前工作目录
        """
        if workspace_root:
            self._root = workspace_root
        else:
            # 获取当前文件所在目录的父级（workspace）
            self._root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self._state_dir = os.path.join(self._root, STATE_DIR)
        self._constraint_path = os.path.join(self._state_dir, CONSTRAINT_STATE_FILE)
        self._patch_state_path = os.path.join(self._state_dir, PATCH_STATE_FILE)

        self._lock = threading.RLock()

        # 确保目录存在
        os.makedirs(self._state_dir, exist_ok=True)

        # 加载已有状态
        self._patches: dict[str, Patch] = {}
        self._load_state()

    # --------------------------------------------------------
    # 内部工具
    # --------------------------------------------------------

    def _load_state(self) -> None:
        """从磁盘加载补丁状态"""
        if os.path.exists(self._patch_state_path):
            try:
                with open(self._patch_state_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for pid, pdata in raw.get("patches", {}).items():
                    self._patches[pid] = Patch.from_dict(pdata)
            except (json.JSONDecodeError, KeyError, TypeError):
                self._patches = {}
        else:
            self._patches = {}

    def _save_state(self) -> None:
        """持久化补丁状态到磁盘"""
        with self._lock:
            raw = {
                "saved_at": time.time(),
                "patches": {pid: p.to_dict() for pid, p in self._patches.items()}
            }
            with open(self._patch_state_path, "w", encoding="utf-8") as f:
                json.dump(raw, f, ensure_ascii=False, indent=2)

    def _load_constraint_state(self) -> dict:
        """读取约束生命周期状态"""
        if os.path.exists(self._constraint_path):
            try:
                with open(self._constraint_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def _get_priority(self, patch_type: str) -> int:
        """根据补丁类型获取优先级数值"""
        key = PATCH_TYPE_PRIORITY.get(patch_type, "TEMP_PATCH")
        return PRIORITY_RULES.get(key, 4)

    def _check_timeout(self, patch: Patch) -> bool:
        """检查补丁是否超时"""
        stage_info = PATCH_STAGES.get(patch.stage, {})
        timeout = stage_info.get("timeout")
        if timeout is None:
            return False
        return (time.time() - patch.stage_entered_at) > timeout

    def _resolve_conflicts_on_create(self, patch: Patch) -> list[str]:
        """
        创建补丁时检测冲突，返回需要降级的补丁ID列表
        规则：优先级相同 + 作用于相同拓扑区域 → 冲突
        """
        victim_ids = []
        for existing in self._patches.values():
            if existing.patch_id == patch.patch_id:
                continue
            if existing.stage in ("ROLLED_BACK", "INTEGRATED"):
                continue

            # 检查是否作用在同一拓扑区域
            if self._topology_overlaps(patch.target_topology, existing.target_topology):
                # 优先级相同时，新补丁让位于已有补丁（防止频繁创建覆盖）
                if existing.priority <= patch.priority:
                    victim_ids.append(patch.patch_id)
                    break
                else:
                    # 已有补丁优先级更高，回滚已有补丁
                    victim_ids.append(existing.patch_id)

        return victim_ids

    def _topology_overlaps(self, t1: dict, t2: dict) -> bool:
        """检查两个拓扑区域是否有重叠"""
        if not t1 or not t2:
            return False
        # 以 target_keys 作为重叠判定
        keys1 = set(t1.get("target_keys", []))
        keys2 = set(t2.get("target_keys", []))
        if keys1 and keys2:
            return bool(keys1 & keys2)

        # 以 topology_id 判定
        return t1.get("topology_id") == t2.get("topology_id")

    def _call_anchor_state_machine(self, action: str, patch_id: str,
                                   patch_data: Optional[dict] = None) -> bool:
        """
        调用锚点状态机同步补丁卸载

        Args:
            action: "register" | "unregister" | "sync"
            patch_id: 补丁ID
            patch_data: 补丁数据

        Returns:
            是否调用成功
        """
        try:
            from anchor_state_machine import AnchorStateMachine
            anchor_sm = AnchorStateMachine()
            if action == "register":
                anchor_sm.register_patch(patch_id, patch_data or {})
                return True
            elif action == "unregister":
                anchor_sm.unregister_patch(patch_id)
                return True
            elif action == "sync":
                anchor_sm.sync_patch_state(patch_id, patch_data or {})
                return True
        except ImportError:
            pass
        except Exception:
            pass
        return False

    def _auto_check_timeouts(self) -> list[PatchStageReport]:
        """检查所有补丁超时，返回触发超时的补丁报告"""
        reports = []
        for patch in list(self._patches.values()):
            if patch.stage in ("ROLLED_BACK", "INTEGRATED"):
                continue
            if self._check_timeout(patch):
                # 自动推进到下一阶段
                report = self.advance_stage(patch.patch_id, trigger="timeout")
                reports.append(report)
        return reports

    # --------------------------------------------------------
    # 公开接口
    # --------------------------------------------------------

    def create_patch(self, patch_id: str, target_topology: dict,
                     patch_data: dict) -> str:
        """
        创建补丁，进入 GENERATION 阶段

        Args:
            patch_id: 补丁唯一标识
            target_topology: 目标拓扑（包含 topology_id, target_keys 等）
            patch_data: 补丁数据

        Returns:
            补丁ID（重复ID自动加后缀）
        """
        with self._lock:
            # 处理ID冲突
            original_id = patch_id
            counter = 1
            while patch_id in self._patches:
                patch_id = f"{original_id}_v{counter}"
                counter += 1

            patch_type = patch_data.get("patch_type", "temp")
            priority = self._get_priority(patch_type)
            now = time.time()

            patch = Patch(
                patch_id=patch_id,
                patch_type=patch_type,
                target_topology=target_topology,
                patch_data=patch_data,
                stage="GENERATION",
                stage_entered_at=now,
                created_at=now,
                priority=priority,
                metadata=patch_data.get("metadata", {})
            )

            self._patches[patch_id] = patch
            self._save_state()

            # 冲突检测
            victims = self._resolve_conflicts_on_create(patch)
            for vid in victims:
                self.rollback_patch(vid, reason="conflict_with_newer_patch")

            # 同步锚点状态机
            self._call_anchor_state_machine("register", patch_id, patch_data)

            return patch_id

    def get_patch(self, patch_id: str) -> Optional[dict]:
        """
        返回补丁状态

        Args:
            patch_id: 补丁ID

        Returns:
            补丁信息字典，不存在则返回 None
        """
        with self._lock:
            patch = self._patches.get(patch_id)
            if not patch:
                return None
            return patch.to_dict()

    def get_all_patches(self, stage_filter: Optional[str] = None) -> list:
        """
        返回所有补丁

        Args:
            stage_filter: 可选，按阶段过滤

        Returns:
            补丁列表
        """
        with self._lock:
            patches = list(self._patches.values())
            if stage_filter:
                patches = [p for p in patches if p.stage == stage_filter]
            return [p.to_dict() for p in patches]

    def advance_stage(self, patch_id: str, trigger: str) -> PatchStageReport:
        """
        推进补丁到下一阶段

        Args:
            patch_id: 补丁ID
            trigger: 触发器
                - "integration_complete": 整合完成
                - "timeout": 超时自动降级
                - "conflict_detected": 检测到冲突

        Returns:
            PatchStageReport 阶段推进报告

        Raises:
            ValueError: 补丁不存在或无法推进
        """
        with self._lock:
            patch = self._patches.get(patch_id)
            if not patch:
                raise ValueError(f"Patch not found: {patch_id}")

            prev_stage = patch.stage
            stage_info = PATCH_STAGES.get(prev_stage, {})

            # 特殊触发器处理
            if trigger == "conflict_detected":
                if prev_stage not in ("ROLLED_BACK", "INTEGRATED", "CONFLICT"):
                    patch.stage = "CONFLICT"
                    patch.stage_entered_at = time.time()
                    patch.conflict_with = patch_data.get("conflict_with", [])
                    self._save_state()
                    return PatchStageReport(
                        patch_id=patch_id,
                        previous_stage=prev_stage,
                        new_stage="CONFLICT",
                        trigger=trigger,
                        timestamp=time.time(),
                        message=f"补丁进入冲突状态，冲突对象: {patch.conflict_with}"
                    )

            # 检查是否有下一阶段
            next_stage = stage_info.get("next")
            if next_stage is None:
                return PatchStageReport(
                    patch_id=patch_id,
                    previous_stage=prev_stage,
                    new_stage=prev_stage,
                    trigger=trigger,
                    timestamp=time.time(),
                    message="补丁已达最终阶段，无法继续推进",
                    warnings=["already_final_stage"]
                )

            patch.stage = next_stage
            patch.stage_entered_at = time.time()
            self._save_state()

            return PatchStageReport(
                patch_id=patch_id,
                previous_stage=prev_stage,
                new_stage=next_stage,
                trigger=trigger,
                timestamp=time.time(),
                message=f"补丁从 {prev_stage} 推进到 {next_stage}",
                warnings=[]
            )

    def get_patch_stats(self) -> PatchStats:
        """
        返回补丁统计

        Returns:
            PatchStats 各阶段数量、总补丁数、整合率等
        """
        with self._lock:
            # 超时自动检查
            self._auto_check_timeouts()

            patches = list(self._patches.values())
            total = len(patches)
            by_stage = {}
            for stage_key in PATCH_STAGES:
                by_stage[stage_key] = sum(1 for p in patches if p.stage == stage_key)

            integrated = by_stage.get("INTEGRATED", 0)
            conflict = by_stage.get("CONFLICT", 0)
            rolled_back = by_stage.get("ROLLED_BACK", 0)
            active = total - rolled_back - integrated

            return PatchStats(
                total=total,
                by_stage=by_stage,
                integration_rate=(integrated / total) if total > 0 else 0.0,
                conflict_count=conflict,
                rolled_back_count=rolled_back,
                active_count=active
            )

    def rollback_patch(self, patch_id: str, reason: str) -> str:
        """
        回滚补丁

        Args:
            patch_id: 补丁ID
            reason: 回滚原因

        Returns:
            回滚后的阶段 "ROLLED_BACK"
        """
        with self._lock:
            patch = self._patches.get(patch_id)
            if not patch:
                return ""

            patch.stage = "ROLLED_BACK"
            patch.rollback_reason = reason
            patch.stage_entered_at = time.time()
            self._save_state()

            # 同步锚点状态机
            self._call_anchor_state_machine("unregister", patch_id)

            return "ROLLED_BACK"

    def merge_to_background(self, patch_id: str) -> str:
        """
        将补丁整合为背景板（进入 BACKGROUND 阶段）

        Args:
            patch_id: 补丁ID

        Returns:
            新阶段 "BACKGROUND"
        """
        with self._lock:
            patch = self._patches.get(patch_id)
            if not patch:
                return ""

            patch.stage = "BACKGROUND"
            patch.stage_entered_at = time.time()
            self._save_state()
            return "BACKGROUND"

    def demote_to_placeholder(self, patch_id: str) -> str:
        """
        将补丁降级为占位符（进入 PLACEHOLDER 阶段）

        Args:
            patch_id: 补丁ID

        Returns:
            新阶段 "PLACEHOLDER"
        """
        with self._lock:
            patch = self._patches.get(patch_id)
            if not patch:
                return ""

            patch.stage = "PLACEHOLDER"
            patch.stage_entered_at = time.time()
            self._save_state()
            return "PLACEHOLDER"

    def integrate_fully(self, patch_id: str) -> str:
        """
        完成补丁整合（进入 INTEGRATED 阶段）

        Args:
            patch_id: 补丁ID

        Returns:
            新阶段 "INTEGRATED"
        """
        with self._lock:
            patch = self._patches.get(patch_id)
            if not patch:
                return ""

            patch.stage = "INTEGRATED"
            patch.stage_entered_at = time.time()
            self._save_state()

            # 同步锚点状态机
            self._call_anchor_state_machine("sync", patch_id,
                                            {"stage": "INTEGRATED",
                                             "patch_data": patch.patch_data})

            return "INTEGRATED"

    def get_conflict_patches(self) -> list:
        """
        返回与其他补丁冲突的补丁列表

        Returns:
            CONFLICT 阶段的补丁列表
        """
        with self._lock:
            return [p.to_dict() for p in self._patches.values()
                    if p.stage == "CONFLICT"]

    def check_and_resolve_conflicts(self, patch_id: str) -> list[str]:
        """
        检测并解决补丁冲突，返回被降级的补丁ID列表

        Args:
            patch_id: 补丁ID

        Returns:
            被回滚的补丁ID列表
        """
        with self._lock:
            patch = self._patches.get(patch_id)
            if not patch:
                return []

            rolled_back_ids = []
            for existing in self._patches.values():
                if existing.patch_id == patch_id:
                    continue
                if existing.stage in ("ROLLED_BACK", "INTEGRATED"):
                    continue

                if self._topology_overlaps(patch.target_topology,
                                           existing.target_topology):
                    if existing.priority <= patch.priority:
                        # 新补丁存活，已有补丁回滚
                        self.rollback_patch(existing.patch_id,
                                           f"conflict_with_{patch_id}")
                        rolled_back_ids.append(existing.patch_id)
                    else:
                        # 已有补丁优先级更高
                        if patch.stage != "CONFLICT":
                            patch.stage = "CONFLICT"
                            patch.conflict_with.append(existing.patch_id)
                            patch.stage_entered_at = time.time()

            if rolled_back_ids or patch.conflict_with:
                self._save_state()

            return rolled_back_ids

    def get_topology_coverage(self) -> dict:
        """
        获取拓扑覆盖情况（用于可视化）

        Returns:
            拓扑区域到补丁的映射
        """
        with self._lock:
            coverage = {}
            for patch in self._patches.values():
                if patch.stage in ("ROLLED_BACK",):
                    continue
                topo_id = patch.target_topology.get("topology_id", "unknown")
                if topo_id not in coverage:
                    coverage[topo_id] = []
                coverage[topo_id].append({
                    "patch_id": patch.patch_id,
                    "stage": patch.stage,
                    "priority": patch.priority
                })
            return coverage


# ============================================================
# 验证测试
# ============================================================

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("PatchManager 验证测试")
    print("=" * 60)

    # 使用临时目录进行测试
    import tempfile
    test_root = tempfile.mkdtemp(prefix="patchmgr_test_")
    print(f"测试工作目录: {test_root}")

    pm = PatchManager(workspace_root=test_root)

    # ------ 测试1：补丁生成→背景板→占位符→整合 ------
    print("\n[测试1] 补丁生命周期流转")
    print("-" * 40)

    patch_id = pm.create_patch(
        patch_id="patch_001",
        target_topology={"topology_id": "dream_v1", "target_keys": ["memory", "context"]},
        patch_data={"patch_type": "anchor", "content": "锚点修复"}
    )
    print(f"创建补丁: {patch_id}")

    p = pm.get_patch(patch_id)
    print(f"  阶段: {p['stage']}")

    # 推进到背景板
    r = pm.advance_stage(patch_id, trigger="integration_complete")
    print(f"  推进: {r.previous_stage} → {r.new_stage}")

    # 推进到占位符
    r = pm.advance_stage(patch_id, trigger="integration_complete")
    print(f"  推进: {r.previous_stage} → {r.new_stage}")

    # 推进到整合完成
    r = pm.advance_stage(patch_id, trigger="integration_complete")
    print(f"  推进: {r.previous_stage} → {r.new_stage}")

    # ------ 测试2：冲突检测与回滚 ------
    print("\n[测试2] 冲突检测与回滚")
    print("-" * 40)

    # 创建两个优先级相同的补丁作用于同一区域
    pid_a = pm.create_patch(
        patch_id="conflict_a",
        target_topology={"topology_id": "dream_v2", "target_keys": ["memory"]},
        patch_data={"patch_type": "temp"}
    )
    pid_b = pm.create_patch(
        patch_id="conflict_b",
        target_topology={"topology_id": "dream_v2", "target_keys": ["memory"]},
        patch_data={"patch_type": "temp"}
    )
    print(f"补丁A: {pid_a}")
    print(f"补丁B: {pid_b}")

    p_a = pm.get_patch(pid_a)
    p_b = pm.get_patch(pid_b)
    print(f"  A 阶段: {p_a['stage']}, B 阶段: {p_b['stage']}")

    conflicts = pm.get_conflict_patches()
    print(f"  冲突补丁数量: {len(conflicts)}")

    # ------ 测试3：优先级差异 - 高优先级存活 ------
    print("\n[测试3] 优先级差异处理")
    print("-" * 40)

    pid_critical = pm.create_patch(
        patch_id="critical_fix",
        target_topology={"topology_id": "dream_v3", "target_keys": ["security"]},
        patch_data={"patch_type": "critical"}
    )
    pid_temp = pm.create_patch(
        patch_id="temp_fix",
        target_topology={"topology_id": "dream_v3", "target_keys": ["security"]},
        patch_data={"patch_type": "temp"}
    )

    c = pm.get_patch(pid_critical)
    t = pm.get_patch(pid_temp)
    print(f"  关键补丁优先级: {c['priority']}")
    print(f"  临时补丁优先级: {t['priority']}")
    print(f"  关键补丁阶段: {c['stage']}")
    print(f"  临时补丁阶段: {t['stage']}")

    # ------ 统计 ------
    print("\n[统计]")
    print("-" * 40)
    stats = pm.get_patch_stats()
    print(f"  总补丁数: {stats.total}")
    print(f"  各阶段: {stats.by_stage}")
    print(f"  整合率: {stats.integration_rate:.1%}")
    print(f"  活跃补丁: {stats.active_count}")

    # ------ 拓扑覆盖 ------
    print("\n[拓扑覆盖]")
    print("-" * 40)
    coverage = pm.get_topology_coverage()
    for topo_id, patches in coverage.items():
        print(f"  {topo_id}: {len(patches)} 个补丁")

    print("\n" + "=" * 60)
    print("所有测试完成!")
    print("=" * 60)

    # 清理测试目录
    import shutil
    shutil.rmtree(test_root, ignore_errors=True)
