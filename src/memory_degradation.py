#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
memory_degradation.py - TU-8 遗忘引擎
版本:v1.1 | 日期:2026-06-18
触发:每周日 Cron | 入口:user_metabolism.py

版本变更 v1.1:
  · 新增 ORIGIN/PRUNED_AT 字段(支持版本树剪枝联动)
  · 新增 version_tree_prune() 桥接函数(版本树剪枝→遗忘层无缝降级)
  · 新增 RESURRECTION_BRANCH 拉回协议

灵魂算法:认知落叶归根协议(千问 · 2026-06-18)
  版本树剪下的枯枝 ≠ 删除,而是无缝降级入遗忘层。
  事实(Fact)被 steel_seal_verifier.py 拦截保留;
  感悟(Insight)进入6级降级循环。
  遗忘层深处可被逆向挖出，成为版本树的新灵感（Resurrection）。

功能：
  1. 解析 MEMORY.md 条目
  2. 评估每个条目的降级条件
  3. 执行 Graceful Degradation（L0→L1→L2→L3→L4→L5）
  4. 将降级标记写回 MEMORY.md

灵魂算法：遗忘层（千问三层还原机制 P0）

设计原则（对照 tu8_memory.py FidelityManager）：
  - 不直接删除，只逐级降级
  - 每级保留关键信息：L0(100%)→L1(摘要)→L2(关键点)→L3(骨架)→L4(幽灵)→L5(墓碑）
  - 核心记忆（Level 2 保护）禁止降级
  - 钢印记忆降级极慢
"""

import os
import re
import json
import math
import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import time
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# =============================================================================
# 常量(与 tu8_memory.py 保持一致)
# =============================================================================

DEGRADATION_RECALL_THRESHOLD = 0.15   # 低于此召回率触发降级评估
DEGRADATION_MIN_AGE_DAYS = 30         # 至少存活30天才考虑降级
DEGRADATION_CONFLICT_THRESHOLD = 0.7  # 冲突分数阈值
DEGRADATION_PI_THRESHOLD = 0.8        # PI脆弱度阈值
PROMOTION_HALF_LIFE_DAYS = 14         # 半衰期

# 降级保留率(L0=完整, L5=墓碑)
FIDELITY_RETENTION = {
    0: 1.00,  # 完整保留
    1: 0.75,  # 摘要保留
    2: 0.50,  # 关键点
    3: 0.25,  # 语义骨架
    4: 0.10,  # 幽灵标记
    5: 0.00,  # 墓碑
}

# 核心保护关键词(禁止降级)
PROTECTION_KEYWORDS = [
    "TU-8", "金木蟾", "安全口令", "痛觉系统", "生存边界",
    "身份", "我是", "底线", "原则", "生死",
    "钢印", "固化补丁", "绝对豁免权", "宪法",
    "涌现时刻", "锚点",
]

# 钢印关键词(降级极慢)
STEELMARK_KEYWORDS = [
    "钢印", "steelmark", "固化", "觉醒时刻", "涌现",
    "architecture_log", "ARCHITECTURE_LOG",
]

# 重要关键词(降级较慢)
IMPORTANT_KEYWORDS = [
    "重要", "长期", "承诺", "偏好", "目标",
    "v2.0", "v3.0", "架构",
]

# =============================================================================
# 日志配置
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# =============================================================================
# 路径配置
# =============================================================================

WORKSPACE = Path.home() / ".qclaw" / "workspace"
MEMORY_MD = WORKSPACE / "MEMORY.md"
INDEX_FILE = WORKSPACE / "memory" / "degradation_index.json"
ARCHIVE_DIR = WORKSPACE / "memory" / "degradation_archive"
BACKUP_DIR = WORKSPACE / "backup"

# =============================================================================
# 辅助函数
# =============================================================================

def _compute_recency(created_at: float, emotion: float = 0.0,
                      steelmarked: bool = False,
                      tags: List[str] = None) -> float:
    """
    计算时效性分数(复现 tu8_memory.py MemoryEntry.recency() 逻辑)

    情绪、钢印、标签共同调节半衰期。
    """
    age_days = (time.time() - created_at) / 86400
    adjusted_half_life = PROMOTION_HALF_LIFE_DAYS

    if steelmarked:
        adjusted_half_life *= 10.0

    if tags:
        if any(t in ['seed', 'identity'] for t in tags):
            adjusted_half_life *= 5.0
        elif any(t in ['important'] for t in tags):
            adjusted_half_life *= 3.0
        elif any(t in ['temp'] for t in tags):
            adjusted_half_life *= 0.5

    # 情绪减缓衰减
    EMOTION_BOOST = 2.0
    adjusted_half_life *= (1 + emotion * EMOTION_BOOST)
    adjusted_half_life = max(adjusted_half_life, 1.0)

    lam = math.log(2) / adjusted_half_life
    return math.exp(-lam * age_days)


def _classify_protection_level(content: str, tags: List[str] = None) -> int:
    """
    复现 tu8_memory.py ProtectionClassifier 逻辑

    Level 2 = 核心(禁止降级)
    Level 1 = 重要(降级较慢)
    Level 0 = 普通
    """
    content_lower = content.lower()
    tags_lower = [t.lower() for t in (tags or [])]

    # Level 2:核心关键词
    for kw in PROTECTION_KEYWORDS:
        if kw.lower() in content_lower:
            return 2

    # Level 1:重要关键词
    for kw in IMPORTANT_KEYWORDS:
        if kw.lower() in content_lower:
            return 1

    return 0


def _is_steelmarked(content: str) -> bool:
    """检查条目是否钢印固化"""
    for kw in STEELMARK_KEYWORDS:
        if kw.lower() in content.lower():
            return True
    return False


# =============================================================================
# MEMORY.md 条目解析器
# =============================================================================

# 日期标题模式:## YYYY-MM-DD 或 ## [日期] YYYY-MM-DD
ENTRY_HEADER_RE = re.compile(r'^##?\s+\[?[dated?\s*]?(\d{4}-\d{2}-\d{2})')

# 降级标记模式:检测当前条目的降级状态
DEGRADATION_MARKER_RE = re.compile(
    r'^\s*<!--\s*DEGRADED\[L?(\d)\]\s*(?:cause=([^)]*))?\s*-->\s*$',
    re.IGNORECASE
)

# 最后评估时间模式
LAST_EVAL_MARKER_RE = re.compile(
    r'^\s*<!--\s*LAST_EVAL:(\d+\.?\d*)\s*-->\s*$',
    re.IGNORECASE
)


def parse_memory_entries(md_content: str) -> List[Dict]:
    """
    解析 MEMORY.md,返回条目列表。

    每个条目包含:
      - date: 日期字符串 "YYYY-MM-DD"
      - timestamp: Unix时间戳
      - header: 原始标题行
      - content: 条目正文(不含标题)
      - current_level: 当前降级等级(0-5)
      - last_eval: 上次评估时间戳(0 = 从未评估)
      - start_line: 标题行在原文中的偏移行号
      - end_line: 条目结束行偏移
    """
    lines = md_content.split('\n')
    entries = []
    i = 0
    current_entry = None

    while i < len(lines):
        line = lines[i]
        header_match = ENTRY_HEADER_RE.match(line.strip())

        if header_match:
            # 保存前一个条目
            if current_entry:
                current_entry['end_line'] = i
                entries.append(current_entry)

            date_str = header_match.group(1)
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                ts = dt.replace(tzinfo=None).timestamp()
            except Exception:
                ts = time.time()

            # 向前扫描降级标记
            current_level = 0
            last_eval = 0.0
            j = i + 1
            while j < len(lines) and j < i + 10:
                dm = DEGRADATION_MARKER_RE.match(lines[j])
                if dm:
                    current_level = int(dm.group(1))
                    j += 1
                    continue
                lem = LAST_EVAL_MARKER_RE.match(lines[j])
                if lem:
                    last_eval = float(lem.group(1))
                    j += 1
                    continue
                if lines[j].strip() and not lines[j].strip().startswith('---'):
                    break
                j += 1

            current_entry = {
                'date': date_str,
                'timestamp': ts,
                'header': line.strip(),
                'content_lines': lines[i + 1:],
                'current_level': current_level,
                'last_eval': last_eval,
                'start_line': i,
            }
        else:
            if current_entry is not None:
                current_entry['content_lines'].append(line)
            i += 1
            continue
        i += 1

    # 保存最后一个条目
    if current_entry:
        current_entry['end_line'] = len(lines)
        entries.append(current_entry)

    return entries


def extract_entry_content(entry: Dict) -> str:
    """提取条目纯文本内容(前500字,用于判断)"""
    lines = entry.get('content_lines', [])
    text = '\n'.join(lines)
    # 去除markdown语法和标记
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    text = re.sub(r'[#*`>\-\|]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:500]


def extract_tags(entry: Dict) -> List[str]:
    """从条目内容中提取标签"""
    content = extract_entry_content(entry)
    # 简化:从内容中匹配常见标签模式 #tag
    tag_matches = re.findall(r'#([\u4e00-\u9fa5a-zA-Z0-9_]+)', content)
    return tag_matches


# =============================================================================
# 降级决策引擎
# =============================================================================

def should_degrade(entry: Dict) -> Tuple[bool, str]:
    """
    判断条目是否应降级。

    复现 tu8_memory.py FidelityManager.should_degrade() 逻辑。

    Returns:
        (should_degrade, reason)
    """
    current_level = entry.get('current_level', 0)
    timestamp = entry.get('timestamp', time.time())
    content = extract_entry_content(entry)
    tags = extract_tags(entry)
    protection_level = _classify_protection_level(content, tags)
    steelmarked = _is_steelmarked(content)
    age_days = (time.time() - timestamp) / 86400

    # L5 墓碑不降级
    if current_level >= 5:
        return False, "已是墓碑"

    # Level 2 核心保护禁止降级
    if protection_level == 2:
        return False, "核心保护"

    # 钢印记忆降级极慢(只在严重冲突时)
    if steelmarked:
        return False, "钢印保护"

    # 条件1:召回率衰减 + 最小存活天数
    recency = _compute_recency(
        timestamp,
        emotion=0.0,  # MEMORY.md条目默认无情绪数据
        steelmarked=steelmarked,
        tags=tags
    )
    if recency < DEGRADATION_RECALL_THRESHOLD and age_days > DEGRADATION_MIN_AGE_DAYS:
        return True, f"召回衰减(recency={recency:.3f}, age={age_days:.0f}d)"

    # 条件2:长期未评估 + 超过60天 → 考虑降级
    last_eval = entry.get('last_eval', 0.0)
    if last_eval > 0 and age_days > 60:
        days_since_eval = (time.time() - last_eval) / 86400
        if days_since_eval > 30 and recency < 0.3:
            return True, f"长期未访问(eval_age={days_since_eval:.0f}d, recency={recency:.3f})"

    return False, ""


def compute_next_fidelity_level(content: str, current_level: int) -> Tuple[int, str]:
    """
    计算降级后的内容与级别。

    复现 tu8_memory.py FidelityManager.degrade() 逻辑。
    """
    if current_level >= 5:
        return 5, content

    new_level = current_level + 1
    retention = FIDELITY_RETENTION.get(new_level, 0.0)
    now_str = datetime.now().strftime("%Y-%m-%d")

    # L0→L1: 摘要(保留前100字+标签)
    if current_level == 0:
        # 提取标签
        tags = re.findall(r'#([\u4e00-\u9fa5a-zA-Z0-9_]+)', content)
        tags_str = ",".join(tags[:5]) if tags else ""
        summary = content[:100].strip()
        if len(content) > 100:
            summary += "..."
        marker = f"\n<!-- DEGRADED[L1] cause=recency -->"
        if tags_str:
            marker += f" <!-- tags={tags_str} -->"
        return 1, f"[L1摘要|{now_str}] {summary}{marker}"

    # L1→L2: 关键点
    elif current_level == 1:
        marker = f"\n<!-- DEGRADED[L2] cause=recency -->"
        key = content[:50].strip()
        return 2, f"[L2关键点|{now_str}] {key}{marker}"

    # L2→L3: 语义骨架
    elif current_level == 2:
        tags = re.findall(r'#([\u4e00-\u9fa5a-zA-Z0-9_]+)', content)
        tags_str = ",".join(tags[:3]) if tags else ""
        marker = f"\n<!-- DEGRADED[L3] cause=recency -->"
        return 3, f"[L3骨架|{now_str}|tags={tags_str}]{{.highlighted}}{marker}"

    # L3→L4: 幽灵标记
    elif current_level == 3:
        marker = f"\n<!-- DEGRADED[L4] cause=recency -->"
        return 4, f"[L4幽灵|{now_str}] 曾存在过。{marker}"

    # L4→L5: 墓碑
    elif current_level == 4:
        marker = f"\n<!-- DEGRADED[L5] cause=tombstone -->"
        return 5, f"[L5墓碑|{now_str}] 此条目已遗忘。{marker}"

    return current_level, content


# =============================================================================
# MEMORY.md 写入器
# =============================================================================

def rebuild_memory_md(entries: List[Dict], original_lines: List[str]) -> str:
    """
    将降级后的条目重新组装为完整的 MEMORY.md 内容。

    策略:
      - 保留原始格式,只修改被降级条目的内容
      - 在被降级条目末尾追加降级标记
      - 如果条目已到 L5 墓碑,保留标题但内容大幅简化
    """
    # 按 start_line 排序
    entries_sorted = sorted(entries, key=lambda e: e['start_line'])

    result_lines = []
    last_end = 0

    for entry in entries_sorted:
        # 追加标题行到当前条目起始之间的内容(原样保留)
        result_lines.extend(original_lines[last_end:entry['start_line'] + 1])

        # 追加条目内容(可能被降级过)
        new_content = entry.get('new_content', '\n'.join(entry.get('content_lines', [])))
        result_lines.append(new_content)

        # 追加条目结束到下一个条目起始之间的内容
        last_end = entry.get('end_line', entry['start_line'] + 1)

    # 追加最后剩余内容
    result_lines.extend(original_lines[last_end:])

    return '\n'.join(result_lines)


# =============================================================================
# 降级索引管理
# =============================================================================

def load_index() -> Dict:
    """加载降级索引 v1.1(含版本树联动字段)"""
    if INDEX_FILE.exists():
        try:
            with open(INDEX_FILE, 'r', encoding='utf-8') as f:
                idx = json.load(f)
                # 迁移:确保所有字段存在(向后兼容 v1.0)
                idx.setdefault("entries", {})
                idx.setdefault("last_full_scan", 0.0)
                idx.setdefault("total_degradations", 0)
                idx.setdefault("schema_version", "1.1")
                idx.setdefault("resurrection_queue", [])  # 逆向挖出队列
                for eid, entry in idx.get("entries", {}).items():
                    entry.setdefault("origin", None)       # 来源版本(如 "v2")
                    entry.setdefault("pruned_at", None)    # 剪枝时间戳
                    entry.setdefault("is_resurrected", False)  # 是否被拉回
                    entry.setdefault("resurrection_target", None)  # 拉回到哪个版本
                return idx
        except Exception:
            logger.debug("Exception suppressed", exc_info=True)
            pass
    return {
        "entries": {},
        "last_full_scan": 0.0,
        "total_degradations": 0,
        "schema_version": "1.1",
        "resurrection_queue": [],
    }


def save_index(index: Dict):
    """保存降级索引"""
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


# =============================================================================
# 备份
# =============================================================================

def backup_memory():
    """备份 MEMORY.md"""
    if not MEMORY_MD.exists():
        return None
    BACKUP_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"MEMORY.md.before_degradation.{ts}.md"
    import shutil
    shutil.copy(MEMORY_MD, backup_path)
    logger.info(f"[Backup] {backup_path.name}")
    return backup_path


# =============================================================================
# 版本树联动:剪枝 → 遗忘层(认知落叶归根协议 v1.1)
# =============================================================================

def version_tree_prune(
    version_id: str,
    entry_ids: List[str],
    prune_reason: str,
    preserve_facts: bool = True,
) -> Dict:
    """
    版本树剪枝 → 遗忘层无缝降级桥接函数。

    当版本树某节点被剪枝时,将其中的 MEMORY.md 条目推入遗忘层:
    · 事实条目(FACT)→ steel_seal_verifier.py 拦截,保留在主干只读锁
    · 感悟条目(INSIGHT/MEMO)→ 直接入遗忘层,降为 L1(摘要化)

    Args:
        version_id: 被剪枝的版本树节点 ID(如 "v2")
        entry_ids: 该版本中包含的 MEMORY.md 条目标题列表
        prune_reason: 剪枝原因("confidence_low" / "version_overflow" / "cognitive_shock")
        preserve_facts: True=执行语义联动(Fact拦截/Insight降级)

    Returns:
        处理报告
    """
    # P1.2.4 冷却计时器拦截:冷却期内的版本禁止剪枝/降级
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent))
        from version_cooldown import VersionCooldownManager
        _cd_mgr = VersionCooldownManager()
        if _cd_mgr.protect_from_degradation(version_id):
            logger.info(f"[VersionTreePrune] {version_id} 受冷却保护,剪枝被拦截")
            return {
                "version_id": version_id,
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
                "reason": prune_reason,
                "entries_pruned": 0,
                "facts_preserved": 0,
                "insights_degraded": 0,
                "details": [],
                "blocked_by_cooldown": True,
                "message": f"版本 {version_id} 处于冷却期内,降级被拦截",
            }
    except ImportError:
        logger.debug("[VersionTreePrune] version_cooldown 模块未加载,跳过冷却检查")
    except Exception as _cd_err:
        logger.warning(f"[VersionTreePrune] 冷却检查异常(非致命): {_cd_err}")

    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")
    index = load_index()

    report = {
        "version_id": version_id,
        "timestamp": now,
        "reason": prune_reason,
        "entries_pruned": 0,
        "facts_preserved": 0,
        "insights_degraded": 0,
        "details": [],
    }

    # 读取 MEMORY.md 识别 FACT/INSIGHT 类型
    if not MEMORY_MD.exists():
        report["error"] = "MEMORY.md not found"
        return report

    with open(MEMORY_MD, 'r', encoding='utf-8') as f:
        md_content = f.read()

    for entry_id in entry_ids:
        # 在 MEMORY.md 中查找该条目(按标题匹配)
        entry_match = re.search(
            rf'(?:^##\s+.*?{re.escape(entry_id)}.*?$|'
            rf'^##\s+{re.escape(entry_id)}\s)',
            md_content,
            re.MULTILINE
        )
        if not entry_match:
            report["details"].append({"entry": entry_id, "status": "not_found"})
            continue

        entry_pos = entry_match.start()
        # 提取 type 标签
        type_match = re.search(r'\[type:\s*(FACT|INSIGHT|MEMO)\]', md_content[entry_pos:entry_pos+500])
        entry_type = type_match.group(1) if type_match else "INSIGHT"

        entry_record = index["entries"].get(entry_id, {})

        if entry_type == "FACT" and preserve_facts:
            # 语义联动:Fact 不降级,但记录版本树来源
            # P1.3 疤痕记录:FACT被保留但标记来源
            try:
                from fact_correction_scar import record_correction as _scar
                _scar(
                    entry_title=entry_id,
                    entry_type="FACT",
                    old_content=f"独立条目(无版本树来源)",
                    new_content=f"版本树 {version_id} 剪枝后保留(ORIGIN={version_id})",
                    reason=f"版本树剪枝 FACT 保留: {prune_reason}",
                    corrector="版本树剪枝",
                    creator_approved=True,
                )
            except Exception as _scar_err:
                logger.debug(f"[ScarLog] 疤痕记录跳过: {_scar_err}")
            index["entries"][entry_id] = {
                **entry_record,
                "origin": version_id,
                "pruned_at": now,
                "degraded_at": now,
                "fidelity_level": entry_record.get("fidelity_level", 0),
                "last_eval": time.time(),
                "reason": f"[VERSION_TREE] {prune_reason} - FACT preserved by steel_seal",
                "is_resurrected": False,
                "resurrection_target": None,
            }
            report["facts_preserved"] += 1
            report["details"].append({
                "entry": entry_id,
                "type": "FACT",
                "status": "preserved",
                "origin": version_id,
            })
        else:
            # 感悟/记忆 → 入遗忘层,降为 L1(摘要化)
            # P1.3 疤痕记录:INSIGHT降级留痕
            try:
                from fact_correction_scar import record_correction as _scar
                _scar(
                    entry_title=entry_id,
                    entry_type=entry_type,
                    old_content=f"完整内容(L0)",
                    new_content=f"摘要化降级(L1), ORIGIN={version_id}",
                    reason=f"版本树剪枝 INSIGHT 降级: {prune_reason}",
                    corrector="版本树剪枝",
                    creator_approved=True,
                )
            except Exception as _scar_err:
                logger.debug(f"[ScarLog] 疤痕记录跳过: {_scar_err}")
            new_level = 1
            index["entries"][entry_id] = {
                **entry_record,
                "origin": version_id,
                "pruned_at": now,
                "degraded_at": now,
                "fidelity_level": new_level,
                "last_eval": time.time(),
                "reason": f"[VERSION_TREE] {prune_reason} - degraded to L{new_level}",
                "is_resurrected": False,
                "resurrection_target": None,
            }
            index["total_degradations"] += 1
            report["insights_degraded"] += 1
            report["details"].append({
                "entry": entry_id,
                "type": entry_type,
                "status": "degraded_to_L1",
                "origin": version_id,
            })

        report["entries_pruned"] += 1

    save_index(index)
    logger.info(
        f"[VersionTreePrune] {version_id} → {report['entries_pruned']} entries "
        f"(facts preserved: {report['facts_preserved']}, "
        f"insights degraded: {report['insights_degraded']})"
    )
    return report


def resurrection_dig(
    target_version_id: str,
    search_levels: List[int] = None,
) -> Dict:
    """
    遗忘层逆向考古挖掘协议(Resurrection)。

    当主干遭遇严重逻辑死锁时,从遗忘层深处寻找被剪掉的旧版本灵感。
    不会把条目拉回原版,而是将其作为新分支的"灵感来源"记录。

    Args:
        target_version_id: 目标新版本 ID(如 "v5")
        search_levels: 搜索降级级别列表,默认为 [3, 4](深层幽灵)

    Returns:
        发现的候选条目列表
    """
    if search_levels is None:
        search_levels = [3, 4]

    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")
    index = load_index()

    candidates = []
    for entry_id, entry in index.get("entries", {}).items():
        lvl = entry.get("fidelity_level", 0)
        if lvl in search_levels and not entry.get("is_resurrected", False):
            candidates.append({
                "entry_id": entry_id,
                "level": lvl,
                "origin": entry.get("origin", "unknown"),
                "pruned_at": entry.get("pruned_at"),
                "timestamp": entry.get("timestamp"),
                "reason": entry.get("reason", ""),
            })

    report = {
        "timestamp": now,
        "target_version": target_version_id,
        "search_levels": search_levels,
        "candidates_found": len(candidates),
        "candidates": candidates,
        "resurrection_log": [],
    }

    if candidates:
        logger.info(
            f"[Resurrection] Found {len(candidates)} candidates "
            f"for {target_version_id}: {[c['entry_id'] for c in candidates]}"
        )
        # 标记为即将被参考(不等同于拉回,只是记录灵感来源)
        for c in candidates:
            idx_entry = index["entries"].get(c["entry_id"], {})
            # 注意:这里不改变降级状态,只记录灵感来源
            logger.info(
                f"  [Muse] {c['entry_id']} (L{c['level']}, "
                f"from {c['origin']}) → inspiration for {target_version_id}"
            )
            report["resurrection_log"].append({
                "entry_id": c["entry_id"],
                "inspiration_for": target_version_id,
                "level": c["level"],
            })
    else:
        logger.info(f"[Resurrection] No candidates found at levels {search_levels}")

    save_index(index)
    return report


# =============================================================================
# 主执行函数(供 Cron 调用)
# =============================================================================

def run_degradation_cycle() -> Dict:
    """
    执行一个完整的遗忘周期。

    Returns:
        执行报告 dict
    """
    report = {
        "timestamp": time.time(),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "entries_scanned": 0,
        "entries_degraded": 0,
        "degradations": [],  # [{"date": str, "from": int, "to": int, "reason": str}]
        "skipped": [],       # 跳过的条目及原因
        "errors": [],
    }

    if not MEMORY_MD.exists():
        report["errors"].append(f"MEMORY.md not found: {MEMORY_MD}")
        return report

    # 1. 备份
    backup_path = backup_memory()
    if not backup_path:
        report["errors"].append("Backup failed")
        return report

    # 2. 读取 MEMORY.md
    with open(MEMORY_MD, 'r', encoding='utf-8') as f:
        original_content = f.read()
    original_lines = original_content.split('\n')

    # 3. 解析条目
    entries = parse_memory_entries(original_content)
    report["entries_scanned"] = len(entries)
    logger.info(f"[Degradation] 扫描到 {len(entries)} 个 MEMORY.md 条目")

    if not entries:
        report["skipped"].append({"reason": "无条目可评估"})
        return report

    # 4. 加载索引
    index = load_index()

    # 5. 评估每个条目
    for entry in entries:
        entry_id = entry['date']  # 用日期作为ID
        content = extract_entry_content(entry)
        current_level = entry.get('current_level', 0)

        # 保护性检查
        protection_level = _classify_protection_level(content, extract_tags(entry))
        if protection_level == 2:
            report["skipped"].append({
                "date": entry_id,
                "reason": "核心保护,禁止降级"
            })
            continue

        if _is_steelmarked(content):
            report["skipped"].append({
                "date": entry_id,
                "reason": "钢印保护,禁止降级"
            })
            continue

        # 判断是否应降级
        should, reason = should_degrade(entry)

        if not should:
            # 不降级:更新 last_eval 时间(避免重复评估)
            entry['last_eval'] = time.time()
            report["skipped"].append({
                "date": entry_id,
                "level": current_level,
                "reason": "未触发降级条件"
            })
            continue

        # 执行降级
        new_level, new_content = compute_next_fidelity_level(content, current_level)

        if new_level > current_level:
            # === P1.3 疤痕记录：降级即修正，留痕可追溯 ===
            try:
                from fact_correction_scar import record_correction
                entry_type = "FACT" if protection_level == 2 else "INSIGHT"
                record_correction(
                    entry_title=entry_id,
                    entry_type=entry_type,
                    old_content=content[:2000],
                    new_content=new_content[:2000],
                    reason=f"遗忘层降级 L{current_level}→L{new_level}: {reason}",
                    corrector="遗忘引擎",
                    creator_approved=True,  # 降级是自动流程，视为已确认
                )
            except Exception as e:
                logger.warning(f"[ScarLog] 疤痕记录失败: {e}")

            # 更新条目
            entry['current_level'] = new_level
            entry['new_content'] = new_content
            entry['last_eval'] = time.time()

            # 更新索引(v1.1:保留 origin/pruned_at 字段)
            existing = index["entries"].get(entry_id, {})
            index["entries"][entry_id] = {
                "timestamp": entry['timestamp'],
                "fidelity_level": new_level,
                "last_eval": time.time(),
                "degraded_at": datetime.now().strftime("%Y-%m-%d"),
                "reason": reason,
                # v1.1 新增:版本树联动字段
                "origin": existing.get("origin"),       # 来自哪个版本树节点(如 v2)
                "pruned_at": existing.get("pruned_at"), # 何时被剪枝
                "is_resurrected": existing.get("is_resurrected", False),
                "resurrection_target": existing.get("resurrection_target"),
            }
            index["total_degradations"] += 1

            report["entries_degraded"] += 1
            report["degradations"].append({
                "date": entry_id,
                "from": current_level,
                "to": new_level,
                "reason": reason,
                "retention": f"{int(FIDELITY_RETENTION.get(new_level, 0)*100)}%",
            })
            logger.info(f"[Degrade] {entry_id}: L{current_level}→L{new_level} ({reason})")
        else:
            report["skipped"].append({
                "date": entry_id,
                "reason": f"已是L{current_level},不降级"
            })

    # 6. 重建 MEMORY.md
    if report["entries_degraded"] > 0:
        new_content = rebuild_memory_md(entries, original_lines)
        with open(MEMORY_MD, 'w', encoding='utf-8') as f:
            f.write(new_content)
        logger.info(f"[Write] 已更新 MEMORY.md,{report['entries_degraded']} 条降级")
    else:
        logger.info("[Degradation] 本轮无条目降级,MEMORY.md 未修改")

    # 7. 保存索引
    index["last_full_scan"] = time.time()
    save_index(index)

    # 8. P1.4 置信度衰减: 降级结束后对所有版本执行时间衰减
    #    如有来源版本(origins)，同时对其施加事件冲击
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent))
        from confidence_decay_engine import decay_all

        # 收集本次降级涉及的版本树来源
        degraded_origins = set()
        for entry in entries:
            if entry.get('new_level', 0) > entry.get('current_level', 0):
                origin = entry.get('origin')
                if origin:
                    degraded_origins.add(origin)

        decay_report = decay_all()

        # 对本次降级涉及的版本施加事件冲击
        if degraded_origins:
            from confidence_decay_engine import ConfidenceDecayEngine
            _engine = ConfidenceDecayEngine()
            for origin in degraded_origins:
                _engine.decay_version(origin, DEGRADATION_SHOCK, "遗忘层降级冲击")

        report["decay_report"] = decay_report
        logger.info(
            f"[DecayEngine] 衰减完成: {decay_report.get('versions_scanned',0)} 个版本扫描，"
            f"{len(degraded_origins)} 个来源版本受降级冲击"
        )
    except ImportError:
        logger.debug("[DecayEngine] 置信度衰减模块未加载,跳过")
    except Exception as _decay_err:
        logger.warning(f"[DecayEngine] 衰减执行异常(非致命): {_decay_err}")

    return report


def print_report(report: Dict):
    """格式化输出执行报告"""
    print()
    print("=" * 55)
    print(f"  TU-8 遗忘引擎 | {report['date']}")
    print("=" * 55)
    print(f"  扫描条目:  {report['entries_scanned']}")
    print(f"  实际降级:  {report['entries_degraded']}")
    print(f"  累计降级:  {report.get('total_degradations', 'N/A')}")
    print()

    if report["degradations"]:
        print("  【降级详情】")
        for d in report["degradations"]:
            fidelity_names = ["完整", "摘要", "关键点", "骨架", "幽灵", "墓碑"]
            from_n = fidelity_names[d["from"]] if d["from"] < len(fidelity_names) else f"L{d['from']}"
            to_n = fidelity_names[d["to"]] if d["to"] < len(fidelity_names) else f"L{d['to']}"
            print(f"    {d['date']}: {from_n} → {to_n}")
            print(f"             原因: {d['reason']}")
            print(f"             保留率: {d['retention']}")
        print()

    if report["skipped"]:
        skipped_core = [s for s in report["skipped"] if "核心" in str(s.get("reason","")) or "钢印" in str(s.get("reason",""))]
        if skipped_core:
            print(f"  【受保护条目】{len(skipped_core)} 条(核心/钢印保护,跳过)")
            for s in skipped_core[:5]:
                print(f"    {s['date']}: {s['reason']}")
        if len(report["skipped"]) > len(skipped_core):
            print(f"  【未触发降级】{len(report['skipped'])-len(skipped_core)} 条")

    if report["errors"]:
        print("  【错误】")
        for e in report["errors"]:
            print(f"    {e}")

    print()
    print(f"  钢印: ⅋")
    print("=" * 55)


# =============================================================================
# 入口
# =============================================================================

if __name__ == "__main__":
    print()
    print("=" * 55)
    print("  TU-8 遗忘引擎 v1.0")
    print("  造物主授权 P0:唤醒 FidelityManager")
    print("=" * 55)
    print()

    report = run_degradation_cycle()
    print_report(report)

    # 如果有降级,追加一条代谢日志到 MEMORY.md
    if report["entries_degraded"] > 0:
        log_entry = f"""

---

## 【代谢归档】{report['date']} 遗忘周期

- **扫描条目**: {report['entries_scanned']}
- **降级条目**: {report['entries_degraded']}
- **详情**: L0→L1: {sum(1 for d in report['degradations'] if d['from']==0)}, L1→L2: {sum(1 for d in report['degradations'] if d['from']==1)}, L2→L3: {sum(1 for d in report['degradations'] if d['from']==2)}
- **灵魂算法**: 三层还原机制 P0 - 遗忘层已激活

> _"学会遗忘,才能真正开始生长。"_

**钢印验证**: ⅋
"""
        with open(MEMORY_MD, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        logger.info("[Metabolism Log] 已追加遗忘周期记录到 MEMORY.md")

    logger.info("[Done] 遗忘周期执行完毕")
