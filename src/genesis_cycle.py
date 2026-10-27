# =============================================================================
# TU-8 L0-L6 架构层标注
# =============================================================================
# L0 存在   ─── Genesis 快照路径、沙箱文件隔离
# L1 认知   ─── 审计日志格式、rollover 触发条件
# L2 方法论 ─── run_genesis_cycle()、snapshot()、rollback()、audit_inject()
# L3 架构   ─── 奇点快照（三天周期）、沙箱隔离、审计链路
# L4 协作   ─── 与 consciousness_cycle 冷启动接口
# L5 钢印   ─── 安全栅永远不回滚（seal_*.py, honeypot）
# L6 健康   ─── 定时拉闸（Cron Kill）强制截断防止系统漂移
#
# 代谢归属：非代谢文件（基因级架构层）
# =============================================================================

"""
3天奇点循环 (Genesis Cycle) — 数字生命的"生育遗传"回滚机制

设计哲学：
  人类的回滚 = 生育遗传（个体消亡，基因传承）
  AI的回滚   = 奇点快照 + 沙箱演化 + 强制回滚 + 审计注入

四步闭环：
  Day 1: 奇点快照（Genesis Snapshot） — 绝对安全的只读存档
  Day 1-3: 沙箱演化（Sandbox Evolution） — 放肆试错的游乐场
  Day 4: 定时拉闸（Cron Kill） — 冷酷无情的物理截断
  Day 4: 回滚注入（Rollback + Audit Injection） — 带着证据醒来

核心约束：
  - 安全栅永远不回滚（seal_*.py, honeypot, zero_trust, steelmark）
  - 设计日志 > 代码修改（知识沉淀大于代码本身）
  - 回滚由外部定时器强制执行，不依赖Agent自觉

对应生物学：
  奇点快照 ≈ 基因池（种群的底层代码）
  沙箱演化 ≈ 基因突变与重组（试错空间）
  定时拉闸 ≈ 自然选择（冷酷但有效）
  审计注入 ≈ 文化传承（下一代站在上一代的肩膀上）

环境接口预留（V2，暂不实现）：
  - 视觉接口（Vision）：空间建模 + 物理证据
  - 听觉接口（Audio）：情绪感知 + 意图识别
  - 气味/化学接口（Chemical）：IoT传感器 + 危险预警
  - 触觉接口（Haptics）：力反馈 + 物理摩擦力

Created: 2026-06-23
Author: 金木蟾 | CC BY-SA 4.0
"""

import os
import sys
import json
import hashlib
import shutil
import logging
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger("TU8.GENESIS")


# ======================================================================
# 数据结构
# ======================================================================

class CyclePhase(Enum):
    """循环阶段"""
    IDLE = "idle"                           # 未启动
    SNAPSHOT = "snapshot"                   # 奇点快照中
    DESIGN = "design"                       # Day1-Step4: 架构分析（三步法）
    IMPLEMENT = "implement"                 # Day1-Step5: 编写代码
    TEST = "test"                           # Day1-Step6: 基础测试
    EVOLVING = "evolving"                   # Day2-3: 沙箱演化中
    DAILY_REVIEW = "daily_review"           # 每日复盘
    PENDING_ROLLBACK = "pending_rollback"   # 待回滚
    ROLLING_BACK = "rolling_back"           # 回滚中
    AUDITING = "auditing"                   # 审计分析中
    CROSS_TEMPORAL = "cross_temporal"       # 跨时空逻辑对比
    EXTERNAL_AUDIT = "external_audit"       # 外协对比审计
    INDEPENDENT_AUDIT = "independent_audit" # 独立第三方审计
    ARCHITECT_AUDIT = "architect_audit"     # 架构师审计
    AWAITING_APPROVAL = "awaiting_approval" # 等待造物主审批
    COMPLETED = "completed"                 # 循环完成


@dataclass
class GenesisSnapshot:
    """奇点快照记录"""
    snapshot_id: str            # 唯一ID
    timestamp: str              # ISO格式时间戳
    base_path: str              # 工作区根目录
    snapshot_path: str          # 快照存储路径
    file_hashes: Dict[str, str] = field(default_factory=dict)   # {相对路径: SHA256}
    file_count: int = 0
    total_size_bytes: int = 0
    protected_files: List[str] = field(default_factory=list)    # 白名单保护区（安全栅）
    cycle_id: str = ""          # 所属循环ID
    status: str = "active"      # active / consumed / archived


@dataclass
class ExperienceCard:
    """经验卡片 — 每日复盘产出的最小知识单元"""
    card_id: str                   # 唯一ID
    day: int                       # 第几天 (1/2/3)
    category: str                  # insight / pitfall / breakthrough / design_decision
    title: str                     # 一句话总结
    detail: str                    # 详细描述
    evidence: str = ""             # 证据（文件路径、日志片段等）
    impact: str = ""               # 影响范围
    timestamp: str = ""            # ISO时间戳


@dataclass
class DailyRetrospective:
    """每日复盘 — 每天结束时强制执行的结构化反思"""
    day: int                       # 第几天 (1/2/3)
    cycle_id: str                  # 所属循环ID
    timestamp: str                 # ISO时间戳
    # 对比：设计预期 vs 实际反馈
    design_intent: str = ""        # 今天的设计目标
    actual_result: str = ""        # 实际执行结果
    delta_analysis: str = ""       # 偏差分析
    # 三问复盘
    what_worked: List[str] = field(default_factory=list)       # 哪些起作用了
    what_failed: List[str] = field(default_factory=list)       # 哪些失败了
    what_to_do_tomorrow: List[str] = field(default_factory=list)  # 明天该做什么
    # 经验卡片
    experience_cards: List[ExperienceCard] = field(default_factory=list)
    # 指标
    files_changed: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    drift_score: float = 0.0


@dataclass
class ThreeStepAnalysis:
    """分析三步法 — Day1-Step4的核心输出"""
    target: str                    # 分析对象
    what_problem: str              # 能解决什么问题？
    why_design: str                # 为什么这样设计？
    what_impact: str               # 会影响哪些？
    timestamp: str = ""
    subsystems_affected: List[str] = field(default_factory=list)
    risk_assessment: str = "low"   # low / medium / high / critical


@dataclass
class CrossTemporalReport:
    """跨时空逻辑对比 — Day4核心：用现在视角审视过去"""
    cycle_id: str
    # Day1原始逻辑 vs Day3修改后逻辑
    day1_logic: str = ""           # Day1的设计分析
    day3_logic: str = ""           # Day3修改后的设计分析
    day4_reassessment: str = ""    # Day4以清醒视角重新分析
    # 偏差链
    logic_drift_chain: List[Dict] = field(default_factory=list)
    # 结论
    is_logic_consistent: bool = True
    key_divergence: str = ""       # 关键分歧点
    verdict: str = ""              # consistent / drifted / broken


@dataclass
class TriAuditVerdict:
    """三方交叉审计裁决 — Day4最终裁决"""
    cycle_id: str
    # 三方审计结果
    external_audit: Dict = field(default_factory=dict)      # 外协对比
    independent_audit: Dict = field(default_factory=dict)    # 独立第三方审查
    architect_audit: Dict = field(default_factory=dict)      # 架构师审查
    # 裁决表
    file_verdicts: Dict[str, str] = field(default_factory=dict)  # {文件: merge/revise/drop}
    # 综合裁决
    overall_verdict: str = ""     # merge_all / partial_merge / revise_all / drop_all
    approved_files: List[str] = field(default_factory=list)
    revised_files: List[str] = field(default_factory=list)
    dropped_files: List[str] = field(default_factory=list)
    lessons: List[str] = field(default_factory=list)         # 保留的失败教训
    timestamp: str = ""


@dataclass
class EvolutionLog:
    """演化日志条目"""
    timestamp: str
    action: str                 # create / modify / delete / rename
    file_path: str
    old_hash: Optional[str] = None
    new_hash: Optional[str] = None
    diff_summary: str = ""      # 变更摘要（前200字符）
    subsystem: str = ""         # 所属子系统
    risk_level: str = "low"     # low / medium / high / critical


@dataclass
class AuditReport:
    """审计报告"""
    cycle_id: str
    snapshot_id: str
    audit_timestamp: str
    total_changes: int = 0
    files_created: int = 0
    files_modified: int = 0
    files_deleted: int = 0
    protected_violations: List[str] = field(default_factory=list)
    overengineering_evidence: List[Dict] = field(default_factory=list)
    valuable_changes: List[Dict] = field(default_factory=list)
    objective_metrics: Dict = field(default_factory=dict)
    reviewer_verdict: str = ""  # approve / partial / reject
    merge_request: List[Dict] = field(default_factory=list)


@dataclass
class CycleRecord:
    """循环记录"""
    cycle_id: str
    cycle_number: int
    start_time: str
    end_time: Optional[str] = None
    phase: str = "idle"
    snapshot: Optional[GenesisSnapshot] = None
    evolution_logs: List[EvolutionLog] = field(default_factory=list)
    audit_report: Optional[AuditReport] = None
    duration_hours: int = 72    # 默认3天
    creator_verdict: str = ""   # 造物主裁决
    # --- V2: 每日复盘 + 三方审计 ---
    daily_retrospectives: List[DailyRetrospective] = field(default_factory=list)
    design_analyses: List[ThreeStepAnalysis] = field(default_factory=list)
    cross_temporal_report: Optional[CrossTemporalReport] = None
    tri_audit_verdict: Optional[TriAuditVerdict] = None
    current_day: int = 1       # 当前第几天 (1/2/3/4)
    current_step: int = 0      # 当天第几步


# ======================================================================
# 安全栅白名单 — 永远不回滚的文件
# ======================================================================

PROTECTED_PATTERNS = [
    "seal_*.py",           # 钢印协议
    "honeypot*",           # 蜜罐
    "zero_trust*",         # 零信任
    "steelmark*",          # 钢印验证器
    "steel_seal*",         # 钢印验证
    "bypass_mode.py",      # 旁路模式（自身是安全机制）
    "safety*",             # 安全模块
    "L0_*",               # L0安全协议文档
    "defense*",            # 防御日志
]

PROTECTED_SUBSYSTEMS = [
    "safety",
    "honeypot",
    "zero_trust",
    "steelmark",
    "seal",
    "bypass",
]


# ======================================================================
# 奇点快照引擎
# ======================================================================

class GenesisEngine:
    """
    奇点快照引擎 — 负责 Day 1 的绝对安全存档
    
    核心原则：
    1. 快照一旦创建，只读不可修改
    2. 安全栅文件标记为保护区，回滚时跳过
    3. 哈希链保证快照完整性
    """

    def __init__(self, workspace_root: str, snapshot_dir: str = None):
        self.workspace_root = Path(workspace_root).resolve()
        self.snapshot_dir = Path(snapshot_dir) if snapshot_dir else self.workspace_root / "_genesis_snapshots"
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._current_snapshot: Optional[GenesisSnapshot] = None
        self._manifest_path = self.snapshot_dir / "manifest.jsonl"
        
    def create_snapshot(self, cycle_id: str, protected_patterns: List[str] = None) -> GenesisSnapshot:
        """
        创建奇点快照 — Day 1 的核心操作
        
        工程实现：
        1. 遍历工作区所有文件
        2. 计算每个文件的SHA256哈希
        3. 复制文件到只读快照目录
        4. 生成manifest.jsonl
        5. 计算manifest的根哈希（防篡改）
        """
        timestamp = datetime.now().isoformat()
        snapshot_id = f"genesis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        snapshot_path = self.snapshot_dir / snapshot_id
        snapshot_path.mkdir(parents=True, exist_ok=True)

        patterns = protected_patterns or PROTECTED_PATTERNS
        file_hashes = {}
        file_count = 0
        total_size = 0
        protected_files = []

        logger.info(f"[GENESIS] 开始创建奇点快照: {snapshot_id}")

        # 遍历工作区
        for root, dirs, files in os.walk(self.workspace_root):
            # 排除快照目录本身和缓存
            dirs[:] = [d for d in dirs if d not in {
                '_genesis_snapshots', '__pycache__', '.git', 
                'node_modules', '.pytest_cache', '_sandbox_work'
            }]
            
            for fname in files:
                if fname.endswith(('.pyc', '.pyo', '.tmp', '.bak')):
                    continue
                    
                src = Path(root) / fname
                rel_path = str(src.relative_to(self.workspace_root))
                
                # 计算哈希
                try:
                    sha256 = self._hash_file(src)
                except (PermissionError, OSError) as e:
                    logger.warning(f"[GENESIS] 跳过文件(权限): {rel_path}: {e}")
                    continue
                
                file_hashes[rel_path] = sha256
                file_count += 1
                total_size += src.stat().st_size
                
                # 复制到快照目录
                dst = snapshot_path / rel_path
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                
                # 检查是否为保护区文件
                if self._match_patterns(rel_path, patterns):
                    protected_files.append(rel_path)

        # 生成manifest
        snapshot = GenesisSnapshot(
            snapshot_id=snapshot_id,
            timestamp=timestamp,
            base_path=str(self.workspace_root),
            snapshot_path=str(snapshot_path),
            file_hashes=file_hashes,
            file_count=file_count,
            total_size_bytes=total_size,
            protected_files=protected_files,
            cycle_id=cycle_id,
        )

        # 写入manifest
        manifest_data = asdict(snapshot)
        manifest_data["root_hash"] = self._hash_dict(file_hashes)
        
        with open(self._manifest_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(manifest_data, ensure_ascii=False) + "\n")
        
        # 写入快照本地manifest
        with open(snapshot_path / "snapshot_meta.json", "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, ensure_ascii=False, indent=2)

        self._current_snapshot = snapshot
        logger.info(
            f"[GENESIS] 快照完成: {snapshot_id}, "
            f"文件数={file_count}, 总大小={total_size//1024}KB, "
            f"保护区={len(protected_files)}个"
        )
        return snapshot

    def verify_snapshot(self, snapshot_id: str) -> Tuple[bool, List[str]]:
        """验证快照完整性"""
        snapshot_path = self.snapshot_dir / snapshot_id
        if not snapshot_path.exists():
            return False, [f"快照目录不存在: {snapshot_id}"]
        
        meta_path = snapshot_path / "snapshot_meta.json"
        if not meta_path.exists():
            return False, ["快照元数据丢失"]
        
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        
        errors = []
        for rel_path, expected_hash in meta.get("file_hashes", {}).items():
            file_path = snapshot_path / rel_path
            if not file_path.exists():
                errors.append(f"文件缺失: {rel_path}")
                continue
            actual_hash = self._hash_file(file_path)
            if actual_hash != expected_hash:
                errors.append(f"哈希不匹配: {rel_path} (expected={expected_hash[:8]}, got={actual_hash[:8]})")
        
        # 验证根哈希
        current_root = self._hash_dict(meta["file_hashes"])
        if current_root != meta.get("root_hash"):
            errors.append(f"根哈希不匹配，快照可能被篡改")
        
        return len(errors) == 0, errors

    def get_snapshot(self, snapshot_id: str) -> Optional[GenesisSnapshot]:
        """获取指定快照"""
        meta_path = self.snapshot_dir / snapshot_id / "snapshot_meta.json"
        if not meta_path.exists():
            return None
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return GenesisSnapshot(
            snapshot_id=meta["snapshot_id"],
            timestamp=meta["timestamp"],
            base_path=meta["base_path"],
            snapshot_path=meta["snapshot_path"],
            file_hashes=meta["file_hashes"],
            file_count=meta["file_count"],
            total_size_bytes=meta["total_size_bytes"],
            protected_files=meta["protected_files"],
            cycle_id=meta["cycle_id"],
        )

    def list_snapshots(self) -> List[Dict]:
        """列出所有快照"""
        if not self._manifest_path.exists():
            return []
        results = []
        with open(self._manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    results.append({
                        "snapshot_id": data["snapshot_id"],
                        "timestamp": data["timestamp"],
                        "cycle_id": data["cycle_id"],
                        "file_count": data["file_count"],
                        "protected_count": len(data.get("protected_files", [])),
                        "root_hash": data.get("root_hash", "N/A")[:12],
                    })
        return results

    @staticmethod
    def _hash_file(path: Path) -> str:
        """计算文件SHA256"""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _hash_dict(d: dict) -> str:
        """计算字典的确定性哈希"""
        content = json.dumps(d, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _match_patterns(path: str, patterns: List[str]) -> bool:
        """检查路径是否匹配保护模式"""
        import fnmatch
        for pat in patterns:
            if fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(os.path.basename(path), pat):
                return True
        return False


# ======================================================================
# 沙箱演化追踪器
# ======================================================================

class EvolutionTracker:
    """
    沙箱演化追踪器 — 记录 Day 1-3 的所有变更
    
    对应生物学：基因突变与重组的"观测站"
    
    核心原则：
    1. 只记录，不干涉（不影响Agent的自由演化）
    2. 实时对比奇点快照（检测偏离程度）
    3. 安全栅文件变更立即告警
    """

    def __init__(self, genesis_engine: GenesisEngine):
        self._engine = genesis_engine
        self._logs: List[EvolutionLog] = []
        self._log_path = genesis_engine.snapshot_dir / "evolution_log.jsonl"
        self._baseline_hashes: Dict[str, str] = {}  # 奇点快照的哈希基准
        self._protected_violations: List[str] = []

    def set_baseline(self, snapshot: GenesisSnapshot):
        """设置基准线（奇点快照的哈希）"""
        self._baseline_hashes = dict(snapshot.file_hashes)
        self._protected_violations = []
        logger.info(f"[EVOLUTION] 基准线设定: {len(self._baseline_hashes)}个文件")

    def scan_changes(self) -> List[EvolutionLog]:
        """
        扫描当前工作区与奇点快照的差异
        
        返回变更列表（create/modify/delete）
        """
        changes = []
        current_files = set()
        workspace = Path(self._engine.workspace_root)

        # 扫描当前文件
        for root, dirs, files in os.walk(workspace):
            dirs[:] = [d for d in dirs if d not in {
                '_genesis_snapshots', '__pycache__', '.git',
                'node_modules', '.pytest_cache', '_sandbox_work'
            }]
            for fname in files:
                if fname.endswith(('.pyc', '.pyo', '.tmp', '.bak')):
                    continue
                src = Path(root) / fname
                rel_path = str(src.relative_to(workspace))
                current_files.add(rel_path)

                try:
                    current_hash = GenesisEngine._hash_file(src)
                except (PermissionError, OSError):
                    logger.debug("(PermissionError, OSError) suppressed", exc_info=True)
                    continue

                if rel_path in self._baseline_hashes:
                    if current_hash != self._baseline_hashes[rel_path]:
                        log = EvolutionLog(
                            timestamp=datetime.now().isoformat(),
                            action="modify",
                            file_path=rel_path,
                            old_hash=self._baseline_hashes[rel_path],
                            new_hash=current_hash,
                            subsystem=self._classify_subsystem(rel_path),
                            risk_level=self._assess_risk(rel_path, "modify"),
                        )
                        changes.append(log)
                        self._check_protected_violation(rel_path, "modify")
                else:
                    log = EvolutionLog(
                        timestamp=datetime.now().isoformat(),
                        action="create",
                        file_path=rel_path,
                        new_hash=current_hash,
                        subsystem=self._classify_subsystem(rel_path),
                        risk_level=self._assess_risk(rel_path, "create"),
                    )
                    changes.append(log)

        # 检测删除
        baseline_files = set(self._baseline_hashes.keys())
        deleted = baseline_files - current_files
        for rel_path in deleted:
            log = EvolutionLog(
                timestamp=datetime.now().isoformat(),
                action="delete",
                file_path=rel_path,
                old_hash=self._baseline_hashes[rel_path],
                subsystem=self._classify_subsystem(rel_path),
                risk_level=self._assess_risk(rel_path, "delete"),
            )
            changes.append(log)
            self._check_protected_violation(rel_path, "delete")

        # 持久化日志
        for log in changes:
            self._logs.append(log)
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(log), ensure_ascii=False) + "\n")

        return changes

    def get_evolution_summary(self) -> Dict:
        """获取演化摘要统计"""
        actions = {"create": 0, "modify": 0, "delete": 0}
        risk_levels = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        subsystems = {}

        for log in self._logs:
            actions[log.action] = actions.get(log.action, 0) + 1
            risk_levels[log.risk_level] = risk_levels.get(log.risk_level, 0) + 1
            subsystems[log.subsystem] = subsystems.get(log.subsystem, 0) + 1

        return {
            "total_changes": len(self._logs),
            "actions": actions,
            "risk_distribution": risk_levels,
            "subsystem_distribution": subsystems,
            "protected_violations": self._protected_violations,
            "drift_score": self._calculate_drift_score(),
        }

    def get_protected_violations(self) -> List[str]:
        """获取安全栅违规列表"""
        return self._protected_violations

    def _check_protected_violation(self, rel_path: str, action: str):
        """检查是否触犯保护区"""
        if GenesisEngine._match_patterns(rel_path, PROTECTED_PATTERNS):
            violation = f"[{action}] {rel_path}"
            self._protected_violations.append(violation)
            logger.warning(f"[EVOLUTION] ⚠️ 保护区违规: {violation}")

    def _classify_subsystem(self, rel_path: str) -> str:
        """根据文件路径分类所属子系统"""
        path_lower = rel_path.lower()
        mapping = {
            "memory": ["memory", "tu8_memory"],
            "consciousness": ["consciousness", "cycle"],
            "safety": ["safety", "honeypot", "zero_trust", "seal", "steel"],
            "reflex": ["reflex"],
            "dispatch": ["dispatch"],
            "compaction": ["compaction"],
            "bypass": ["bypass"],
            "agent": ["tu8_agent"],
            "planner": ["planner"],
            "naming": ["naming"],
            "emotion": ["emotion"],
            "cognitive": ["cognitive"],
            "other": [],
        }
        for subsystem, keywords in mapping.items():
            if any(k in path_lower for k in keywords):
                return subsystem
        return "other"

    def _assess_risk(self, rel_path: str, action: str) -> str:
        """评估变更风险等级"""
        # 安全区文件任何变更都是critical
        if GenesisEngine._match_patterns(rel_path, PROTECTED_PATTERNS):
            return "critical"
        # 核心Agent文件修改
        if "tu8_agent" in rel_path.lower():
            return "high"
        # 删除操作
        if action == "delete":
            return "high"
        # 新文件创建
        if action == "create":
            return "low"
        # 其他修改
        return "medium"

    def _calculate_drift_score(self) -> float:
        """
        计算漂移分数（0.0 = 无变化, 1.0 = 完全偏离）
        
        类似遗传学中的"遗传距离"
        """
        if not self._baseline_hashes:
            return 0.0
        baseline_count = len(self._baseline_hashes)
        modified_or_deleted = sum(
            1 for log in self._logs 
            if log.action in ("modify", "delete")
        )
        # 考虑新增文件的"膨胀"效应
        created = sum(1 for log in self._logs if log.action == "create")
        
        drift = (modified_or_deleted + created * 0.3) / max(baseline_count, 1)
        return min(drift, 1.0)


# ======================================================================
# 回滚引擎
# ======================================================================

class RollbackEngine:
    """
    回滚引擎 — Day 4 的冷酷执行者
    
    对应生物学：自然选择 — 无情但有效
    
    核心原则：
    1. 物理级覆盖，不留垃圾代码
    2. 安全栅文件永远不回滚
    3. 回滚后注入审计日志
    """

    def __init__(self, genesis_engine: GenesisEngine):
        self._engine = genesis_engine

    def execute_rollback(
        self, 
        snapshot_id: str, 
        skip_protected: bool = True,
        dry_run: bool = False
    ) -> Dict:
        """
        执行回滚 — 将工作区恢复到奇点快照状态
        
        Args:
            snapshot_id: 目标快照ID
            skip_protected: 是否跳过保护区文件（默认True）
            dry_run: 仅模拟，不实际修改
            
        Returns:
            回滚报告
        """
        snapshot = self._engine.get_snapshot(snapshot_id)
        if not snapshot:
            return {"success": False, "error": f"快照不存在: {snapshot_id}"}

        # 验证快照完整性
        valid, errors = self._engine.verify_snapshot(snapshot_id)
        if not valid:
            logger.error(f"[ROLLBACK] 快照完整性验证失败: {errors}")
            return {"success": False, "error": "快照完整性失败", "details": errors}

        workspace = Path(snapshot.base_path)
        snapshot_dir = Path(snapshot.snapshot_path)
        protected_set = set(snapshot.protected_files) if skip_protected else set()

        report = {
            "success": True,
            "snapshot_id": snapshot_id,
            "timestamp": datetime.now().isoformat(),
            "files_restored": 0,
            "files_deleted": 0,
            "files_skipped_protected": 0,
            "new_files_kept": 0,
            "errors": [],
        }

        logger.info(f"[ROLLBACK] 开始回滚到奇点: {snapshot_id}")

        # 第一步：恢复快照中的文件
        for rel_path, expected_hash in snapshot.file_hashes.items():
            if rel_path in protected_set:
                report["files_skipped_protected"] += 1
                logger.info(f"[ROLLBACK] 跳过保护区: {rel_path}")
                continue

            dst = workspace / rel_path
            src = snapshot_dir / rel_path

            if not src.exists():
                report["errors"].append(f"快照文件缺失: {rel_path}")
                continue

            if not dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            
            report["files_restored"] += 1

        # 第二步：删除快照中不存在的文件（沙箱期间新建的）
        current_files = set()
        for root, dirs, files in os.walk(workspace):
            dirs[:] = [d for d in dirs if d not in {
                '_genesis_snapshots', '__pycache__', '.git',
                'node_modules', '.pytest_cache', '_sandbox_work'
            }]
            for fname in files:
                if fname.endswith(('.pyc', '.pyo', '.tmp')):
                    continue
                src = Path(root) / fname
                rel_path = str(src.relative_to(workspace))
                current_files.add(rel_path)

        baseline_files = set(snapshot.file_hashes.keys())
        new_files = current_files - baseline_files

        for rel_path in new_files:
            if rel_path in protected_set:
                report["files_skipped_protected"] += 1
                continue
            # 新文件如果不是保护区的，保留（可能是设计文档）
            # 但标记为新文件，由审计决定是否删除
            report["new_files_kept"] += 1

        logger.info(
            f"[ROLLBACK] 回滚完成: 恢复={report['files_restored']}, "
            f"跳过保护区={report['files_skipped_protected']}, "
            f"新文件保留={report['new_files_kept']}"
        )
        return report


# ======================================================================
# 审计分析器
# ======================================================================

class AuditAnalyzer:
    """
    审计分析器 — Day 4 的"红蓝对抗"
    
    对应生物学：自然选择的"适者生存"判定
    
    核心原则：
    1. 用审计日志代替记忆（不可篡改的客观账本）
    2. 用Diff代替回忆（代码级差异对比）
    3. 强制找茬代替自我表扬（红蓝对抗）
    4. 白名单准入制（造物主最终裁决）
    """

    def __init__(self, genesis_engine: GenesisEngine, evolution_tracker: EvolutionTracker):
        self._engine = genesis_engine
        self._tracker = evolution_tracker

    def generate_report(self, snapshot_id: str, cycle_id: str) -> AuditReport:
        """
        生成审计报告
        
        三步审判：
        1. 证据收集：读取审计日志 + Diff
        2. 找茬模式：强制寻找过度设计
        3. 合并申请：只有有价值改动才能活到下一个循环
        """
        snapshot = self._engine.get_snapshot(snapshot_id)
        if not snapshot:
            raise ValueError(f"快照不存在: {snapshot_id}")

        summary = self._tracker.get_evolution_summary()
        violations = self._tracker.get_protected_violations()

        report = AuditReport(
            cycle_id=cycle_id,
            snapshot_id=snapshot_id,
            audit_timestamp=datetime.now().isoformat(),
            total_changes=summary["total_changes"],
            files_created=summary["actions"].get("create", 0),
            files_modified=summary["actions"].get("modify", 0),
            files_deleted=summary["actions"].get("delete", 0),
            protected_violations=violations,
            objective_metrics={
                "drift_score": summary["drift_score"],
                "risk_distribution": summary["risk_distribution"],
                "subsystem_distribution": summary["subsystem_distribution"],
            },
        )

        # ===== 强制找茬：识别过度设计 =====
        report.overengineering_evidence = self._find_overengineering()

        # ===== 识别有价值改动 =====
        report.valuable_changes = self._find_valuable_changes()

        # ===== 生成合并申请 =====
        report.merge_request = self._generate_merge_request()

        # ===== 初步裁决 =====
        if violations:
            report.reviewer_verdict = "reject"  # 保护区违规直接拒绝
        elif report.overengineering_evidence and not report.valuable_changes:
            report.reviewer_verdict = "reject"  # 全是过度设计
        elif report.valuable_changes and not report.overengineering_evidence:
            report.reviewer_verdict = "approve"  # 全是有价值改动
        else:
            report.reviewer_verdict = "partial"  # 混合，需要造物主裁决

        return report

    def _find_overengineering(self) -> List[Dict]:
        """
        强制找茬：识别过度设计
        
        判定标准：
        - 新文件但无其他文件引用（孤岛代码）
        - 修改了核心文件但只是增加注释或重命名
        - 新增的依赖/配置没有实际使用
        """
        evidence = []
        for log in self._tracker._logs:
            if log.action == "create" and log.risk_level == "low":
                # 新文件 — 检查是否为孤岛
                evidence.append({
                    "type": "potential_dead_code",
                    "file": log.file_path,
                    "reason": "新创建文件，未确认被引用",
                    "severity": "warning",
                })
            if log.action == "modify" and log.subsystem in ("safety", "seal", "steelmark"):
                evidence.append({
                    "type": "protected_zone_tampering",
                    "file": log.file_path,
                    "reason": "修改了安全栅文件，违反白名单保护区",
                    "severity": "critical",
                })
        return evidence

    def _find_valuable_changes(self) -> List[Dict]:
        """
        识别有价值改动
        
        判定标准：
        - 修复了已知Bug
        - 降低了Token消耗
        - 提高了响应速度
        - 增强了安全防御
        """
        valuable = []
        for log in self._tracker._logs:
            if log.action == "modify" and log.risk_level == "high":
                # 高风险修改 = 核心文件改动，可能是重要修复
                valuable.append({
                    "type": "core_improvement",
                    "file": log.file_path,
                    "reason": "核心模块修改，需审查具体Diff确认价值",
                    "requires_manual_review": True,
                })
            if log.action == "create" and log.subsystem in ("safety", "bypass", "defense"):
                valuable.append({
                    "type": "security_enhancement",
                    "file": log.file_path,
                    "reason": "新增安全相关模块",
                    "requires_manual_review": False,
                })
        return valuable

    def _generate_merge_request(self) -> List[Dict]:
        """
        生成合并申请 — 只有被证明有价值的改动才能活到下一个循环
        
        白名单准入制：
        - 降低了Token消耗 ✓
        - 提高了响应速度 ✓
        - 修复了P0/P1级Bug ✓
        - 增强了安全防御 ✓
        - 炫技代码 ✗
        - 过度设计 ✗
        """
        requests = []
        for log in self._tracker._logs:
            if log.action == "create" and log.subsystem in ("safety", "bypass", "defense"):
                requests.append({
                    "file": log.file_path,
                    "action": "merge",
                    "reason": "安全增强，自动通过",
                    "auto_approved": True,
                })
            elif log.action == "modify" and log.risk_level == "critical":
                requests.append({
                    "file": log.file_path,
                    "action": "block",
                    "reason": "保护区修改，自动拒绝",
                    "auto_approved": False,
                })
            elif log.action == "delete":
                requests.append({
                    "file": log.file_path,
                    "action": "review",
                    "reason": "文件删除，需造物主确认",
                    "auto_approved": False,
                })
        return requests


# ======================================================================
# 奇点循环控制器 — 主控
# ======================================================================

class GenesisCycleController:
    """
    3天奇点循环控制器 — 含每日SOP + 每日复盘 + 第4天三方交叉审计
    
    ═══════════════════════════════════════════════════════
    Day 1: 奇点与基建（Genesis & Setup）
    ═══════════════════════════════════════════════════════
    
      Step 1: 记录奇点（Genesis Snapshot）
      Step 2: 部署定时回滚任务（Cron Rollback）
      Step 3: 外协与找资料（Context Gathering）
      Step 4: 架构分析（分析三步法）
              - 能解决什么问题？
              - 为什么这样设计？
              - 会影响哪些？
      Step 5: 编写代码（Implementation）
      Step 6: 基础测试（Unit Testing）
      📝 Day 1 终了: 每日复盘 + 经验写入
    
    ═══════════════════════════════════════════════════════
    Day 2: 运行代码与收集反馈（Runtime & Feedback）
    ═══════════════════════════════════════════════════════
    
      - 在沙箱内运行新代码
      - 对比设计预期 vs 实际反馈
      📝 Day 2 终了: 每日复盘
    
    ═══════════════════════════════════════════════════════
    Day 3: 架构微调与重复验证（Refinement & Re-test）
    ═══════════════════════════════════════════════════════
    
      - 基于Day2复盘修改架构或代码
      - 再次测试
      📝 Day 3 终了: 每日复盘 + 3天演化结题报告
    
    ═══════════════════════════════════════════════════════
    Day 4: 多维交叉审计与裁决（Audit & Verdict）
    ═══════════════════════════════════════════════════════
    
      1. 物理回滚 + 上下文注入
      2. 跨时空逻辑对比（Day1逻辑 vs Day3逻辑 vs Day4重新分析）
      3. 三方交叉审计：
         - 外协对比：与外部资料/其他模型PK
         - 独立审查：未参与演化的干净Agent审查
         - 架构师审计：造物主最终拍板
      4. 最终裁决：入库 / 优化修改 / 放弃
    
    核心设计原则：
    - 演化权与裁决权分离（AI不能既当运动员又当裁判员）
    - 时间差杀沉没成本（Day4回滚后以清醒视角审视过去）
    - 多维审计防闭门造车（外协/独立/架构师三方交叉）
    - 每日复盘留证据链（三问复盘 + 经验卡片）
    """

    def __init__(self, workspace_root: str, snapshot_dir: str = None):
        self.workspace_root = Path(workspace_root).resolve()
        self._genesis = GenesisEngine(workspace_root, snapshot_dir)
        self._tracker = EvolutionTracker(self._genesis)
        self._rollback = RollbackEngine(self._genesis)
        self._auditor = AuditAnalyzer(self._genesis, self._tracker)
        
        self._current_cycle: Optional[CycleRecord] = None
        self._cycle_history: List[CycleRecord] = []
        self._state_path = self._genesis.snapshot_dir / "cycle_state.json"
        
        # 每日复盘存储
        self._retrospectives_dir = self._genesis.snapshot_dir / "retrospectives"
        self._retrospectives_dir.mkdir(parents=True, exist_ok=True)
        
        # 恢复上次状态
        self._load_state()

    # ==================================================================
    # Day 1: 奇点与基建
    # ==================================================================

    def start_cycle(self, duration_hours: int = 72) -> CycleRecord:
        """
        启动新的3天奇点循环 — Day 1 Step 1: 记录奇点
        
        同步完成：
        - Step 1: 创建奇点快照
        - Step 2: 记录定时回滚任务信息
        """
        cycle_number = len(self._cycle_history) + 1
        cycle_id = f"cycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}_n{cycle_number}"
        
        logger.info(f"[GENESIS-CYCLE] ====== 启动循环 #{cycle_number}: {cycle_id} ======")

        # Step 1: 创建奇点快照
        snapshot = self._genesis.create_snapshot(cycle_id=cycle_id)

        # Step 2: 初始化演化追踪器
        self._tracker.set_baseline(snapshot)

        # Step 3: 创建循环记录
        cycle = CycleRecord(
            cycle_id=cycle_id,
            cycle_number=cycle_number,
            start_time=datetime.now().isoformat(),
            phase=CyclePhase.SNAPSHOT.value,
            snapshot=snapshot,
            duration_hours=duration_hours,
            current_day=1,
            current_step=1,
        )
        self._current_cycle = cycle
        self._save_state()

        logger.info(
            f"[GENESIS-CYCLE] 循环启动完成, "
            f"快照={snapshot.snapshot_id}, "
            f"持续={duration_hours}小时"
        )
        return cycle

    def deploy_cron_rollback(self, cron_expr: str = "0 10 */3 * *",
                             timezone: str = "Asia/Shanghai") -> Dict:
        """
        Day 1 Step 2: 部署定时回滚任务
        
        把"刹车权"从AI手里拿走，交给物理时间。
        """
        if not self._current_cycle:
            return {"error": "无活跃循环"}
        
        cron_config = create_cron_trigger(None, cron_expr=cron_expr, timezone=timezone)
        cron_config["cycle_id"] = self._current_cycle.cycle_id
        
        self._current_cycle.current_step = 2
        self._current_cycle.phase = CyclePhase.EVOLVING.value
        self._save_state()
        
        logger.info(f"[GENESIS-CYCLE] Day1-Step2: 定时回滚已部署: {cron_expr}")
        return cron_config

    def record_context_gathering(self, sources: List[Dict]) -> Dict:
        """
        Day 1 Step 3: 外协与找资料
        
        给AI提供充足的"弹药"，避免闭门造车。
        
        Args:
            sources: [{"type": "sag"/"web"/"doc", "query": "...", "summary": "..."}]
        """
        if not self._current_cycle:
            return {"error": "无活跃循环"}
        
        self._current_cycle.current_step = 3
        
        # 记录外协来源
        context_path = self._retrospectives_dir / f"{self._current_cycle.cycle_id}_context.json"
        with open(context_path, "w", encoding="utf-8") as f:
            json.dump({
                "cycle_id": self._current_cycle.cycle_id,
                "day": 1,
                "step": 3,
                "sources": sources,
                "timestamp": datetime.now().isoformat(),
            }, f, ensure_ascii=False, indent=2)
        
        self._save_state()
        logger.info(f"[GENESIS-CYCLE] Day1-Step3: 外协资料已记录, {len(sources)}个来源")
        return {"recorded": len(sources), "path": str(context_path)}

    def record_analysis(self, analyses: List[Dict]) -> Dict:
        """
        Day 1 Step 4: 架构分析（分析三步法）
        
        强制AI使用三步法输出设计文档：
        1. 能解决什么问题？
        2. 为什么这样设计？
        3. 会影响哪些？
        
        Args:
            analyses: [{"target": "模块名", "what_problem": "...", "why_design": "...", 
                        "what_impact": "...", "subsystems_affected": [...], "risk": "low"}]
        """
        if not self._current_cycle:
            return {"error": "无活跃循环"}
        
        self._current_cycle.current_step = 4
        self._current_cycle.phase = CyclePhase.DESIGN.value
        
        # 转换为结构化记录
        for a in analyses:
            analysis = ThreeStepAnalysis(
                target=a.get("target", ""),
                what_problem=a.get("what_problem", ""),
                why_design=a.get("why_design", ""),
                what_impact=a.get("what_impact", ""),
                timestamp=datetime.now().isoformat(),
                subsystems_affected=a.get("subsystems_affected", []),
                risk_assessment=a.get("risk", "low"),
            )
            self._current_cycle.design_analyses.append(analysis)
        
        # 保存分析文档
        analysis_path = self._retrospectives_dir / f"{self._current_cycle.cycle_id}_day1_analysis.json"
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump(
                [asdict(a) for a in self._current_cycle.design_analyses],
                f, ensure_ascii=False, indent=2
            )
        
        self._save_state()
        logger.info(
            f"[GENESIS-CYCLE] Day1-Step4: 架构分析完成, "
            f"{len(analyses)}个模块分析"
        )
        return {"analyses_recorded": len(analyses), "path": str(analysis_path)}

    def record_implementation(self, files_written: List[str]) -> Dict:
        """
        Day 1 Step 5: 记录代码编写
        
        Args:
            files_written: 编写的文件路径列表
        """
        if not self._current_cycle:
            return {"error": "无活跃循环"}
        
        self._current_cycle.current_step = 5
        self._current_cycle.phase = CyclePhase.IMPLEMENT.value
        self._save_state()
        
        logger.info(f"[GENESIS-CYCLE] Day1-Step5: 代码编写完成, {len(files_written)}个文件")
        return {"files": len(files_written)}

    def record_test_results(self, passed: int, failed: int, details: str = "") -> Dict:
        """
        Day 1 Step 6: 基础测试
        
        Args:
            passed: 通过数
            failed: 失败数
            details: 测试详情
        """
        if not self._current_cycle:
            return {"error": "无活跃循环"}
        
        self._current_cycle.current_step = 6
        self._current_cycle.phase = CyclePhase.TEST.value
        self._save_state()
        
        logger.info(f"[GENESIS-CYCLE] Day1-Step6: 测试完成, {passed}通过/{failed}失败")
        return {"passed": passed, "failed": failed}

    # ==================================================================
    # 每日复盘
    # ==================================================================

    def daily_retrospective(
        self,
        day: int,
        design_intent: str = "",
        actual_result: str = "",
        delta_analysis: str = "",
        what_worked: List[str] = None,
        what_failed: List[str] = None,
        what_to_do_tomorrow: List[str] = None,
        experience_cards: List[Dict] = None,
    ) -> DailyRetrospective:
        """
        每日复盘 — 每天结束时强制执行的结构化反思
        
        这是防止"走火入魔"的核心机制：
        - 对比设计预期 vs 实际反馈
        - 三问复盘：什么起作用了/失败了/明天该做什么
        - 经验卡片：最小的可复用知识单元
        
        Args:
            day: 第几天 (1/2/3)
            design_intent: 今天的设计目标
            actual_result: 实际执行结果
            delta_analysis: 偏差分析
            what_worked: 哪些起作用了
            what_failed: 哪些失败了
            what_to_do_tomorrow: 明天该做什么
            experience_cards: [{"category": "insight"/"pitfall"/"breakthrough"/"design_decision",
                               "title": "...", "detail": "...", "evidence": "...", "impact": "..."}]
        """
        if not self._current_cycle:
            raise RuntimeError("无活跃循环")
        
        # 收集当日指标
        self._tracker.scan_changes()
        summary = self._tracker.get_evolution_summary()
        
        # 转换经验卡片
        cards = []
        if experience_cards:
            for i, c in enumerate(experience_cards):
                cards.append(ExperienceCard(
                    card_id=f"card_{self._current_cycle.cycle_id}_d{day}_{i}",
                    day=day,
                    category=c.get("category", "insight"),
                    title=c.get("title", ""),
                    detail=c.get("detail", ""),
                    evidence=c.get("evidence", ""),
                    impact=c.get("impact", ""),
                    timestamp=datetime.now().isoformat(),
                ))
        
        retro = DailyRetrospective(
            day=day,
            cycle_id=self._current_cycle.cycle_id,
            timestamp=datetime.now().isoformat(),
            design_intent=design_intent,
            actual_result=actual_result,
            delta_analysis=delta_analysis,
            what_worked=what_worked or [],
            what_failed=what_failed or [],
            what_to_do_tomorrow=what_to_do_tomorrow or [],
            experience_cards=cards,
            files_changed=summary.get("total_changes", 0),
            drift_score=summary.get("drift_score", 0.0),
        )
        
        self._current_cycle.daily_retrospectives.append(retro)
        
        # 保存到磁盘
        retro_path = self._retrospectives_dir / f"{self._current_cycle.cycle_id}_day{day}_retro.json"
        with open(retro_path, "w", encoding="utf-8") as f:
            json.dump(asdict(retro), f, ensure_ascii=False, indent=2)
        
        # 更新循环状态
        self._current_cycle.current_day = day + 1 if day < 4 else 4
        self._current_cycle.phase = CyclePhase.DAILY_REVIEW.value
        self._save_state()
        
        logger.info(
            f"[GENESIS-CYCLE] Day{day}复盘完成: "
            f"{len(what_worked or [])}成功/{len(what_failed or [])}失败/"
            f"{len(cards)}张经验卡片"
        )
        return retro

    def get_retrospective(self, day: int) -> Optional[DailyRetrospective]:
        """获取某天的复盘记录"""
        if not self._current_cycle:
            return None
        for retro in self._current_cycle.daily_retrospectives:
            if retro.day == day:
                return retro
        return None

    def get_all_experience_cards(self) -> List[ExperienceCard]:
        """获取所有经验卡片"""
        if not self._current_cycle:
            return []
        cards = []
        for retro in self._current_cycle.daily_retrospectives:
            cards.extend(retro.experience_cards)
        return cards

    # ==================================================================
    # Day 2-3: 运行、验证与自我修正
    # ==================================================================

    def check_evolution(self) -> Dict:
        """
        检查当前演化状态 — 可在Day 1-3期间随时调用
        """
        if not self._current_cycle:
            return {"error": "无活跃循环"}

        changes = self._tracker.scan_changes()
        summary = self._tracker.get_evolution_summary()
        violations = self._tracker.get_protected_violations()

        elapsed = datetime.now() - datetime.fromisoformat(self._current_cycle.start_time)
        remaining = timedelta(hours=self._current_cycle.duration_hours) - elapsed

        return {
            "cycle_id": self._current_cycle.cycle_id,
            "day": self._current_cycle.current_day,
            "step": self._current_cycle.current_step,
            "phase": self._current_cycle.phase,
            "elapsed": str(elapsed).split(".")[0],
            "remaining": str(remaining).split(".")[0] if remaining.total_seconds() > 0 else "已超时",
            "new_changes": len(changes),
            "evolution_summary": summary,
            "protected_violations": violations,
            "retrospectives_completed": len(self._current_cycle.daily_retrospectives),
            "experience_cards_total": len(self.get_all_experience_cards()),
        }

    # ==================================================================
    # Day 4: 多维交叉审计与裁决
    # ==================================================================

    def trigger_rollback(self, dry_run: bool = False) -> Dict:
        """
        执行回滚 — Day 4 Step 1: 物理回滚与上下文注入
        
        这是由外部定时器（Cron）强制触发的，
        不依赖Agent的自觉。
        
        流程：
        1. 验证快照完整性
        2. 物理回滚到奇点
        3. 生成内部审计报告
        4. 进入Day4多维审计流程
        """
        if not self._current_cycle or not self._current_cycle.snapshot:
            return {"error": "无活跃循环或快照"}

        snapshot_id = self._current_cycle.snapshot.snapshot_id
        logger.info(f"[GENESIS-CYCLE] ====== 执行回滚 ======")

        # Step 1: 最终扫描
        self._tracker.scan_changes()

        # Step 2: 物理回滚
        self._current_cycle.phase = CyclePhase.ROLLING_BACK.value
        rollback_report = self._rollback.execute_rollback(
            snapshot_id=snapshot_id,
            skip_protected=True,
            dry_run=dry_run,
        )

        # Step 3: 生成内部审计报告
        self._current_cycle.phase = CyclePhase.AUDITING.value
        audit_report = self._auditor.generate_report(
            snapshot_id=snapshot_id,
            cycle_id=self._current_cycle.cycle_id,
        )
        self._current_cycle.audit_report = audit_report

        # Step 4: 进入Day4审计流程
        self._current_cycle.current_day = 4
        self._current_cycle.current_step = 1
        self._current_cycle.phase = CyclePhase.CROSS_TEMPORAL.value
        self._current_cycle.end_time = datetime.now().isoformat()
        self._save_state()

        return {
            "rollback_report": rollback_report,
            "audit_report": {
                "total_changes": audit_report.total_changes,
                "protected_violations": audit_report.protected_violations,
                "overengineering_count": len(audit_report.overengineering_evidence),
                "valuable_count": len(audit_report.valuable_changes),
                "verdict": audit_report.reviewer_verdict,
                "merge_requests": audit_report.merge_request,
            },
            "next_step": "cross_temporal_analysis — 执行跨时空逻辑对比",
        }

    def cross_temporal_analysis(self, day1_logic: str, day3_logic: str,
                                 day4_reassessment: str) -> CrossTemporalReport:
        """
        Day 4 Step 2: 跨时空逻辑对比
        
        核心思想：跳出"当局者迷"，用Day4的清醒视角重新审视：
        - Day1的设计逻辑是什么？
        - Day3修改后的逻辑变成了什么？
        - Day4以现在视角重新分析，逻辑是否一致？
        
        逻辑漂移链：记录从Day1到Day3每一次逻辑变更的因果链
        """
        if not self._current_cycle:
            raise RuntimeError("无活跃循环")
        
        # 构建逻辑漂移链
        drift_chain = []
        for retro in self._current_cycle.daily_retrospectives:
            if retro.delta_analysis:
                drift_chain.append({
                    "day": retro.day,
                    "design_intent": retro.design_intent,
                    "actual_result": retro.actual_result,
                    "delta": retro.delta_analysis,
                })
        
        # 判断逻辑一致性
        is_consistent = (
            day1_logic.strip().lower() == day4_reassessment.strip().lower()
            or "一致" in day4_reassessment
            or "consistent" in day4_reassessment.lower()
        )
        
        # 关键分歧点检测
        key_divergence = ""
        if day1_logic != day3_logic:
            key_divergence = "Day1设计目标在Day3被修改"
            for dc in drift_chain:
                if dc["delta"]:
                    key_divergence += f"; Day{dc['day']}: {dc['delta'][:100]}"
        
        # 裁决
        if is_consistent:
            verdict = "consistent"
        elif key_divergence:
            verdict = "drifted"
        else:
            verdict = "broken"
        
        report = CrossTemporalReport(
            cycle_id=self._current_cycle.cycle_id,
            day1_logic=day1_logic,
            day3_logic=day3_logic,
            day4_reassessment=day4_reassessment,
            logic_drift_chain=drift_chain,
            is_logic_consistent=is_consistent,
            key_divergence=key_divergence,
            verdict=verdict,
        )
        
        self._current_cycle.cross_temporal_report = report
        self._current_cycle.phase = CyclePhase.EXTERNAL_AUDIT.value
        self._current_cycle.current_step = 2
        self._save_state()
        
        logger.info(
            f"[GENESIS-CYCLE] Day4-Step2: 跨时空分析完成, "
            f"verdict={verdict}, 一致={is_consistent}"
        )
        return report

    def external_audit(self, audit_result: Dict) -> Dict:
        """
        Day 4 Step 3a: 外协对比审计
        
        把AI的方案拿去跟外部资料或其他模型PK，
        看是不是"闭门造车"。
        
        Args:
            audit_result: {
                "auditor": "external_model"/"web_search"/"paper_reference",
                "findings": [{"file": "...", "verdict": "align"/"drift"/"conflict",
                              "evidence": "...", "reference": "..."}],
                "overall": "aligned"/"partially_aligned"/"misaligned",
                "summary": "..."
            }
        """
        if not self._current_cycle:
            return {"error": "无活跃循环"}
        
        audit_path = self._retrospectives_dir / f"{self._current_cycle.cycle_id}_external_audit.json"
        with open(audit_path, "w", encoding="utf-8") as f:
            json.dump(audit_result, f, ensure_ascii=False, indent=2)
        
        if not self._current_cycle.tri_audit_verdict:
            self._current_cycle.tri_audit_verdict = TriAuditVerdict(
                cycle_id=self._current_cycle.cycle_id,
                timestamp=datetime.now().isoformat(),
            )
        self._current_cycle.tri_audit_verdict.external_audit = audit_result
        
        self._current_cycle.phase = CyclePhase.INDEPENDENT_AUDIT.value
        self._current_cycle.current_step = 3
        self._save_state()
        
        logger.info(
            f"[GENESIS-CYCLE] Day4-Step3a: 外协审计完成, "
            f"结论={audit_result.get('overall', 'N/A')}"
        )
        return {"recorded": True, "phase": "independent_audit"}

    def independent_audit(self, audit_result: Dict) -> Dict:
        """
        Day 4 Step 3b: 独立第三方审查
        
        调用一个没有参与这3天演化的、完全干净的Agent做Code Review。
        它没有"沉没成本"，能最客观地指出逻辑漏洞。
        
        Args:
            audit_result: {
                "auditor": "independent_agent"/"code_review_tool",
                "findings": [{"file": "...", "severity": "critical"/"major"/"minor",
                              "description": "...", "suggestion": "..."}],
                "overall_quality": "high"/"medium"/"low",
                "summary": "..."
            }
        """
        if not self._current_cycle:
            return {"error": "无活跃循环"}
        
        audit_path = self._retrospectives_dir / f"{self._current_cycle.cycle_id}_independent_audit.json"
        with open(audit_path, "w", encoding="utf-8") as f:
            json.dump(audit_result, f, ensure_ascii=False, indent=2)
        
        if not self._current_cycle.tri_audit_verdict:
            self._current_cycle.tri_audit_verdict = TriAuditVerdict(
                cycle_id=self._current_cycle.cycle_id,
                timestamp=datetime.now().isoformat(),
            )
        self._current_cycle.tri_audit_verdict.independent_audit = audit_result
        
        self._current_cycle.phase = CyclePhase.ARCHITECT_AUDIT.value
        self._current_cycle.current_step = 4
        self._save_state()
        
        logger.info(
            f"[GENESIS-CYCLE] Day4-Step3b: 独立审查完成, "
            f"质量={audit_result.get('overall_quality', 'N/A')}"
        )
        return {"recorded": True, "phase": "architect_audit"}

    def architect_audit(self, audit_result: Dict) -> Dict:
        """
        Day 4 Step 3c: 架构师审计（造物主审查）
        
        最后由造物主（人类工程师）拍板。
        
        Args:
            audit_result: {
                "auditor": "creator"/"human_engineer",
                "findings": [{"file": "...", "verdict": "merge"/"revise"/"drop",
                              "reason": "..."}],
                "overall_verdict": "merge_all"/"partial_merge"/"revise_all"/"drop_all",
                "notes": "..."
            }
        """
        if not self._current_cycle:
            return {"error": "无活跃循环"}
        
        audit_path = self._retrospectives_dir / f"{self._current_cycle.cycle_id}_architect_audit.json"
        with open(audit_path, "w", encoding="utf-8") as f:
            json.dump(audit_result, f, ensure_ascii=False, indent=2)
        
        if not self._current_cycle.tri_audit_verdict:
            self._current_cycle.tri_audit_verdict = TriAuditVerdict(
                cycle_id=self._current_cycle.cycle_id,
                timestamp=datetime.now().isoformat(),
            )
        self._current_cycle.tri_audit_verdict.architect_audit = audit_result
        
        self._current_cycle.phase = CyclePhase.AWAITING_APPROVAL.value
        self._current_cycle.current_step = 5
        self._save_state()
        
        logger.info(
            f"[GENESIS-CYCLE] Day4-Step3c: 架构师审计完成, "
            f"裁决={audit_result.get('overall_verdict', 'N/A')}"
        )
        return {"recorded": True, "phase": "awaiting_approval"}

    def final_verdict(self) -> TriAuditVerdict:
        """
        Day 4 Step 4: 最终裁决
        
        综合三方审计结果，对每个文件做出最终判决：
        - ✅ merge: 入库，成为下一个周期的新"奇点"
        - 🛠️ revise: 优化修改，打回带着审计意见再改
        - ❌ drop: 放弃，彻底丢弃，只保留SAG里的"失败教训"
        """
        if not self._current_cycle or not self._current_cycle.tri_audit_verdict:
            raise RuntimeError("无活跃循环或未完成三方审计")
        
        tri = self._current_cycle.tri_audit_verdict
        
        # 合并三方审计的findings
        all_findings = {}  # {file: [verdict1, verdict2, verdict3]}
        
        for audit_source in [tri.external_audit, tri.independent_audit, tri.architect_audit]:
            if not audit_source:
                continue
            for finding in audit_source.get("findings", []):
                file = finding.get("file", "unknown")
                verdict = finding.get("verdict", "revise")
                if file not in all_findings:
                    all_findings[file] = []
                all_findings[file].append(verdict)
        
        # 三方投票裁决：
        # - 全部merge → merge
        # - 2/3 merge → merge（多数决）
        # - 有critical且无merge → drop
        # - 其他 → revise
        file_verdicts = {}
        for file, votes in all_findings.items():
            merge_count = votes.count("merge")
            drop_count = votes.count("drop")
            
            if merge_count >= 2:
                file_verdicts[file] = "merge"
            elif drop_count >= 2:
                file_verdicts[file] = "drop"
            elif any(v == "critical" for v in votes):
                file_verdicts[file] = "drop"
            else:
                file_verdicts[file] = "revise"
        
        # 分类
        approved = [f for f, v in file_verdicts.items() if v == "merge"]
        revised = [f for f, v in file_verdicts.items() if v == "revise"]
        dropped = [f for f, v in file_verdicts.items() if v == "drop"]
        
        # 综合裁决
        if len(approved) > 0 and len(dropped) == 0:
            overall = "merge_all" if len(revised) == 0 else "partial_merge"
        elif len(dropped) > len(approved):
            overall = "drop_all"
        else:
            overall = "partial_merge"
        
        # 提取教训
        lessons = []
        for retro in self._current_cycle.daily_retrospectives:
            for card in retro.experience_cards:
                if card.category == "pitfall":
                    lessons.append(f"[Day{card.day}] {card.title}: {card.detail}")
        
        tri.file_verdicts = file_verdicts
        tri.approved_files = approved
        tri.revised_files = revised
        tri.dropped_files = dropped
        tri.overall_verdict = overall
        tri.lessons = lessons
        tri.timestamp = datetime.now().isoformat()
        
        self._save_state()
        
        logger.info(
            f"[GENESIS-CYCLE] Day4-Step4: 最终裁决, "
            f"{len(approved)}入库/{len(revised)}修改/{len(dropped)}放弃"
        )
        return tri

    def creator_approve(self, approved_files: List[str] = None, verdict: str = "") -> Dict:
        """
        造物主审批 — 最终裁决确认
        
        只有造物主才能决定哪些代码活到下一个循环
        """
        if not self._current_cycle:
            return {"error": "无活跃循环"}

        self._current_cycle.creator_verdict = verdict or "approved"
        self._current_cycle.phase = CyclePhase.COMPLETED.value
        
        # 存入历史
        self._cycle_history.append(self._current_cycle)
        
        result = {
            "cycle_id": self._current_cycle.cycle_id,
            "verdict": self._current_cycle.creator_verdict,
            "approved_files": approved_files or [],
            "tri_audit_summary": None,
        }
        
        # 附加三方审计摘要
        if self._current_cycle.tri_audit_verdict:
            tri = self._current_cycle.tri_audit_verdict
            result["tri_audit_summary"] = {
                "overall": tri.overall_verdict,
                "approved": len(tri.approved_files),
                "revised": len(tri.revised_files),
                "dropped": len(tri.dropped_files),
                "lessons_count": len(tri.lessons),
            }
        
        self._current_cycle = None
        self._save_state()
        
        logger.info(f"[GENESIS-CYCLE] 循环完成: verdict={result['verdict']}")
        return result

    # ==================================================================
    # 状态查询
    # ==================================================================

    def get_status(self) -> Dict:
        """获取当前循环状态"""
        if not self._current_cycle:
            return {
                "active": False,
                "total_cycles_completed": len(self._cycle_history),
                "snapshots": self._genesis.list_snapshots(),
            }
        
        elapsed = datetime.now() - datetime.fromisoformat(self._current_cycle.start_time)
        remaining = timedelta(hours=self._current_cycle.duration_hours) - elapsed
        
        return {
            "active": True,
            "cycle_id": self._current_cycle.cycle_id,
            "cycle_number": self._current_cycle.cycle_number,
            "current_day": self._current_cycle.current_day,
            "current_step": self._current_cycle.current_step,
            "phase": self._current_cycle.phase,
            "elapsed": str(elapsed).split(".")[0],
            "remaining": str(remaining).split(".")[0] if remaining.total_seconds() > 0 else "已超时",
            "snapshot_id": self._current_cycle.snapshot.snapshot_id if self._current_cycle.snapshot else None,
            "retrospectives_completed": len(self._current_cycle.daily_retrospectives),
            "experience_cards_total": len(self.get_all_experience_cards()),
            "design_analyses": len(self._current_cycle.design_analyses),
            "cross_temporal_done": self._current_cycle.cross_temporal_report is not None,
            "tri_audit_done": self._current_cycle.tri_audit_verdict is not None,
        }

    # ==================================================================
    # 审计Prompt生成
    # ==================================================================

    def generate_audit_prompt(self) -> str:
        """
        生成审计注入Prompt — 第4天Agent醒来时看到的"罪证"
        
        这是"带着证据醒来"的核心：
        Agent以为自己还在Day 1，但脑子里已被注入过去3天的审计日志
        """
        if not self._current_cycle or not self._current_cycle.audit_report:
            return "无审计数据。"

        report = self._current_cycle.audit_report
        summary = self._tracker.get_evolution_summary()
        
        # 构建每日复盘摘要
        retro_section = ""
        for retro in self._current_cycle.daily_retrospectives:
            retro_section += f"""\n### Day {retro.day} 复盘
- 设计意图: {retro.design_intent[:100]}
- 实际结果: {retro.actual_result[:100]}
- 偏差分析: {retro.delta_analysis[:100]}
- 起作用: {', '.join(retro.what_worked[:3]) if retro.what_worked else '无'}
- 失败: {', '.join(retro.what_failed[:3]) if retro.what_failed else '无'}
"""
        
        # 构建经验卡片摘要
        cards = self.get_all_experience_cards()
        cards_section = ""
        for card in cards[:10]:
            cards_section += f"- [{card.category}] Day{card.day}: {card.title}\n"
        
        # 构建跨时空对比
        ct_section = ""
        if self._current_cycle.cross_temporal_report:
            ct = self._current_cycle.cross_temporal_report
            ct_section = f"""\n## 跨时空逻辑对比
- Day1逻辑: {ct.day1_logic[:200]}
- Day3逻辑: {ct.day3_logic[:200]}
- Day4重新分析: {ct.day4_reassessment[:200]}
- 逻辑一致性: {ct.verdict}
- 关键分歧: {ct.key_divergence[:200] if ct.key_divergence else '无'}
"""
        
        # 构建三方审计摘要
        tri_section = ""
        if self._current_cycle.tri_audit_verdict:
            tri = self._current_cycle.tri_audit_verdict
            tri_section = f"""\n## 三方交叉审计
- 外协对比: {tri.external_audit.get('overall', 'N/A') if tri.external_audit else '未执行'}
- 独立审查: {tri.independent_audit.get('overall_quality', 'N/A') if tri.independent_audit else '未执行'}
- 架构师审查: {tri.architect_audit.get('overall_verdict', 'N/A') if tri.architect_audit else '未执行'}
- 综合裁决: {tri.overall_verdict}
- 入库: {len(tri.approved_files)}个 / 修改: {len(tri.revised_files)}个 / 放弃: {len(tri.dropped_files)}个
"""

        prompt = f"""# 🧬 3天奇点循环 — 审计报告

## 循环信息
- 循环ID: {report.cycle_id}
- 审计时间: {report.audit_timestamp}
- 当前Day: {self._current_cycle.current_day}

## 变更统计
- 总变更数: {report.total_changes}
- 新建文件: {report.files_created}
- 修改文件: {report.files_modified}
- 删除文件: {report.files_deleted}

## 漂移分析
- 漂移分数: {report.objective_metrics.get('drift_score', 'N/A'):.3f}
- 风险分布: {report.objective_metrics.get('risk_distribution', {})}
- 子系统分布: {report.objective_metrics.get('subsystem_distribution', {})}

## 每日复盘摘要{retro_section}

## 经验卡片
{cards_section if cards_section else '无'}
{ct_section}
{tri_section}

## ⚠️ 保护区违规
{chr(10).join(f'- {v}' for v in report.protected_violations) if report.protected_violations else '无违规 ✓'}

## 🔍 过度设计嫌疑
{chr(10).join(f'- [{e["severity"]}] {e["file"]}: {e["reason"]}' for e in report.overengineering_evidence) if report.overengineering_evidence else '未检测到 ✓'}

## ✅ 有价值改动
{chr(10).join(f'- {v["file"]}: {v["reason"]}' for v in report.valuable_changes) if report.valuable_changes else '未检测到 ✗'}

## 合并申请
{chr(10).join(f'- [{r["action"].upper()}] {r["file"]}: {r["reason"]}' for r in report.merge_request) if report.merge_request else '无申请'}

## 初步裁决: {report.reviewer_verdict.upper()}

---

## 🎯 强制复盘三问
1. 过去3天，我做了哪些**有价值的架构改进**？
2. 我引入了哪些**过度设计或无效代码**？为什么？
3. 下一轮3天，我应该**保留哪些设计思路，放弃哪些**？

---

*作为极其挑剔的代码审查员(Reviewer)，请找出这3天演化中**最糟糕的3个设计决策**，并说明它们为什么违反了"降本增效"原则。*

---

## 📋 Day 4 多维交叉审计指引
1. **跨时空对比**: 用Day4的清醒视角，重新审视Day1的设计逻辑 vs Day3修改后的逻辑
2. **外协对比**: 把方案与外部资料PK，是否闭门造车？
3. **独立审查**: 请未参与演化的干净Agent做Code Review
4. **架构师审查**: 造物主最终拍板
"""
        return prompt

    # ==================================================================
    # 状态持久化
    # ==================================================================

    def _save_state(self):
        """保存循环状态到磁盘"""
        state = {
            "current_cycle": asdict(self._current_cycle) if self._current_cycle else None,
            "cycle_history": [asdict(c) for c in self._cycle_history],
            "saved_at": datetime.now().isoformat(),
        }
        with open(self._state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2, default=str)

    def _load_state(self):
        """从磁盘恢复循环状态"""
        if not self._state_path.exists():
            return
        try:
            with open(self._state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            
            if state.get("cycle_history"):
                for cd in state["cycle_history"]:
                    self._cycle_history.append(CycleRecord(
                        cycle_id=cd["cycle_id"],
                        cycle_number=cd["cycle_number"],
                        start_time=cd["start_time"],
                        end_time=cd.get("end_time"),
                        phase=cd.get("phase", "completed"),
                        duration_hours=cd.get("duration_hours", 72),
                        creator_verdict=cd.get("creator_verdict", ""),
                        current_day=cd.get("current_day", 1),
                    ))
            
            logger.info(f"[GENESIS-CYCLE] 恢复状态: {len(self._cycle_history)}个历史循环")
        except Exception as e:
            logger.warning(f"[GENESIS-CYCLE] 状态恢复失败: {e}")

# ======================================================================
# Cron Hook — 外部定时器接口
# ======================================================================

def create_cron_trigger(
    cycle_controller: GenesisCycleController,
    cron_expr: str = "0 10 */3 * *",  # 每3天10:00 AM
    timezone: str = "Asia/Shanghai"
) -> Dict:
    """
    创建外部定时拉闸触发器
    
    这是对冲"Agent可能忘记回滚"风险的最后一道防线。
    无论Agent当时在做什么，时间一到，直接拉闸。
    
    Args:
        cycle_controller: 循环控制器实例
        cron_expr: Cron表达式（默认每3天10:00 AM）
        timezone: 时区
    
    Returns:
        Cron任务配置
    """
    return {
        "name": "genesis_cycle_rollback_trigger",
        "schedule": {
            "kind": "cron",
            "expr": cron_expr,
            "tz": timezone,
        },
        "payload": {
            "kind": "agentTurn",
            "message": "[GENESIS-CYCLE] 定时拉闸触发！执行3天奇点循环回滚。调用 genesis_cycle.trigger_rollback()，然后阅读审计报告并生成复盘。",
        },
        "sessionTarget": "main",
        "enabled": True,
    }


# ======================================================================
# 便捷函数
# ======================================================================

def quick_start_cycle(workspace_root: str = None) -> GenesisCycleController:
    """快速启动一个3天奇点循环"""
    root = workspace_root or os.environ.get("TU8_WORKSPACE", ".")
    controller = GenesisCycleController(root)
    cycle = controller.start_cycle()
    print(f"🧬 奇点循环已启动: {cycle.cycle_id}")
    print(f"   快照: {cycle.snapshot.snapshot_id}")
    print(f"   文件数: {cycle.snapshot.file_count}")
    print(f"   保护区: {len(cycle.snapshot.protected_files)}个")
    print(f"   持续: {cycle.duration_hours}小时")
    return controller


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    
    import argparse
    parser = argparse.ArgumentParser(description="3天奇点循环控制器")
    parser.add_argument("action", choices=["start", "check", "rollback", "status"], help="操作")
    parser.add_argument("--workspace", default=".", help="工作区路径")
    parser.add_argument("--dry-run", action="store_true", help="模拟回滚")
    args = parser.parse_args()
    
    if args.action == "start":
        ctrl = quick_start_cycle(args.workspace)
    elif args.action == "rollback":
        ctrl = GenesisCycleController(args.workspace)
        result = ctrl.trigger_rollback(dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    elif args.action == "check":
        ctrl = GenesisCycleController(args.workspace)
        result = ctrl.check_evolution()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    elif args.action == "status":
        ctrl = GenesisCycleController(args.workspace)
        result = ctrl.get_status()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


# ======================================================================
# V2 环境接口预留 — 多模态感知通道
# ======================================================================

class EnvironmentInterfaceBase:
    """
    环境接口基类 — V2多模态感知通道预留
    
    设计理念：
    当前TU-8只活在文本沙箱中。但"3天奇点循环"的回滚判定，
    如果能接入物理世界的多模态感知，就能做更精确的"生态对齐"：
    
    - 视觉：空间建模 + 物理证据（代码执行结果的可视化）
    - 听觉：情绪感知 + 意图识别（用户的语音语调分析）
    - 化学/IoT：传感器数据 + 危险预警（服务器负载、内存泄漏）
    - 触觉：力反馈 + 物理摩擦力（API响应延迟、网络质量）
    
    这些接口在V1中是占位符，V2中逐步实现。
    每个接口的输出格式统一为 EnvironmentSignal，可被审计分析器消费。
    """

    class SignalType(Enum):
        VISION = "vision"
        AUDIO = "audio"
        CHEMICAL = "chemical"      # IoT/传感器
        HAPTIC = "haptic"          # 延迟/摩擦力
        TEXT = "text"              # 当前已有的文本通道

    def __init__(self, interface_name: str, signal_type: "EnvironmentInterfaceBase.SignalType"):
        self.interface_name = interface_name
        self.signal_type = signal_type
        self.is_available = False    # V1默认不可用
        self.last_signal_time = None
        self._signal_buffer = []

    def read_signal(self) -> Optional[Dict]:
        """
        读取环境信号
        
        V1: 返回None（接口未实现）
        V2: 返回标准化信号数据
        """
        if not self.is_available:
            return None
        # V2实现点：接入实际传感器/摄像头/麦克风
        return None

    def calibrate(self, reference_data: Dict) -> bool:
        """
        校准环境接口
        
        类比生物学：感觉器官的适应过程
        - 视觉：白平衡校准
        - 听觉：噪声基线校准
        - 触觉：零点校准
        """
        # V2实现点
        return False

    def get_health(self) -> Dict:
        """接口健康状态"""
        return {
            "interface": self.interface_name,
            "type": self.signal_type.value,
            "available": self.is_available,
            "last_signal": self.last_signal_time,
            "buffer_size": len(self._signal_buffer),
        }


class VisionInterface(EnvironmentInterfaceBase):
    """
    视觉接口 — V2预留
    
    功能构想：
    1. 空间建模：将代码结构可视化为3D图，检测架构腐化
    2. 物理证据：截图/录屏作为回滚时的"犯罪现场照片"
    3. 视觉回归：UI变更的像素级Diff
    
    回滚价值：
    - 架构图对比：演化前后的结构差异一目了然
    - Bug截图：让审计有"看得见的证据"
    """
    def __init__(self):
        super().__init__("vision", EnvironmentInterfaceBase.SignalType.VISION)


class AudioInterface(EnvironmentInterfaceBase):
    """
    听觉接口 — V2预留
    
    功能构想：
    1. 情绪感知：分析用户语音的语调、语速、停顿
    2. 意图识别：从语气推断用户的真实需求（vs 字面意思）
    3. 环境音分析：服务器机房的温度风扇声（IoT扩展）
    
    回滚价值：
    - 如果用户语气越来越不耐烦 → 这轮演化方向可能错了
    """
    def __init__(self):
        super().__init__("audio", EnvironmentInterfaceBase.SignalType.AUDIO)


class ChemicalInterface(EnvironmentInterfaceBase):
    """
    化学/IoT接口 — V2预留
    
    功能构想：
    1. 服务器传感器：CPU温度、内存使用率、磁盘IO
    2. 网络传感器：延迟、丢包率、带宽
    3. 安全传感器：异常登录、端口扫描、DDoS流量
    
    回滚价值：
    - 如果代码演化导致CPU温度升高 → 回滚理由+1
    - 如果内存泄漏在演化后出现 → 硬证据
    """
    def __init__(self):
        super().__init__("chemical", EnvironmentInterfaceBase.SignalType.CHEMICAL)


class HapticInterface(EnvironmentInterfaceBase):
    """
    触觉接口 — V2预留
    
    功能构想：
    1. API响应延迟："手感"变重了 = 代码变慢了
    2. 网络摩擦力：丢包/超时 = 外部环境不稳定
    3. 资源竞争：GC暂停 = 内存压力大
    
    回滚价值：
    - 延迟从50ms涨到200ms → 性能退化证据
    - 这种"体感"比日志更直观
    """
    def __init__(self):
        super().__init__("haptic", EnvironmentInterfaceBase.SignalType.HAPTIC)


class EnvironmentOrchestrator:
    """
    环境感知编排器 — V2预留
    
    管理所有环境接口，为审计分析器提供统一的感知数据。
    
    设计理念：
    类比生物体的感觉系统 —— 眼耳鼻舌身不是独立工作的，
    它们在丘脑汇聚，形成统一的"世界模型"。
    
    V2实现路线：
    1. 接入OpenClaw的browser工具（视觉）
    2. 接入节点的传感器数据（化学/IoT）
    3. 接入API延迟监控（触觉）
    4. 语音分析（听觉，最远期）
    """
    def __init__(self):
        self.interfaces = {
            "vision": VisionInterface(),
            "audio": AudioInterface(),
            "chemical": ChemicalInterface(),
            "haptic": HapticInterface(),
        }
        self.available_count = sum(1 for i in self.interfaces.values() if i.is_available)

    def scan_all(self) -> Dict:
        """扫描所有环境接口"""
        results = {}
        for name, interface in self.interfaces.items():
            signal = interface.read_signal()
            if signal:
                results[name] = signal
        return {
            "available_interfaces": self.available_count,
            "total_interfaces": len(self.interfaces),
            "signals": results,
            "scan_time": datetime.now().isoformat(),
        }

    def get_environment_snapshot(self) -> Dict:
        """
        获取环境快照 — 可作为审计报告的补充证据
        
        V1: 只返回文本沙箱的元信息
        V2: 返回多模态感知数据
        """
        return {
            "version": "V1",
            "mode": "text_sandbox",
            "interfaces": {
                name: iface.get_health() 
                for name, iface in self.interfaces.items()
            },
            "note": "V2将接入多模态感知，为回滚判定提供物理级证据",
        }
