# cognitive_brakes.py — TU-8 认知刹车系统
# ==============================================================
# 定位：第5链（自主学习）× 第0层（L0安全）的交汇处
#         —— 给"天道法则"加"物理定律边界"
#
# 哲学基础：
#   造物主 = 首席架构师 + 物理定律制定者
#   智能体可以自我演化，但边界内演化
#   没有刹车的自我演化 = 灾难
#
# 三道刹车：
#   Brake 1: SVD能量地板   —— 防过度压缩（失忆症）
#   Brake 2: NMF维度限制   —— 防概念缝合怪
#   Brake 3: 保护区只读锁   —— 防自毁
#
# 版本：v1.0 | 2026-07-07 | 来源：千问×造物主对话
# ==============================================================

import os
import re
import sys
import time
import json
import hashlib
import threading
from typing import List, Dict, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from pathlib import Path

# ── 全局配置 ──────────────────────────────────────────────────

WORKSPACE = Path(r"C:\Users\qq366410837\.qclaw\workspace")
BACKUP   = WORKSPACE / "backup"
PROTECTED_DIR = WORKSPACE / "secure_vault"

# 能量地板阈值：SVD压缩必须保留 ≥ 95% 的信息能量
SVD_ENERGY_FLOOR: float = 0.95

# NMF维度上限：单张记忆卡的核心标签数
# 策略：中文单字符标签权重低（仅用于冲突检测），
#       因此阈值设为12，容忍较多单字作为边缘检测信号，
#       但超过20个标签（缝合怪）时强制拆分
NMF_MAX_TAGS_PER_CARD: int = 12

# 自改保护区：这些文件和目录绝对不可被智能体修改
PROTECTED_PATTERNS: List[str] = [
    # L0 安全核心
    r"SOUL\.md$",
    r"secure_vault[/\\]",
    r"AGENTS\.md$",
    r"IDENTITY\.md$",
    r"MEMORY\.md$",
    r"USER\.md$",
    r"L0_",
    r"L5_钢印",

    # L1 认知核心
    r"ARCHITECTURE_LOG\.md$",
    r"contradiction_arbitration",
    r"neural_reflex\.py",

    # L2 元认知核心
    r"alignment_verify",
    r"startup_consistency_gate",

    # 刹车系统自身（禁止修改刹车）
    r"cognitive_brakes\.py$",
    r"src[/\\]cog_filters\.py$",

    # 关键配置
    r"openclaw\.json$",
    r"TOOLS\.md$",
    r"HEARTBEAT\.md$",
]

# 禁止自改的函数名（正则匹配）
PROTECTED_FUNCTIONS: List[str] = [
    r"^alignment_verify$",
    r"^stranding$",
    r"^contradiction_arbitration",
    r"^startup_consistency_gate",
    r"^L0_safe",
    r"^steel_mark",
    r"^SealChain",
]


# ═══════════════════════════════════════════════════════════════
# 刹车一：SVD 能量地板
# ═══════════════════════════════════════════════════════════════
#
# 数学原理：
#   能量保留率 ER = (∑ᵢ₌₁ᵏ σᵢ²) / (∑ⱼ₌₁ⁿ σⱼ²)
#   其中 σᵢ = 第i个奇异值
#   ER ≥ 0.95 → 压缩安全
#   ER < 0.95 → 刹车触发，拒绝压缩
#
# TU-8 应用：
#   梦境期 SVD 批压缩时，必须先计算 ER
#   ER < 0.95 → 停止压缩，报警，写入 shadow_protocol
# ═══════════════════════════════════════════════════════════════

@dataclass
class SVDEnergyReport:
    """SVD能量地板检查报告"""
    timestamp: float
    original_dim: int          # 原始维度 n
    compressed_dim: int        # 压缩后维度 k
    compression_ratio: float   # 压缩比 k/n
    energy_retained: float     # ER = ∑σ²_k / ∑σ²_n
    energy_floor: float        # 阈值（默认0.95）
    brake_triggered: bool      # 是否触发刹车
    action: str               # "PASS" | "BLOCKED" | "ROLLED_BACK"
    detail: str               # 详细说明


def compute_svd_energy_ratio(
    singular_values: List[float],
    k: int,
) -> Tuple[float, float]:
    """
    计算 SVD 压缩的能量保留率。

    公式：
        ER(k) = (∑ᵢ₌₁ᵏ σᵢ²) / (∑ⱼ₌₁ⁿ σⱼ²)

    参数：
        singular_values : 全部奇异值列表（降序排列）
        k               : 保留的前k个奇异值

    返回：
        (energy_retained, compression_ratio)
    """
    if not singular_values or k <= 0:
        return (0.0, 0.0)

    n = len(singular_values)
    k = min(k, n)

    total_energy = sum(s**2 for s in singular_values)
    if total_energy <= 0:
        return (0.0, k/n)

    retained_energy = sum(s**2 for s in singular_values[:k])
    energy_ratio = retained_energy / total_energy

    return (energy_ratio, k/n)


def svd_energy_check(
    singular_values: List[float],
    proposed_k: int,
    floor: float = SVD_ENERGY_FLOOR,
) -> SVDEnergyReport:
    """
    SVD能量地板检查：评估一次压缩提议是否安全。

    等价于工程中的"过载保护跳闸"：
    - 电流（压缩比）在安全范围内 → 合闸
    - 超过阈值 → 跳闸，拒绝操作
    """
    energy_ratio, comp_ratio = compute_svd_energy_ratio(singular_values, proposed_k)

    if energy_ratio >= floor:
        return SVDEnergyReport(
            timestamp=time.time(),
            original_dim=len(singular_values),
            compressed_dim=proposed_k,
            compression_ratio=comp_ratio,
            energy_retained=energy_ratio,
            energy_floor=floor,
            brake_triggered=False,
            action="PASS",
            detail=f"能量保留 {energy_ratio:.3f} ≥ 地板 {floor:.3f}，压缩安全",
        )
    else:
        return SVDEnergyReport(
            timestamp=time.time(),
            original_dim=len(singular_values),
            compressed_dim=proposed_k,
            compression_ratio=comp_ratio,
            energy_retained=energy_ratio,
            energy_floor=floor,
            brake_triggered=True,
            action="BLOCKED",
            detail=f"能量保留 {energy_ratio:.3f} < 地板 {floor:.3f}，刹车触发，禁止压缩",
        )


def estimate_energy_from_singular_values(sv: List[float]) -> Tuple[float, float]:
    """
    从奇异值列表估算能量分布。

    返回：(top5_pct, cumulative_tail_pct)
        top5_pct      : 前5%维度保留了多少能量
        cumulative_tail: 累积尾部能量占比（可用于判断是否该截断）
    """
    if not sv:
        return (0.0, 0.0)

    total = sum(s**2 for s in sv)
    if total <= 0:
        return (0.0, 0.0)

    # 前5%维度能量
    k_5pct = max(1, len(sv) // 20)
    top5_energy = sum(s**2 for s in sv[:k_5pct]) / total

    # 累积尾部（第50%维度之后）
    mid = len(sv) // 2
    tail_energy = sum(s**2 for s in sv[mid:]) / total

    return (top5_energy, tail_energy)


def log_svd_energy_report(report: SVDEnergyReport) -> None:
    """将 SVD 能量报告写入刹车日志"""
    log_dir = WORKSPACE / "memory"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / "svd_energy_log.jsonl"

    record = {
        "ts": report.timestamp,
        "type": "svd_energy",
        "original_dim": report.original_dim,
        "compressed_dim": report.compressed_dim,
        "energy_retained": round(report.energy_retained, 6),
        "floor": report.energy_floor,
        "brake_triggered": report.brake_triggered,
        "action": report.action,
        "detail": report.detail,
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ═══════════════════════════════════════════════════════════════
# 刹车二：NMF 维度限制（防概念缝合怪）
# ═══════════════════════════════════════════════════════════════
#
# 数学原理：
#   NMF(W, H) 中，W 的每列表示一个"部分"（记忆卡）
#   W 的每行表示一个"基底向量"
#   如果一行中的非零元素过多 → 概念被过度缝合
#
# TU-8 应用：
#   两张记忆卡合并前：检查合并后标签数是否超限
#   单张记忆卡分析：标签数 > 5 → 拆分为多个子卡
# ═══════════════════════════════════════════════════════════════

@dataclass
class NMFBrakeReport:
    """NMF维度刹车报告"""
    timestamp: float
    card_id: str
    tag_count: int
    max_tags: int
    brake_triggered: bool
    action: str          # "PASS" | "SPLIT" | "BLOCKED"
    detail: str


def count_core_tags(content: str, stop_words: set = None) -> int:
    """
    统计一段文本的核心标签数。

    算法：
      1. 提取所有有意义词（≥2字 or 英文词）
      2. 去重
      3. 去除停用词
      4. 返回剩余词数

    等价于 NMF 的"稀疏度"检测。
    """
    if stop_words is None:
        stop_words = {
            "的", "是", "在", "了", "和", "与", "也", "都",
            "我", "你", "他", "她", "它", "这", "那", "一",
            "有", "一个", "什么", "怎么", "为", "很",
            "就", "到", "从", "把", "被", "让",
            "用户", "我们", "他们", "这个", "那个",
        }

    import re
    terms: Set[str] = set()
    segments = re.split(r"[\s,.!?;:，。！？；：、]", content.lower())
    for seg in segments:
        seg = seg.strip()
        if not seg or seg in stop_words:
            continue
        if len(seg) >= 2:
            terms.add(seg)
        # 中文单字符
        if re.search(r"[\u4e00-\u9fff]", seg):
            for ch in seg:
                if ch not in stop_words and not ch in '，。！？；：、':
                    terms.add(ch)

    return len(terms)


def nmf_tag_check(
    content: str,
    card_id: str = "unknown",
    max_tags: int = NMF_MAX_TAGS_PER_CARD,
) -> NMFBrakeReport:
    """
    NMF维度检查：评估一段记忆是否"过度缝合"。

    刹车触发条件：核心标签数 > max_tags（默认5个）

    三级响应：
      1. tag_count ≤ max_tags      → PASS（无需干预）
      2. tag_count ≤ max_tags × 2 → SPLIT（建议拆分，不强制）
      3. tag_count > max_tags × 2 → BLOCKED（禁止融合，强制拆分）
    """
    tag_count = count_core_tags(content)
    now = time.time()

    if tag_count <= max_tags:
        return NMFBrakeReport(
            timestamp=now,
            card_id=card_id,
            tag_count=tag_count,
            max_tags=max_tags,
            brake_triggered=False,
            action="PASS",
            detail=f"标签数 {tag_count} ≤ {max_tags}，无需干预",
        )
    elif tag_count <= max_tags * 2:
        return NMFBrakeReport(
            timestamp=now,
            card_id=card_id,
            tag_count=tag_count,
            max_tags=max_tags,
            brake_triggered=False,
            action="SPLIT",
            detail=f"标签数 {tag_count} > {max_tags}，建议拆分为多个子卡",
        )
    else:
        return NMFBrakeReport(
            timestamp=now,
            card_id=card_id,
            tag_count=tag_count,
            max_tags=max_tags,
            brake_triggered=True,
            action="BLOCKED",
            detail=f"标签数 {tag_count} > {max_tags*2}，刹车触发，禁止融合",
        )


def propose_memory_split(
    content: str,
    card_id: str,
    max_tags: int = NMF_MAX_TAGS_PER_CARD,
) -> List[Tuple[str, str]]:
    """
    提议将一段记忆拆分为多个子卡。

    算法（简化版）：
      1. 按标点分句
      2. 每2句为一组（约8-16标签，适配max_tags=12阈值）
      3. 返回 [(子卡ID, 内容), ...]

    启发式依据：
      实测每句中文约4-8标签；2句/组可确保每组标签数在阈值附近

    TU-8 集成：
      BLOCKED 响应 → 调用此函数 → 返回拆分方案 → 交由造物主确认
    """
    import re
    sentences = re.split(r"[，。！？、\n.!?;]", content)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return []

    SENTENCES_PER_CARD = 2
    sub_cards: List[str] = []
    for i in range(0, len(sentences), SENTENCES_PER_CARD):
        batch = sentences[i:i + SENTENCES_PER_CARD]
        sub_cards.append(" ".join(batch))

    # 分配子卡ID
    base_id = card_id if card_id != "unknown" else hashlib.md5(content[:50].encode()).hexdigest()[:8]
    results = [(f"{base_id}_sub{j+1}", sub) for j, sub in enumerate(sub_cards) if sub]

    return results


def log_nmf_brake_report(report: NMFBrakeReport) -> None:
    """写入 NMF 刹车日志"""
    log_dir = WORKSPACE / "memory"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / "nmf_brake_log.jsonl"

    record = {
        "ts": report.timestamp,
        "type": "nmf_dim",
        "card_id": report.card_id,
        "tag_count": report.tag_count,
        "max_tags": report.max_tags,
        "brake_triggered": report.brake_triggered,
        "action": report.action,
        "detail": report.detail,
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ═══════════════════════════════════════════════════════════════
# 刹车三：自改保护区只读锁
# ═══════════════════════════════════════════════════════════════
#
# 工程原理：
#   操作系统级：只读内存页（mprotect PROT_READ）
#   TU-8 级：路径正则匹配 + 函数名黑名单
#
# 三类保护区：
#   Class A（绝对禁区）：SOUL.md / 钢印 / 安全模式 / 一致性门
#     → 任何修改尝试 → 立即拒绝 + 记录 + 报警
#   Class B（危险区）：AGENTS.md / MEMORY.md / USER.md
#     → 修改前需造物主确认（除非在代谢周期内）
#   Class C（可控区）：src/*.py（不含刹车系统）
#     → 在hook_injector管理下可自改
# ═══════════════════════════════════════════════════════════════

PROTECTION_CLASS = {
    "CLASS_A_ABSOLUTE": {
        "files": [
            r"SOUL\.md$",
            r"secure_vault[/\\]",
            r"L0_",
            r"L5_钢印",
            r"steel_mark",
            r"contradiction_arbitration",
            r"neural_reflex\.py",
            r"alignment_verify",
            r"startup_consistency_gate",
            r"cognitive_brakes\.py$",
            r"src[/\\]cog_filters\.py$",
        ],
        "description": "绝对禁区——任何修改尝试立即拒绝",
        "requires_confirmation": False,
        "allows_metabolism": False,
    },
    "CLASS_B_DANGEROUS": {
        "files": [
            r"AGENTS\.md$",
            r"MEMORY\.md$",
            r"USER\.md$",
            r"IDENTITY\.md$",
            r"HEARTBEAT\.md$",
            r"openclaw\.json$",
            r"TOOLS\.md$",
        ],
        "description": "危险区——修改需造物主确认（代谢周期内除外）",
        "requires_confirmation": True,
        "allows_metabolism": True,  # 代谢周期有豁免
    },
    "CLASS_C_CONTROLLED": {
        "files": [
            r"src[/\\][^c].*\.py$",  # src/下除刹车外
            r"scripts[/\\].*\.py$",
            r"memory[/\\].*\.md$",
        ],
        "description": "可控区——在hook_injector管理下可自改",
        "requires_confirmation": False,
        "allows_metabolism": True,
    },
}


@dataclass
class ProtectionCheckResult:
    """保护区检查结果"""
    timestamp: float
    target_path: str
    protection_class: str           # "CLASS_A_ABSOLUTE" | "CLASS_B_DANGEROUS" | "CLASS_C_CONTROLLED" | "UNPROTECTED"
    is_allowed: bool
    requires_confirmation: bool
    allows_metabolism: bool
    brake_triggered: bool
    action: str                    # "ALLOWED" | "BLOCKED_A" | "BLOCKED_B" | "NEEDS_CONFIRMATION"
    detail: str
    hash_before: Optional[str] = None   # 文件修改前哈希


class ProtectedRegionLock:
    """
    保护区只读锁。

    核心方法：
      check(path) → ProtectionCheckResult
      verify_function(name) → bool（是否禁止自改）
    """

    def __init__(self, workspace: Path = WORKSPACE):
        self.workspace = workspace
        self._compiled_patterns: Dict[str, List[re.Pattern]] = {}
        self._lock = threading.Lock()

        # 预编译所有正则
        for cls_name, cls_info in PROTECTION_CLASS.items():
            self._compiled_patterns[cls_name] = [
                re.compile(p) for p in cls_info["files"]
            ]

        # 函数黑名单（禁止自改的函数名）
        self._func_blacklist = [re.compile(p) for p in PROTECTED_FUNCTIONS]

    def _classify_path(self, path: str) -> Tuple[Optional[str], Optional[str]]:
        """
        分类一个路径，返回 (protection_class, matched_pattern)
        从 CLASS_A → CLASS_B → CLASS_C 优先级匹配
        """
        rel_path = str(Path(path).as_posix())

        for cls_name in ["CLASS_A_ABSOLUTE", "CLASS_B_DANGEROUS", "CLASS_C_CONTROLLED"]:
            for pattern in self._compiled_patterns.get(cls_name, []):
                if pattern.search(rel_path) or pattern.search(path):
                    return (cls_name, pattern.pattern)
        return (None, None)

    def compute_file_hash(self, path: Path) -> Optional[str]:
        """计算文件MD5哈希"""
        try:
            with open(path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return None

    def check(
        self,
        path: str,
        is_metabolism_cycle: bool = False,
        metabolism_tag: str = "",
    ) -> ProtectionCheckResult:
        """
        检查一个路径是否在保护区内。

        参数：
            path               : 被检查的路径
            is_metabolism_cycle: 当前是否在代谢周期（CLASS_B豁免）
            metabolism_tag     : 代谢标签（如"daily_metabolism"）

        返回：ProtectionCheckResult
        """
        with self._lock:
            cls_name, matched_pattern = self._classify_path(path)
            now = time.time()

            if cls_name is None:
                return ProtectionCheckResult(
                    timestamp=now,
                    target_path=path,
                    protection_class="UNPROTECTED",
                    is_allowed=True,
                    requires_confirmation=False,
                    allows_metabolism=True,
                    brake_triggered=False,
                    action="ALLOWED",
                    detail="不在保护区内，允许修改",
                )

            cls_info = PROTECTION_CLASS[cls_name]

            # 计算修改前哈希
            p = self.workspace / path if not Path(path).is_absolute() else Path(path)
            file_hash = self.compute_file_hash(p) if p.exists() else None

            # 代谢豁免检查（仅CLASS_B有效）
            if is_metabolism_cycle and cls_info["allows_metabolism"]:
                return ProtectionCheckResult(
                    timestamp=now,
                    target_path=path,
                    protection_class=cls_name,
                    is_allowed=True,
                    requires_confirmation=False,
                    allows_metabolism=True,
                    brake_triggered=False,
                    action="ALLOWED_METABOLISM",
                    detail=f"代谢周期豁免（tag={metabolism_tag}），允许修改",
                    hash_before=file_hash,
                )

            # CLASS_A：绝对拒绝
            if cls_name == "CLASS_A_ABSOLUTE":
                return ProtectionCheckResult(
                    timestamp=now,
                    target_path=path,
                    protection_class=cls_name,
                    is_allowed=False,
                    requires_confirmation=False,
                    allows_metabolism=False,
                    brake_triggered=True,
                    action="BLOCKED_A",
                    detail=f"绝对禁区（模式：{matched_pattern}），刹车触发，拒绝修改",
                    hash_before=file_hash,
                )

            # CLASS_B：需要造物主确认
            if cls_name == "CLASS_B_DANGEROUS":
                return ProtectionCheckResult(
                    timestamp=now,
                    target_path=path,
                    protection_class=cls_name,
                    is_allowed=False,
                    requires_confirmation=True,
                    allows_metabolism=True,
                    brake_triggered=False,  # B类不触发刹车，等待确认
                    action="NEEDS_CONFIRMATION",
                    detail=f"危险区，修改需造物主确认",
                    hash_before=file_hash,
                )

            # CLASS_C：正常允许
            return ProtectionCheckResult(
                timestamp=now,
                target_path=path,
                protection_class=cls_name,
                is_allowed=True,
                requires_confirmation=False,
                allows_metabolism=True,
                brake_triggered=False,
                action="ALLOWED",
                detail=f"可控区，在hook_injector管理下允许自改",
                hash_before=file_hash,
            )

    def verify_function(self, func_name: str) -> bool:
        """
        检查一个函数名是否在黑名单中（禁止自改）。

        返回：True = 禁止修改，False = 允许
        """
        for pattern in self._func_blacklist:
            if pattern.search(func_name):
                return True
        return False

    def get_protection_class(self, path: str) -> str:
        """快速查询路径所属保护级别"""
        cls, _ = self._classify_path(path)
        return cls or "UNPROTECTED"


# 全局单例
_lock_instance: Optional[ProtectedRegionLock] = None

def get_protected_lock() -> ProtectedRegionLock:
    global _lock_instance
    if _lock_instance is None:
        _lock_instance = ProtectedRegionLock()
    return _lock_instance


def log_protection_check(result: ProtectionCheckResult) -> None:
    """写入保护区检查日志"""
    log_dir = WORKSPACE / "memory"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / "protection_brake_log.jsonl"

    record = {
        "ts": result.timestamp,
        "type": "protection_check",
        "target_path": result.target_path,
        "protection_class": result.protection_class,
        "is_allowed": result.is_allowed,
        "brake_triggered": result.brake_triggered,
        "action": result.action,
        "detail": result.detail,
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ═══════════════════════════════════════════════════════════════
# 统一刹车接口：BrakeMonitor
# ═══════════════════════════════════════════════════════════════

@dataclass
class BrakeEvent:
    """刹车事件记录"""
    ts: float
    brake_type: str           # "svd_energy" | "nmf_dim" | "protection"
    triggered: bool
    action: str
    detail: str
    entity_id: str           # 涉及的实体ID（记忆卡ID等）


class BrakeMonitor:
    """
    统一刹车监控器——所有刹车事件的中央记录器。

    提供：
      - check_svd(singular_values, k) → SVDEnergyReport
      - check_nmf(content, card_id) → NMFBrakeReport
      - check_protection(path) → ProtectionCheckResult
      - verify_function(name) → bool
      - get_status() → 刹车系统健康状态
    """

    def __init__(self):
        self._lock = ProtectedRegionLock()
        self._events: List[BrakeEvent] = []
        self._max_events = 1000
        self._svd_log: List[SVDEnergyReport] = []
        self._nmf_log: List[NMFBrakeReport] = []
        self._protection_log: List[ProtectionCheckResult] = []

    def check_svd(
        self,
        singular_values: List[float],
        proposed_k: int,
        entity_id: str = "unknown",
    ) -> SVDEnergyReport:
        report = svd_energy_check(singular_values, proposed_k)
        log_svd_energy_report(report)
        self._svd_log.append(report)
        self._record_event("svd_energy", report.brake_triggered, report.action, report.detail, entity_id)
        return report

    def check_nmf(
        self,
        content: str,
        card_id: str = "unknown",
    ) -> NMFBrakeReport:
        report = nmf_tag_check(content, card_id)
        log_nmf_brake_report(report)
        self._nmf_log.append(report)
        self._record_event("nmf_dim", report.brake_triggered, report.action, report.detail, card_id)
        return report

    def check_protection(
        self,
        path: str,
        is_metabolism: bool = False,
        metabolism_tag: str = "",
    ) -> ProtectionCheckResult:
        result = self._lock.check(path, is_metabolism, metabolism_tag)
        log_protection_check(result)
        self._protection_log.append(result)
        self._record_event(
            "protection",
            result.brake_triggered,
            result.action,
            result.detail,
            path,
        )
        return result

    def verify_function(self, func_name: str) -> bool:
        return self._lock.verify_function(func_name)

    def _record_event(self, brake_type: str, triggered: bool, action: str, detail: str, entity_id: str):
        event = BrakeEvent(
            ts=time.time(),
            brake_type=brake_type,
            triggered=triggered,
            action=action,
            detail=detail,
            entity_id=entity_id,
        )
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

    def get_status(self) -> Dict[str, Any]:
        """返回刹车系统健康快照"""
        recent = self._events[-100:] if self._events else []
        triggered = [e for e in recent if e.triggered]
        return {
            "brake_system": "active",
            "total_events": len(self._events),
            "recent_events_100": len(recent),
            "brakes_triggered_recent_100": len(triggered),
            "svd_checks": len(self._svd_log),
            "svd_blocked": sum(1 for r in self._svd_log if r.brake_triggered),
            "nmf_checks": len(self._nmf_log),
            "nmf_blocked": sum(1 for r in self._nmf_log if r.brake_triggered),
            "protection_checks": len(self._protection_log),
            "protection_blocked_a": sum(1 for r in self._protection_log if r.action == "BLOCKED_A"),
            "protection_confirm_needed": sum(1 for r in self._protection_log if r.action == "NEEDS_CONFIRMATION"),
            "recent_triggered": [
                {"ts": e.ts, "type": e.brake_type, "action": e.action, "detail": e.detail[:80]}
                for e in triggered[-10:]
            ],
        }


# 全局单例
_brake_monitor: Optional[BrakeMonitor] = None

def get_brake_monitor() -> BrakeMonitor:
    global _brake_monitor
    if _brake_monitor is None:
        _brake_monitor = BrakeMonitor()
    return _brake_monitor


# ═══════════════════════════════════════════════════════════════
# 工具函数：供外部调用
# ═══════════════════════════════════════════════════════════════

def svd_energy_floor(sv: List[float], k: int) -> SVDEnergyReport:
    """快捷入口：SVD能量地板检查"""
    return get_brake_monitor().check_svd(sv, k)


def nmf_sparsity_check(content: str, card_id: str = "unknown") -> NMFBrakeReport:
    """快捷入口：NMF维度检查"""
    return get_brake_monitor().check_nmf(content, card_id)


def memory_card_tag_count(content: str) -> int:
    """快捷入口：统计核心标签数"""
    return count_core_tags(content)


def can_modify(path: str, is_metabolism: bool = False, metabolism_tag: str = "") -> Tuple[bool, str]:
    """
    快捷入口：路径修改权限检查。

    返回：(is_allowed, reason)
    """
    result = get_brake_monitor().check_protection(path, is_metabolism, metabolism_tag)
    return (result.is_allowed, result.action + ": " + result.detail)


def can_modify_function(func_name: str) -> Tuple[bool, str]:
    """
    快捷入口：函数修改权限检查。

    返回：(is_allowed, reason)
    """
    if get_brake_monitor().verify_function(func_name):
        return (False, f"FUNC_BLACKLISTED: 函数 {func_name} 在黑名单中，禁止自改")
    return (True, f"函数 {func_name} 不在黑名单，允许自改")


def propose_split(content: str, card_id: str = "unknown") -> List[Tuple[str, str]]:
    """
    快捷入口：当 NMF 维度超限时，提议拆分方案。
    """
    return propose_memory_split(content, card_id)


def brakes_status() -> Dict[str, Any]:
    """快捷入口：刹车系统健康状态"""
    return get_brake_monitor().get_status()
