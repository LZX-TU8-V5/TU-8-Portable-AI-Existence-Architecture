# -*- coding: utf-8 -*-
"""
cognitive_readiness.py — TU-8 认知就绪度评估器 v1.1
日期: 2026-06-05
# 创作者: 李奥(金木蟾) | TU-8 v5

变更日志 (v1.1):
  [OK] Q9-P0→P3 渐进映射: readiness_score → 四级深度连续映射
  [OK] 草稿残影增强: WorkingMemoryShadow 保存最近消息+活跃文件+状态
  [OK] 工作区哈希增强: 对关键文件内容取 SHA-256，而非仅目录名
  [OK] 对话密度感知: 新增 probe_conversation_density（近期交互频率）
  [OK] 认知负荷评估: 新增 probe_cognitive_load（待办数×未完成草稿长度）

架构定位:
  ColdStartEngine.Phase 2b 的核心评估器
  输出: readiness_score(0-1) + P0-P3 depth level + activation_cues
"""

import json
import hashlib
import os
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, List
from enum import Enum

logger = logging.getLogger(__name__)

# Windows 编码修复
if sys.platform == 'win32':
    import codecs
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = codecs.getwriter('gbk')(sys.stdout.buffer, errors='replace')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = codecs.getwriter('gbk')(sys.stderr.buffer, errors='replace')

# =============================================================================
# 路径配置
# =============================================================================

WORKSPACE_D = r"C:\Users\qq366410837\.qclaw\workspace"
SECURITY_DIR = Path(WORKSPACE_D) / "security"
COGNITIVE_CONTEXT_FILE = SECURITY_DIR / "cognitive_context.json"
WORKING_MEMORY_SHADOW_FILE = SECURITY_DIR / "working_memory_shadow.json"
WORKSPACE_SNAPSHOT_FILE = SECURITY_DIR / "workspace_snapshot.json"

# =============================================================================
# 枚举
# =============================================================================

class ColdStartDepth(str, Enum):
    """P0→P3 冷启动深度四级"""
    P0_MINIMAL = "MINIMAL"   # 几乎不停，直接接续（ready≥0.85）
    P1_LIGHT   = "LIGHT"    # 轻度对齐，1-2 轮恢复（ready 0.60-0.85）
    P2_STANDARD = "STANDARD" # 标准恢复，口令+钢印（ready 0.30-0.60）
    P3_FULL    = "FULL"      # 全面冷启动，完整验证（ready<0.30）

class CircadianPhase(str, Enum):
    MORNING   = "morning"
    AFTERNOON = "afternoon"
    EVENING   = "evening"
    NIGHT     = "night"
    DAWN      = "dawn"

class InterruptionType(str, Enum):
    NATURAL_PAUSE = "natural_pause"
    FORCE_SWITCH   = "force_switch"
    ABNORMAL_EXIT  = "abnormal_exit"
    GRACEFUL_EXIT  = "graceful_exit"

# =============================================================================
# 工作区快照哈希（增强版）
# =============================================================================

CRITICAL_FILES = [
    "SOUL.md",
    "MEMORY.md",
    "TODO.md",
    "src/cold_start_engine.py",
    "src/tu8_agent.py",
    "src/tu8_memory.py",
]

def compute_workspace_snapshot_hash(workspace_dir: str = WORKSPACE_D) -> Dict:
    """
    工作区快照哈希（增强版）

    不只哈希目录名，而是对关键文件内容取 SHA-256，
    并记录文件大小+修改时间，精确感知"工位是否变了"。

    返回:
        {
            "snapshot_hash": "abc123...",   # 关键文件内容哈希
            "file_hashes": {...},           # 每个文件的独立哈希
            "timestamp": 1234567890.123,
            "file_count": N,
        }
    """
    workspace = Path(workspace_dir)
    file_hashes = {}
    snapshot_components = []

    for rel_path in CRITICAL_FILES:
        full_path = workspace / rel_path
        if full_path.exists():
            try:
                stat = full_path.stat()
                mtime = stat.st_mtime
                size = stat.st_size
                with open(full_path, "rb") as f:
                    content_hash = hashlib.sha256(f.read()).hexdigest()[:16]
                file_hashes[rel_path] = {
                    "hash": content_hash,
                    "mtime": mtime,
                    "size": size,
                }
                # 快照组件: 路径 + 内容哈希 + 修改时间
                snapshot_components.append(f"{rel_path}:{content_hash}:{int(mtime)}")
            except Exception as e:
                logger.warning(f"快照哈希计算失败 {rel_path}: {e}")
                snapshot_components.append(f"{rel_path}:ERROR")
        else:
            snapshot_components.append(f"{rel_path}:MISSING")

    # 目录结构哈希（兜底）
    dir_components = []
    try:
        for item in sorted(workspace.iterdir()):
            if item.is_dir():
                dir_components.append(f"D:{item.name}")
            elif item.is_file():
                dir_components.append(f"F:{item.name}")
        src_dir = workspace / "src"
        if src_dir.exists():
            for item in sorted(src_dir.iterdir()):
                if item.suffix == ".py":
                    dir_components.append(f"S:{item.name}")
    except Exception:
        logger.debug("Exception suppressed", exc_info=True)
        pass
    snapshot_components.append("DIR:" + "|".join(dir_components))

    raw = "||".join(snapshot_components)
    snapshot_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    return {
        "snapshot_hash": snapshot_hash,
        "file_hashes": file_hashes,
        "timestamp": datetime.now(timezone.utc).timestamp(),
        "file_count": len(file_hashes),
    }


def load_last_workspace_snapshot() -> Optional[Dict]:
    """加载上次的工作区快照"""
    if WORKSPACE_SNAPSHOT_FILE.exists():
        try:
            with open(WORKSPACE_SNAPSHOT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载工作区快照失败: {e}")
    return None


def save_workspace_snapshot(snapshot: Dict):
    """保存当前工作区快照"""
    try:
        SECURITY_DIR.mkdir(parents=True, exist_ok=True)
        with open(WORKSPACE_SNAPSHOT_FILE, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存工作区快照失败: {e}")


def compare_workspace_snapshots(current: Dict, last: Dict) -> Dict:
    """
    对比两次工作区快照，返回变化详情

    返回:
        {
            "snapshot_changed": bool,
            "changed_files": [...],
            "new_files": [...],
            "missing_files": [...],
            "change_severity": "none"|"minor"|"major"|"catastrophic",
        }
    """
    if last is None:
        return {"snapshot_changed": False, "change_severity": "none",
                "changed_files": [], "new_files": [], "missing_files": []}

    current_hashes = current.get("file_hashes", {})
    last_hashes = last.get("file_hashes", {})

    changed_files = []
    new_files = []
    missing_files = []

    # 检查当前文件相对于上次的变化
    for path, info in current_hashes.items():
        if path not in last_hashes:
            new_files.append(path)
        elif info["hash"] != last_hashes[path]["hash"]:
            changed_files.append(path)

    # 检查消失的文件
    for path in last_hashes:
        if path not in current_hashes:
            missing_files.append(path)

    # 严重等级
    total_changes = len(changed_files) + len(new_files) + len(missing_files)
    if total_changes == 0:
        severity = "none"
    elif total_changes <= 2:
        severity = "minor"
    elif total_changes <= 5:
        severity = "major"
    else:
        severity = "catastrophic"

    snapshot_changed = (current.get("snapshot_hash") != last.get("snapshot_hash"))

    return {
        "snapshot_changed": snapshot_changed,
        "changed_files": changed_files,
        "new_files": new_files,
        "missing_files": missing_files,
        "change_severity": severity,
    }


# =============================================================================
# 草稿残影（工作记忆影子）
# =============================================================================

def save_working_memory_shadow(
    recent_messages: List[str],
    active_files: List[str],
    pending_task: Optional[str] = None,
    draft_buffer: Optional[str] = None,
):
    """
    保存工作记忆残影（增强版草稿残影）

    比 v1.0 的 last_draft_snippet 更完整：
    - recent_messages: 最近 N 条消息（用户+AI）
    - active_files: 正在编辑/查看的文件路径
    - pending_task: 未完成的任务描述
    - draft_buffer: 未发送的草稿 buffer

    存储路径: security/working_memory_shadow.json
    """
    shadow = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "recent_messages": recent_messages[-10:],   # 最多保存 10 条
        "active_files": active_files[:5],            # 最多 5 个活跃文件
        "pending_task": pending_task,
        "draft_buffer": (draft_buffer[:500] if draft_buffer else None),
        "message_count": len(recent_messages),
    }
    try:
        SECURITY_DIR.mkdir(parents=True, exist_ok=True)
        with open(WORKING_MEMORY_SHADOW_FILE, "w", encoding="utf-8") as f:
            json.dump(shadow, f, ensure_ascii=False, indent=2)
        logger.debug("工作记忆残影已保存")
    except Exception as e:
        logger.error(f"保存工作记忆残影失败: {e}")


def load_working_memory_shadow() -> Optional[Dict]:
    """加载工作记忆残影"""
    if WORKING_MEMORY_SHADOW_FILE.exists():
        try:
            with open(WORKING_MEMORY_SHADOW_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载工作记忆残影失败: {e}")
    return None


# =============================================================================
# 感知探针采集器（v1.1 增强版）
# =============================================================================

class PerceptionProbesV11:
    """
    多维感知探针采集器 v1.1

    新增探针:
      - conversation_density: 近期对话密度（消息数/小时）
      - cognitive_load: 认知负荷（未完成任务数 × 平均任务复杂度）
      - workspace_snapshot: 工作区快照哈希（增强版）
      - working_memory_shadow: 工作记忆残影（增强版草稿残影）
    """

    def __init__(self, workspace_dir: str = WORKSPACE_D):
        self.workspace_dir = Path(workspace_dir)
        self._context_file = SECURITY_DIR / "cognitive_context.json"
        self._ensure_dirs()

    def _ensure_dirs(self):
        SECURITY_DIR.mkdir(parents=True, exist_ok=True)

    def collect_all(self, user_message: str = "", recent_messages: List[str] = None) -> Dict:
        """
        采集全部感知信号（v1.1 增强版）

        Args:
            user_message: 用户当前输入
            recent_messages: 最近消息列表（由 tu8_agent 传入，可选）

        Returns:
            完整感知上下文（含新增维度）
        """
        context = self._load_context()

        # —— 原有探针 ——
        probes = {
            # 1. 任务残影
            "pending_draft_snippet": self._probe_draft(context, user_message),
            "unfinished_tasks": self._probe_unfinished_tasks(),

            # 2. 环境锚点（增强版：快照哈希）
            "workspace_snapshot_hash": compute_workspace_snapshot_hash(str(self.workspace_dir))["snapshot_hash"],
            "last_workspace_snapshot_hash": (load_last_workspace_snapshot() or {}).get("snapshot_hash"),
            "workspace_changed": None,

            # 3. 时间衰减
            "gap_seconds": self._probe_gap_seconds(context),
            "last_active": context.get("last_active"),

            # 4. 生物节律
            "circadian_phase": self._probe_circadian(),
            "local_hour": datetime.now().hour,

            # 5. 中断性质
            "interruption_type": self._probe_interruption(context),

            # 6. 任务完成度
            "last_task_completed": context.get("last_task_completed", None),
            "last_task_description": context.get("last_task_description", None),
        }

        # —— 新增探针 v1.1 ——
        probes.update({
            # 7. 对话密度（近期交互频率）
            "conversation_density": self._probe_conversation_density(context, recent_messages),

            # 8. 认知负荷
            "cognitive_load": self._probe_cognitive_load(probes["unfinished_tasks"], context),

            # 9. 工作记忆残影（增强版）
            "working_memory_shadow": load_working_memory_shadow(),

            # 10. 工作区快照详情（增强版）
            "workspace_snapshot_diff": self._probe_workspace_snapshot_diff(),
        })

        # 计算环境变化（使用增强版快照哈希）
        if probes["last_workspace_snapshot_hash"]:
            probes["workspace_changed"] = (
                probes["workspace_snapshot_hash"] != probes["last_workspace_snapshot_hash"]
            )
        else:
            probes["workspace_changed"] = None

        return probes

    def save_context(self, probes: Dict, user_message: str = "",
                     task_completed: bool = None, task_description: str = None):
        """保存当前认知上下文（供下次冷启动使用）"""
        context = {
            "last_active": datetime.now(timezone.utc).isoformat(),
            "last_workspace_hash": probes.get("workspace_snapshot_hash"),
            "last_draft_snippet": (user_message[:200] if user_message else None),
            "last_task_completed": task_completed,
            "last_task_description": task_description,
            "last_circadian_phase": probes.get("circadian_phase"),
            "last_interruption_type": probes.get("interruption_type"),
        }
        try:
            with open(self._context_file, "w", encoding="utf-8") as f:
                json.dump(context, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存认知上下文失败: {e}")

        # v1.1 新增：同时保存工作区快照
        current_snapshot = compute_workspace_snapshot_hash(str(self.workspace_dir))
        save_workspace_snapshot(current_snapshot)

    # =========================================================================
    # 原有探针方法（复用 v1.0 逻辑）
    # =========================================================================

    def _probe_draft(self, context: Dict, user_message: str) -> Optional[str]:
        if user_message:
            return user_message[:200]
        return context.get("last_draft_snippet")

    def _probe_unfinished_tasks(self) -> List[str]:
        tasks = []
        todo_file = self.workspace_dir / "TODO.md"
        if not todo_file.exists():
            return tasks
        try:
            with open(todo_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("### Q") and "[OK]" not in line and "已完成" not in line:
                        tasks.append(line.lstrip("# ").strip())
        except Exception as e:
            logger.error(f"读取 TODO 失败: {e}")
        return tasks

    def _probe_gap_seconds(self, context: Dict) -> float:
        last_active_str = context.get("last_active")
        if not last_active_str:
            return -1.0
        try:
            last_active = datetime.fromisoformat(last_active_str)
            if last_active.tzinfo is None:
                last_active = last_active.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            return (now - last_active).total_seconds()
        except Exception:
            return -1.0

    def _probe_circadian(self) -> str:
        hour = datetime.now().hour
        if 6 <= hour < 12:
            return CircadianPhase.MORNING.value
        elif 12 <= hour < 18:
            return CircadianPhase.AFTERNOON.value
        elif 18 <= hour < 22:
            return CircadianPhase.EVENING.value
        elif 22 <= hour or hour < 2:
            return CircadianPhase.NIGHT.value
        else:
            return CircadianPhase.DAWN.value

    def _probe_interruption(self, context: Dict) -> str:
        last_completed = context.get("last_task_completed")
        last_draft = context.get("last_draft_snippet")
        if last_completed is True:
            return InterruptionType.GRACEFUL_EXIT.value
        elif last_completed is False and last_draft:
            return InterruptionType.FORCE_SWITCH.value
        elif last_completed is None:
            return InterruptionType.ABNORMAL_EXIT.value
        else:
            return InterruptionType.NATURAL_PAUSE.value

    # =========================================================================
    # 新增探针 v1.1
    # =========================================================================

    def _probe_conversation_density(self, context: Dict,
                                   recent_messages: List[str] = None) -> float:
        """
        探针7: 对话密度

        计算近期交互频率（消息数/小时）。
        高密度 → 热启动信号强（"刚才还在聊"）。

        若无 recent_messages，回退到用 gap_seconds 估算。
        """
        gap_seconds = self._probe_gap_seconds(context)
        if gap_seconds < 0:
            return 0.0

        if recent_messages and len(recent_messages) > 0:
            # 有真实消息列表：直接计数
            msg_count = len(recent_messages)
            hours = max(gap_seconds / 3600.0, 0.01)  # 避免除零
            return round(msg_count / hours, 2)
        else:
            # 无消息列表：用 gap 反推（gap 越小密度越高）
            if gap_seconds < 300:      # 5 分钟内
                return 12.0            # 高密度
            elif gap_seconds < 1800:   # 30 分钟内
                return 4.0
            elif gap_seconds < 3600:   # 1 小时内
                return 1.0
            else:
                return 0.0

    def _probe_cognitive_load(self, unfinished_tasks: List[str], context: Dict) -> float:
        """
        探针8: 认知负荷

        未完成任务数 × 平均任务复杂度（从描述长度估算）。
        高负荷 → 冷启动时需要更多恢复时间。

        返回 0.0-1.0 的归一化负荷值。
        """
        task_count = len(unfinished_tasks)
        if task_count == 0:
            return 0.0

        # 复杂度代理：任务描述长度（从 TODO.md 的行长度估算）
        last_task_desc = context.get("last_task_description") or ""
        complexity = min(len(last_task_desc) / 200.0, 1.0)  # 归一化到 0-1

        # 负荷 = 任务数 × 复杂度，上限 1.0
        load = min(task_count * 0.2 * (0.5 + 0.5 * complexity), 1.0)
        return round(load, 3)

    def _probe_workspace_snapshot_diff(self) -> Dict:
        """
        探针10: 工作区快照差异详情（增强版）

        返回 compare_workspace_snapshots() 的详细结果。
        """
        current = compute_workspace_snapshot_hash(str(self.workspace_dir))
        last = load_last_workspace_snapshot()
        return compare_workspace_snapshots(current, last)

    # =========================================================================
    # 内部工具
    # =========================================================================

    def _load_context(self) -> Dict:
        try:
            if self._context_file.exists():
                with open(self._context_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"加载认知上下文失败: {e}")
        return {}


# =============================================================================
# 认知就绪度评估器（v1.1 增强版 — P0→P3 渐进映射）
# =============================================================================

class CognitiveReadinessAssessorV11:
    """
    认知就绪度评估器 v1.1

    核心升级:
      1. P0→P3 连续映射（替代原先只有一条规则）
      2. 对话密度感知（新增权重）
      3. 认知负荷修正（高负荷降低就绪度）
      4. 工作区快照差异感知（catastrophic 变化强制 P3）
    """

    # 节律调制系数
    CIRCADIAN_BOOST = {
        CircadianPhase.MORNING.value:   1.00,
        CircadianPhase.AFTERNOON.value: 0.95,
        CircadianPhase.EVENING.value:   0.90,
        CircadianPhase.NIGHT.value:     0.70,
        CircadianPhase.DAWN.value:      0.50,
    }

    # 中断性质修正
    INTERRUPTION_MODIFIER = {
        InterruptionType.GRACEFUL_EXIT.value: 1.00,
        InterruptionType.NATURAL_PAUSE.value:  0.95,
        InterruptionType.FORCE_SWITCH.value:   0.80,
        InterruptionType.ABNORMAL_EXIT.value:  0.70,
    }

    # P0→P3 映射阈值
    DEPTH_THRESHOLDS = {
        ColdStartDepth.P0_MINIMAL.value:  0.85,   # ≥0.85 → P0
        ColdStartDepth.P1_LIGHT.value:    0.60,   # 0.60-0.85 → P1
        ColdStartDepth.P2_STANDARD.value: 0.30,   # 0.30-0.60 → P2
        # <0.30 → P3_FULL
    }

    def assess(self, probes: Dict) -> Tuple[float, List[str], str]:
        """
        评估认知就绪度（v1.1 增强版）

        Args:
            probes: PerceptionProbesV11.collect_all() 的输出

        Returns:
            (readiness_score, activation_cues, recommended_depth)
            recommended_depth: P0_MINIMAL / P1_LIGHT / P2_STANDARD / P3_FULL
        """
        score = 0.0
        cues = []

        # =====================================================================
        # 1. 任务残影（权重 0.30）— 最强热启动线索
        # =====================================================================
        draft = probes.get("pending_draft_snippet")
        unfinished = probes.get("unfinished_tasks", [])
        shadow = probes.get("working_memory_shadow")  # v1.1 新增

        if draft:
            score += 0.20
            snippet = draft[:50] + ("..." if len(draft) > 50 else "")
            cues.append(f"用户有未完成草稿: '{snippet}'")

        if unfinished:
            score += 0.10
            task_names = "; ".join(unfinished[:3])
            cues.append(f"有{len(unfinished)}项未完成任务: {task_names}")

        # v1.1: 工作记忆残影加分
        if shadow and shadow.get("recent_messages"):
            msg_count = shadow.get("message_count", 0)
            if msg_count > 5:
                score += 0.05
                cues.append(f"工作记忆残影: 上次有{msg_count}条消息")

        # =====================================================================
        # 2. 环境锚点（权重 0.20）— 增强版快照感知
        # =====================================================================
        workspace_changed = probes.get("workspace_changed")
        snapshot_diff = probes.get("workspace_snapshot_diff", {})

        if workspace_changed is False:
            score += 0.20
            cues.append("工作区未变（回到熟悉工位）")
        elif workspace_changed is True:
            # 用快照差异严重等级来扣分
            severity = snapshot_diff.get("change_severity", "minor")
            penalty_map = {
                "none":     0.00,
                "minor":    0.10,
                "major":    0.25,
                "catastrophic": 0.50,
            }
            penalty = penalty_map.get(severity, 0.10)
            score -= penalty
            changed = snapshot_diff.get("changed_files", [])[:3]
            cues.append(f"[!] 工作区已变化({severity}): {changed}")

        # =====================================================================
        # 3. 时间衰减（权重 0.20）— 非线性，受节律调制
        # =====================================================================
        gap_seconds = probes.get("gap_seconds", -1)

        if gap_seconds >= 0:
            gap_hours = gap_seconds / 3600.0
            time_decay = max(0.0, 1.0 - (gap_hours / 24.0) ** 0.7)
            circadian = probes.get("circadian_phase", "afternoon")
            circadian_boost = self.CIRCADIAN_BOOST.get(circadian, 0.80)
            time_contribution = time_decay * 0.20 * circadian_boost
            score += time_contribution

            if gap_hours < 0.5:
                cues.append(f"刚离开{gap_hours*60:.0f}分钟")
            elif gap_hours < 2:
                cues.append(f"离开{gap_hours:.1f}小时（短休）")
            elif gap_hours < 8:
                cues.append(f"离开{gap_hours:.1f}小时（可能睡了一觉）")
            elif gap_hours < 24:
                cues.append(f"离开{gap_hours:.1f}小时（一夜过去了）")
            else:
                cues.append(f"离开{gap_hours:.0f}小时（深度休眠）")

        # =====================================================================
        # 4. 中断性质（权重 0.10）
        # =====================================================================
        interruption = probes.get("interruption_type", "natural_pause")
        modifier = self.INTERRUPTION_MODIFIER.get(interruption, 0.90)
        score *= modifier

        if interruption == InterruptionType.ABNORMAL_EXIT.value:
            cues.append("[!] 上次非正常退出，建议简要回顾")
        elif interruption == InterruptionType.FORCE_SWITCH.value:
            cues.append("上次被强制切换，可能有未收尾的工作")

        # =====================================================================
        # 5. 任务完成度（权重 0.10）
        # =====================================================================
        last_completed = probes.get("last_task_completed")
        last_task_desc = probes.get("last_task_description")

        if last_completed is True:
            score += 0.10
            if last_task_desc:
                cues.append(f"上次任务已收尾: {last_task_desc[:50]}")
        elif last_completed is False:
            score -= 0.05
            if last_task_desc:
                cues.append(f"上次任务未完成: {last_task_desc[:50]}")

        # =====================================================================
        # 6. 对话密度（权重 0.10）— v1.1 新增
        # =====================================================================
        density = probes.get("conversation_density", 0.0)
        if density > 8.0:
            score += 0.10
            cues.append(f"对话密度高({density:.1f}条/小时)，热启动信号强")
        elif density > 2.0:
            score += 0.05
            cues.append(f"对话密度中等({density:.1f}条/小时)")
        elif density > 0.0:
            score += 0.02
            cues.append(f"对话密度低({density:.1f}条/小时)")

        # =====================================================================
        # 7. 认知负荷（负权重 -0.15）— v1.1 新增
        # =====================================================================
        load = probes.get("cognitive_load", 0.0)
        if load > 0.7:
            score -= 0.15
            cues.append(f"[!] 认知负荷高({load:.2f})，需要更多恢复时间")
        elif load > 0.4:
            score -= 0.08
            cues.append(f"认知负荷中等({load:.2f})")
        # 低负荷不扣分

        # =====================================================================
        # 归一化 + P0→P3 深度推荐
        # =====================================================================
        score = max(0.0, min(1.0, score))
        recommended_depth = self._map_score_to_depth(score)

        return score, cues, recommended_depth

    def _map_score_to_depth(self, score: float) -> str:
        """
        P0→P3 连续映射

        score ≥ 0.85 → P0_MINIMAL   (几乎不停，直接接续)
        score 0.60-0.85 → P1_LIGHT  (轻度对齐)
        score 0.30-0.60 → P2_STANDARD (标准恢复)
        score < 0.30 → P3_FULL      (全面冷启动)
        """
        if score >= self.DEPTH_THRESHOLDS[ColdStartDepth.P0_MINIMAL.value]:
            return ColdStartDepth.P0_MINIMAL.value
        elif score >= self.DEPTH_THRESHOLDS[ColdStartDepth.P1_LIGHT.value]:
            return ColdStartDepth.P1_LIGHT.value
        elif score >= self.DEPTH_THRESHOLDS[ColdStartDepth.P2_STANDARD.value]:
            return ColdStartDepth.P2_STANDARD.value
        else:
            return ColdStartDepth.P3_FULL.value

    def generate_brief(self, readiness_score: float, cues: List[str],
                       probes: Dict, recommended_depth: str) -> str:
        """生成唤醒简报（含 P0→P3 深度建议）"""
        depth_labels = {
            "MINIMAL":   "P0-几乎不停",
            "LIGHT":     "P1-轻度对齐",
            "STANDARD":  "P2-标准恢复",
            "FULL":      "P3-全面冷启动",
        }
        depth_label = depth_labels.get(recommended_depth, recommended_depth)

        if readiness_score >= 0.8:
            level = "高连续性"
        elif readiness_score >= 0.5:
            level = "中度连续"
        elif readiness_score >= 0.3:
            level = "低连续性（需适度对齐）"
        else:
            level = "冷启动（需全面恢复）"

        circadian = probes.get("circadian_phase", "unknown")
        circadian_zh = {
            "morning": "晨间", "afternoon": "午后",
            "evening": "傍晚", "night": "深夜", "dawn": "凌晨",
        }.get(circadian, circadian)

        gap_seconds = probes.get("gap_seconds", -1)
        gap_str = f"{gap_seconds/3600:.1f}小时" if gap_seconds >= 0 else "首次"

        cues_text = "; ".join(cues) if cues else "无特殊线索"

        brief = (
            f"[COGNITIVE_BRIEF]\n"
            f"就绪度: {readiness_score:.2f} | {level}\n"
            f"推荐深度: {recommended_depth} ({depth_label})\n"
            f"线索: {cues_text}\n"
            f"节律: {circadian_zh} | 间隔: {gap_str}\n"
            f"[/COGNITIVE_BRIEF]"
        )
        return brief

    def suggest_recovery_action(self, readiness_score: float,
                                 cues: List[str],
                                 recommended_depth: str) -> str:
        """根据 P0→P3 深度建议恢复行动"""
        if recommended_depth == ColdStartDepth.P0_MINIMAL.value:
            return "P0-几乎不停：直接接续即可，用户状态高度连续。"
        elif recommended_depth == ColdStartDepth.P1_LIGHT.value:
            has_draft = any("草稿" in c or "draft" in c.lower() for c in cues)
            if has_draft:
                return "P1-轻度对齐：用户有未完成的想法，可以主动提示接续。"
            return "P1-轻度对齐：简短确认当前状态，不需要全面回顾。"
        elif recommended_depth == ColdStartDepth.P2_STANDARD.value:
            return "P2-标准恢复：先简要回顾最近进展，再确认下一步方向。"
        else:
            has_abnormal = any("非正常退出" in c or "abnormal" in c.lower() for c in cues)
            if has_abnormal:
                return "P3-全面冷启动：上次异常退出，建议完整回顾钢印和任务状态。"
            return "P3-全面冷启动：温和地问候，全面回顾最近的钢印和任务。"


# =============================================================================
# 便捷入口（v1.1）
# =============================================================================

def assess_cognitive_readiness_v11(
    user_message: str = "",
    recent_messages: List[str] = None,
    workspace_dir: str = WORKSPACE_D
) -> Dict:
    """
    一站式评估入口（v1.1）

    Args:
        user_message: 用户当前输入
        recent_messages: 最近消息列表（可选，由 tu8_agent 传入）
        workspace_dir: 工作空间目录

    Returns:
        {
            "readiness_score": float,
            "activation_cues": List[str],
            "recommended_depth": str,   # P0→P3
            "cognitive_brief": str,
            "recovery_suggestion": str,
            "probes": Dict,
        }
    """
    probes_collector = PerceptionProbesV11(workspace_dir)
    assessor = CognitiveReadinessAssessorV11()

    probes = probes_collector.collect_all(user_message, recent_messages)
    score, cues, depth = assessor.assess(probes)
    brief = assessor.generate_brief(score, cues, probes, depth)
    suggestion = assessor.suggest_recovery_action(score, cues, depth)

    return {
        "readiness_score": score,
        "activation_cues": cues,
        "recommended_depth": depth,
        "cognitive_brief": brief,
        "recovery_suggestion": suggestion,
        "probes": probes,
    }


def save_working_memory_shadow_wrapper(
    recent_messages: List[str] = None,
    active_files: List[str] = None,
    pending_task: str = None,
    draft_buffer: str = None,
):
    """包装函数，供 tu8_agent.py 调用"""
    save_working_memory_shadow(
        recent_messages or [],
        active_files or [],
        pending_task,
        draft_buffer,
    )


# =============================================================================
# CLI 自测
# =============================================================================

def main():
    print("=" * 60)
    print("认知就绪度评估器 v1.1 自测")
    print("=" * 60)

    # 测试工作区快照哈希
    print("\n[1] 工作区快照哈希测试...")
    snapshot = compute_workspace_snapshot_hash()
    print(f"  快照哈希: {snapshot['snapshot_hash']}")
    print(f"  关键文件数: {snapshot['file_count']}")
    for path, info in list(snapshot["file_hashes"].items())[:3]:
        print(f"    {path}: {info['hash']}")

    # 测试评估
    print("\n[2] 认知就绪度评估测试...")
    result = assess_cognitive_readiness_v11(user_message="帮我继续完成 Q9")
    print(f"  就绪度分数: {result['readiness_score']:.2f}")
    print(f"  推荐深度: {result['recommended_depth']}")
    print(f"  激活线索:")
    for cue in result["activation_cues"]:
        print(f"    - {cue}")
    print(f"\n  唤醒简报:")
    print(result["cognitive_brief"])
    print(f"\n  恢复建议: {result['recovery_suggestion']}")

    # 保存快照和残影（模拟正常退出）
    print("\n[3] 保存工作区快照 + 工作记忆残影...")
    save_workspace_snapshot(snapshot)
    save_working_memory_shadow(
        recent_messages=["用户: 帮我做 Q9", "AI: 好的，先读 cognitive_readiness.py"],
        active_files=["src/cognitive_readiness.py"],
        pending_task="Q9 认知就绪度 P0→P3 渐进扩展",
        draft_buffer="def _map_score_to_depth(self, score):",
    )
    print("  已保存")

    print("\n" + "=" * 60)
    print("自测完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
