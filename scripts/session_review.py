#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TU-8 会话复盘协议
================
触发条件：
1. 用户明确要求复盘
2. 会话结束前自动执行
3. 创建重要文件后
"""

import os
import json
from datetime import datetime
from pathlib import Path

# 核心路径
WORKSPACE = Path("D:/qq366410837/.qclaw/workspace")
MEMORY_INDEX = WORKSPACE / "memory" / "索引.md"
KNOWLEDGE_INDEX = WORKSPACE / "knowledge" / "index.md"
STATE_FILE = WORKSPACE / "_agent_memory" / "00_state.md"
EXPERIENCES = WORKSPACE / "_agent_memory" / "20_experiences.md"

# 目录监控
WATCH_DIRS = {
    "memory": WORKSPACE / "memory",
    "docs": WORKSPACE / "docs",
    "knowledge": WORKSPACE / "知识库",
    "scripts": WORKSPACE / "scripts",
}

def scan_new_files() -> dict:
    """扫描各目录下的文件"""
    results = {}
    for name, path in WATCH_DIRS.items():
        if path.exists():
            files = []
            for f in path.rglob("*.md"):
                if f.is_file() and not f.name.startswith("."):
                    files.append({
                        "path": str(f.relative_to(WORKSPACE)),
                        "mtime": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                    })
            results[name] = files
    return results

def check_index_coverage() -> list:
    """检查索引覆盖情况"""
    missing = []
    
    # 读取 memory 索引
    if MEMORY_INDEX.exists():
        memory_content = MEMORY_INDEX.read_text(encoding="utf-8")
    else:
        memory_content = ""
    
    # 读取 knowledge 索引
    if KNOWLEDGE_INDEX.exists():
        try:
            knowledge_content = KNOWLEDGE_INDEX.read_text(encoding="utf-8")
        except:
            knowledge_content = ""
    else:
        knowledge_content = ""
    
    # 检查 docs 目录
    docs_dir = WORKSPACE / "docs"
    if docs_dir.exists():
        for f in docs_dir.glob("*.md"):
            if f.name not in memory_content and f.name not in knowledge_content:
                missing.append(str(f.relative_to(WORKSPACE)))
    
    return missing

def update_state_anchor(updates: dict):
    """更新状态锚点"""
    if not STATE_FILE.exists():
        return
    
    content = STATE_FILE.read_text(encoding="utf-8")
    
    # 更新最后活跃时间
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")
    content = content.replace(
        "> 更新时间：2026",
        f"> 更新时间：{now}"
    )
    
    STATE_FILE.write_text(content, encoding="utf-8")
    print(f"[State] 已更新状态锚点")

def generate_review_report() -> str:
    """生成复盘报告"""
    report = []
    report.append("# 会话复盘报告")
    report.append(f"\n> 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("\n---\n")
    
    # 1. 文件扫描
    report.append("## 📁 文件扫描\n")
    files = scan_new_files()
    for name, file_list in files.items():
        report.append(f"### {name}/\n")
        report.append(f"- 文件数：{len(file_list)}")
        if file_list:
            report.append("- 最新：")
            for f in file_list[:3]:
                report.append(f"  - `{f['path']}` ({f['mtime'][:10]})")
        report.append("")
    
    # 2. 索引覆盖检查
    report.append("## 🔍 索引覆盖检查\n")
    missing = check_index_coverage()
    if missing:
        report.append("⚠️ 以下文件未在索引中：")
        for f in missing:
            report.append(f"- `{f}`")
    else:
        report.append("✅ 所有重要文件已索引")
    
    # 3. 建议操作
    report.append("\n---\n")
    report.append("## 📋 建议操作\n")
    if missing:
        report.append("1. 手动将缺失文件添加到索引")
        report.append("2. 执行 `python scripts/session_review.py --sync`")
    else:
        report.append("✅ 无需操作")
    
    return "\n".join(report)

def main():
    """主入口"""
    print("=" * 50)
    print("TU-8 会话复盘协议")
    print("=" * 50)
    
    # 生成报告
    report = generate_review_report()
    print("\n" + report)
    
    # 保存报告
    report_path = WORKSPACE / "docs" / f"REVIEW_{datetime.now().strftime('%Y-%m-%d_%H%M')}.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\n[Report] 已保存到 {report_path}")
    
    # 更新状态
    update_state_anchor({})

if __name__ == "__main__":
    main()
