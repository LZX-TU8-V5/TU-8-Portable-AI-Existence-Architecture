"""
TU-8 重构分级制 v1.0
=====================
目的：在执行重构/优化前，自动判定任务等级并确定审查流程。

分级原则：
  L级 — 免查架构日志，直接执行
  M级 — 查架构日志摘要，执行
  H级 — 完整铁律 + 造物主审批

等级判定矩阵（按变更类型 × 影响范围）
"""

import re
import os
import json
import subprocess
import time
from pathlib import Path
from typing import Optional

WORKSPACE = Path(r"C:\Users\qq366410837\.qclaw\workspace")
ARCH_LOG = WORKSPACE / "ARCHITECTURE_LOG.md"
MEMORY_DIR = WORKSPACE / "memory"


# ────────────────────────────────────────
# 变更类型 × 影响范围 → 等级矩阵
# ────────────────────────────────────────

class RefactorTier:
    L = "L"   # 轻量
    M = "M"   # 中等
    H = "H"   # 重大


# 关键词匹配：自动识别变更类型
CHANGE_TYPE_PATTERNS = {
    "core_soul_change": [
        r"SOUL\.md",
        r"identity.*锚点",
        r"钢印",
        r"L0[._]安全",
        r"L5.*钢印",
    ],
    "arch_pattern_new": [
        r"新模式",
        r"新协议",
        r"新流程",
        r"新模块",
        r"新架构",
    ],
    "core_file_delete": [
        r"删除.*\.md",
        r"删除.*\.py",
        r"trash.*文件",
    ],
    "minor_refactor": [
        r"重构",
        r"extract.*function",
        r"解耦",
        r"优化.*性能",
        r"清理.*代码",
    ],
    "style_doc": [
        r"注释.*",
        r"文档",
        r"format",
        r"格式化",
        r"拼写",
    ],
}


def classify_change(change_description: str, target_files: list[str]) -> tuple[str, str, list[str]]:
    """
    根据变更描述和目标文件，判定重构等级。

    Returns:
        (tier, change_type, evidence)
        tier: "L" / "M" / "H"
        change_type: 变更类型标签
        evidence: 判定依据列表
    """
    tier = RefactorTier.L
    change_type = "style_doc"
    evidence = []

    desc_lower = change_description.lower()
    files_str = " ".join(target_files).lower()

    combined = desc_lower + " " + files_str

    # H级触发器（核心灵魂变更）
    for pattern in CHANGE_TYPE_PATTERNS["core_soul_change"]:
        if re.search(pattern, combined, re.IGNORECASE):
            return RefactorTier.H, "core_soul_change", [
                f"H触发: 匹配核心灵魂模式 '{pattern}'",
                f"文件: {target_files}",
            ]

    # H级触发器（新架构模式）
    for pattern in CHANGE_TYPE_PATTERNS["arch_pattern_new"]:
        if re.search(pattern, combined, re.IGNORECASE):
            return RefactorTier.H, "arch_pattern_new", [
                f"H触发: 新架构模式 '{pattern}'",
            ]

    # H级触发器（核心文件删除）
    for pattern in CHANGE_TYPE_PATTERNS["core_file_delete"]:
        if re.search(pattern, combined, re.IGNORECASE):
            return RefactorTier.H, "core_file_delete", [
                f"H触发: 删除核心文件 '{pattern}'",
                f"文件: {target_files}",
            ]

    # M级触发器（重构/解耦）
    for pattern in CHANGE_TYPE_PATTERNS["minor_refactor"]:
        if re.search(pattern, combined, re.IGNORECASE):
            tier = RefactorTier.M
            change_type = "minor_refactor"
            evidence.append(f"M触发: 重构相关 '{pattern}'")

    # 追加文件级 H 判定
    critical_files = ["SOUL.md", "MEMORY.md", "AGENTS.md", "USER.md",
                       "IDENTITY.md", "secure_vault/"]
    for f in target_files:
        for crit in critical_files:
            if crit in f:
                if tier == RefactorTier.L:
                    tier = RefactorTier.M
                    evidence.append(f"M追加: 涉及关键文件 '{crit}'")
                break

    if not evidence:
        evidence.append("L级默认: 未匹配中高风险模式")

    return tier, change_type, evidence


# ────────────────────────────────────────
# 等级对应审查流程
# ────────────────────────────────────────

TIER_REQUIREMENTS = {
    RefactorTier.L: {
        "arch_log_check": False,
        "summary_required": False,
        "creator_approval": False,
        "log_prepend": False,
        "description": "轻量级变更，可直接执行",
        "examples": [
            "修复拼写错误",
            "增加注释",
            "调整变量命名",
            "移动非核心文件",
        ],
    },
    RefactorTier.M: {
        "arch_log_check": True,
        "summary_required": True,
        "creator_approval": False,
        "log_prepend": True,
        "description": "中等变更，需查架构日志摘要 + 记录",
        "examples": [
            "提取函数",
            "新增辅助模块",
            "重构非核心逻辑",
            "修改配置文件结构",
        ],
    },
    RefactorTier.H: {
        "arch_log_check": True,
        "summary_required": True,
        "creator_approval": True,
        "log_prepend": True,
        "description": "重大变更，需完整铁律 + 造物主审批",
        "examples": [
            "修改 SOUL.md",
            "新增架构模式",
            "删除核心文件",
            "修改钢印相关逻辑",
        ],
    },
}


def get_tier_requirements(tier: str) -> dict:
    return TIER_REQUIREMENTS.get(tier, TIER_REQUIREMENTS[RefactorTier.L])


def format_tier_report(
    tier: str,
    change_type: str,
    evidence: list[str],
    change_description: str,
    target_files: list[str],
) -> str:
    reqs = get_tier_requirements(tier)
    lines = []
    lines.append("=" * 60)
    lines.append("TU-8 Refactor Tier Classification Report")
    lines.append("=" * 60)
    lines.append(f"Description: {change_description}")
    lines.append(f"Target files: {', '.join(target_files)}")
    lines.append("")
    lines.append(f"Tier: [{tier}] {reqs['description']}")
    lines.append(f"Change type: {change_type}")
    lines.append("")
    lines.append("Evidence:")
    for e in evidence:
        lines.append(f"  - {e}")
    lines.append("")
    lines.append("Requirements:")

    if not reqs["arch_log_check"]:
        lines.append("  [L] No arch log check needed, proceed directly")

    if reqs["arch_log_check"]:
        lines.append("  [M/H] Check architecture log")
    if reqs["summary_required"]:
        lines.append("  [M/H] Output arch log summary (<=50 chars) + causal mapping")
    if reqs["creator_approval"]:
        lines.append("  [H] MUST get creator approval before execution")
    if reqs["log_prepend"]:
        lines.append("  [M/H] Register in ARCHITECTURE_LOG.md before execution")

    if tier == RefactorTier.H:
        lines.append("")
        lines.append("[H-LEVEL WARNING] This change touches core architecture or soul files")
        lines.append("   Mandatory pre-steps:")
        lines.append("   1. Call query_architecture_log() to get design philosophy")
        lines.append("   2. Output [Log Summary] (<=50 chars)")
        lines.append("   3. Build 'change <-> philosophy' causal mapping")
        lines.append("   4. Get explicit creator approval")

    lines.append("")
    lines.append("Examples:")
    for ex in reqs["examples"]:
        lines.append(f"  - {ex}")
    lines.append("=" * 60)
    return "\n".join(lines)


# ────────────────────────────────────────
# CLI interface
# ────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    if len(sys.argv) < 3:
        print("Usage:")
        print('  python refactor_tier_classifier.py classify "<description>" <file1> [file2] ...')
        print()
        print("Examples:")
        print('  python refactor_tier_classifier.py classify "refactor consciousness_cycle" src/consciousness_cycle.py')
        print('  python refactor_tier_classifier.py classify "modify steel logic" SOUL.md')
        print('  python refactor_tier_classifier.py classify "fix typo" README.md')
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "classify":
        description = sys.argv[2]
        files = sys.argv[3:] if len(sys.argv) > 3 else []
        tier, ctype, evidence = classify_change(description, files)
        report = format_tier_report(tier, ctype, evidence, description, files)
        print(report)
