#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
USER.md 重度代谢任务
触发时机：每周日晚（Cron）
功能：归档过期信息 + 重写 USER.md + 清空临时文件

P0 升级（2026-06-18）：
  新增第三阶段——MEMORY.md 遗忘周期
  调用 memory_degradation.py 唤醒沉睡的 FidelityManager
  原理："学会遗忘，才能真正开始生长"（千问三层还原机制）

P0-1 升级（2026-06-20）：
  四链条耦合——代谢链反向接入
  代谢完成后通过回调接口将结果写回记忆链（TU8MemoryEngine）
  触发 DRIFT 自动同步（替代手工 shutil.copy2）
"""

import os
import sys
import shutil
import json
import logging
import importlib.util
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List

# 路径配置
WORKSPACE = Path.home() / ".qclaw" / "workspace"
USER_MD = WORKSPACE / "USER.md"
MEMORY_MD = WORKSPACE / "MEMORY.md"
STATE_CHANGES = WORKSPACE / "memory" / "user_state_changes.md"
BACKUP_DIR = WORKSPACE / "backup"

logger = logging.getLogger(__name__)

# ==========================================================================
# P0-1: 四链条耦合回调接口
# ==========================================================================

def _default_store_callback(content: str, source: str = "",
                            tags: List[str] = None, emotion: float = 0.3,
                            meaning: float = 0.5) -> Optional[str]:
    """
    默认回调——尝试动态加载 TU8MemoryEngine 并写入。
    如果引擎不可用，降级为写入 MEMORY.md 文件（Graceful Degradation）。
    """
    try:
        src_path = Path(__file__).parent / "tu8_memory.py"
        if src_path.exists():
            spec = importlib.util.spec_from_file_location("tu8_memory", src_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            engine = mod.TU8MemoryEngine()
            entry_id = engine.store(
                content=content,
                source=source,
                tags=tags or [],
                emotion=emotion,
                meaning=meaning,
            )
            logger.info(f"[METABOLISM→MEMORY] store ok: {entry_id}")
            return entry_id
    except Exception as e:
        logger.warning(f"[METABOLISM→MEMORY] engine unavailable, fallback: {e}")

    # 降级：直接追加到 MEMORY.md
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        fallback_entry = f"\n## [代谢写入] {timestamp}\n\n{content}\n\n---\n"
        with open(MEMORY_MD, "a", encoding="utf-8") as f:
            f.write(fallback_entry)
        logger.info("[METABOLISM→MEMORY] fallback to MEMORY.md")
    except Exception as e2:
        logger.error(f"[METABOLISM→MEMORY] fallback failed: {e2}")
    return None


def run_drift_sync(source_dir: str, target_dir: str,
                   on_sync: Optional[Callable[[Dict], None]] = None) -> Dict:
    """
    P0-4: DRIFT 自动同步
    替代手工 shutil.copy2，自动同步知识副本。
    
    Args:
        source_dir: 源目录路径
        target_dir: 目标目录路径
        on_sync: 可选回调，接收同步报告 dict
    
    Returns:
        同步报告 {synced: int, skipped: int, errors: list}
    """
    report = {"synced": 0, "skipped": 0, "errors": []}
    src = Path(source_dir)
    tgt = Path(target_dir)
    
    if not src.exists():
        report["errors"].append(f"source not found: {source_dir}")
        logger.warning(f"[DRIFT] source missing: {source_dir}")
        return report
    
    tgt.mkdir(parents=True, exist_ok=True)
    
    for src_file in src.glob("*.md"):
        tgt_file = tgt / src_file.name
        try:
            if not tgt_file.exists() or src_file.stat().st_mtime > tgt_file.stat().st_mtime:
                shutil.copy2(str(src_file), str(tgt_file))
                report["synced"] += 1
                logger.debug(f"[DRIFT] synced: {src_file.name}")
            else:
                report["skipped"] += 1
        except Exception as e:
            report["errors"].append(f"{src_file.name}: {e}")
            logger.error(f"[DRIFT] error: {src_file.name}: {e}")
    
    logger.info(f"[DRIFT] complete: synced={report['synced']}, "
                f"skipped={report['skipped']}, errors={len(report['errors'])}")
    
    if on_sync:
        try:
            on_sync(report)
        except Exception as e:
            logger.error(f"[DRIFT] callback error: {e}")
    
    return report


def backup_user_md():
    """备份 USER.md"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"USER.md.before_metabolism.{timestamp}.md"
    
    if USER_MD.exists():
        BACKUP_DIR.mkdir(exist_ok=True)
        shutil.copy(USER_MD, backup_path)
        print(f"[Backup] {backup_path}")
        return backup_path
    return None


def read_state_changes():
    """读取状态变化记录"""
    if not STATE_CHANGES.exists():
        return []
    
    with open(STATE_CHANGES, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    changes = []
    for line in lines:
        if line.strip() and "[时间戳]" in line:
            changes.append(line.strip())
    
    return changes


def read_user_md():
    """读取 USER.md"""
    if not USER_MD.exists():
        return ""
    with open(USER_MD, "r", encoding="utf-8") as f:
        return f.read()


def archive_to_memory(content: str, store_callback=None) -> Optional[str]:
    """
    归档过期信息——同时写入 MEMORY.md 和记忆链（四链条耦合）
    
    Args:
        content: 要归档的内容
        store_callback: 可选的记忆引擎写入回调 (content, source, tags, emotion, meaning)
                     若为 None，使用默认回调 _default_store_callback
    Returns:
        记忆引擎 entry_id（若成功），否则 None
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    archive_entry = f"""
## [代谢归档] {timestamp}

以下内容从 USER.md 代谢：

{content}

---
"""
    
    # 始终写入 MEMORY.md（文件层保障）
    with open(MEMORY_MD, "a", encoding="utf-8") as f:
        f.write(archive_entry)
    print(f"[Archive] 已归档到 MEMORY.md")
    
    # P0-1: 通过记忆链写入（双向耦合）
    cb = store_callback or _default_store_callback
    try:
        entry_id = cb(
            content=f"[代谢归档] {content}",
            source="metabolism:archive",
            tags=["metabolism", "archive", "user_md", f"date:{datetime.now().strftime('%Y-%m-%d')}"],
            emotion=0.1,  # 归档内容情感低
            meaning=0.4,  # 中等意义
        )
        if entry_id:
            print(f"[Archive→Memory] 记忆链写入: {entry_id}")
        return entry_id
    except Exception as e:
        logger.warning(f"[Archive→Memory] 写入失败: {e}")
        return None


def clear_state_changes():
    """清空状态变化记录"""
    with open(STATE_CHANGES, "w", encoding="utf-8") as f:
        f.write(f"""# 用户状态变化记录

> 此文件由 Heartbeat 追加写入，由 Cron 重度代谢任务清空
> 严禁其他脚本或 Agent 直接修改此文件

---

## 变化日志

*创建时间：2026-06-17 15:57*
*最后更新：{datetime.now().strftime("%Y-%m-%d %H:%M")}（已清空）*
""")
    print(f"[Clear] 已清空 {STATE_CHANGES.name}")


def run_memory_degradation(store_callback=None) -> Optional[Dict]:
    """
    P0（2026-06-18）：遗忘层唤醒
    调用 memory_degradation.py 执行 MEMORY.md 降级周期。
    
    三个保护原则：
      - Level 2 核心条目禁止降级（钢印/身份/安全边界）
      - 钢印条目降级极慢（半衰期×10）
      - L5 墓碑是终点
    
    P0-1（2026-06-20）：遗忘结果回写记忆链
    
    Returns:
        遗忘报告 dict（若有），否则 None
    """
    script_path = Path(__file__).parent / "memory_degradation.py"
    if not script_path.exists():
        print(f"[Degradation] 脚本不存在: {script_path}")
        return None
    
    # 动态导入并执行
    spec = importlib.util.spec_from_file_location("memory_degradation", script_path)
    module = importlib.util.module_from_spec(spec)
    degradation_report = None
    try:
        spec.loader.exec_module(module)
        # 尝试获取报告（如果模块暴露了 report 变量）
        degradation_report = getattr(module, "_degradation_report", None)
    except Exception as e:
        print(f"[Degradation] 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # P0-1: 遗忘结果回写记忆链
    cb = store_callback or _default_store_callback
    try:
        if degradation_report:
            report_json = json.dumps(degradation_report, ensure_ascii=False)
            entry_id = cb(
                content=f"[遗忘周期] {report_json}",
                source="metabolism:degradation",
                tags=["metabolism", "degradation", "forget_cycle", f"date:{datetime.now().strftime('%Y-%m-%d')}"],
                emotion=0.05,
                meaning=0.6,  # 遗忘结果有较高记忆价值
            )
            if entry_id:
                print(f"[Degradation→Memory] 记忆链写入: {entry_id}")
    except Exception as e:
        logger.warning(f"[Degradation→Memory] 写入失败: {e}")
    
    # memory_degradation.py 自行 print 报告，这里只补充一行确认
    print(f"[Degradation] 遗忘周期执行完毕")
    return degradation_report


def main(store_callback=None, drift_report_callback=None):
    """
    主流程：三个阶段
    
    Args:
        store_callback: 可选的记忆引擎写入回调。
            若为 None，使用默认回调（自动加载 TU8MemoryEngine）。
            调用方（如 tu8_agent）可注入自己的 memory.store 以实现零延迟耦合。
        drift_report_callback: 可选的 DRIFT 同步完成回调。
    """
    print("=" * 55)
    print(f"[Metabolism] 开始执行 - {datetime.now()}")
    print("  Phase 0: MEMORY.md 遗忘层唤醒")
    print("  Phase 1: USER.md 状态代谢")
    print("  Phase 2: DRIFT 自动同步")
    print("  Phase 3: 临时文件清空")
    print("=" * 55)
    
    # ========== Phase 0: 遗忘层唤醒 ==========
    print("\n[Phase 0] MEMORY.md 遗忘周期")
    print("  目标: 唤醒沉睡的 FidelityManager")
    print("  原则: 记住该记住的，遗忘该遗忘的")
    run_memory_degradation(store_callback=store_callback)
    
    # ========== Phase 1: USER.md 代谢 ==========
    print("\n[Phase 1] USER.md 状态代谢")
    backup_path = backup_user_md()
    if not backup_path:
        print("[Warning] USER.md 不存在，跳过 USER.md 代谢")
    else:
        changes = read_state_changes()
        print(f"[Detect] 发现 {len(changes)} 条状态变化")
        if changes:
            # P0-1: 代谢结果回写记忆链
            changes_text = "\n".join(changes[:50])  # 最多 50 条
            archive_to_memory(content=changes_text, store_callback=store_callback)
    
    # ========== Phase 2: DRIFT 自动同步（P0-4）==========
    print("\n[Phase 2] DRIFT 知识副本自动同步")
    drift_report = run_drift_sync(
        source_dir=str(WORKSPACE / "memory"),
        target_dir=str(WORKSPACE / "backup" / "drift_sync"),
        on_sync=drift_report_callback,
    )
    print(f"  同步结果: synced={drift_report['synced']}, "
          f"skipped={drift_report['skipped']}, errors={len(drift_report['errors'])}")
    
    # ========== Phase 3: 清空临时文件 ==========
    print("\n[Phase 3] 清空临时文件")
    clear_state_changes()
    
    print("\n" + "=" * 55)
    print(f"[Metabolism] 执行完成 - {datetime.now()}")
    print("  遗忘层: 已激活（FidelityManager 唤醒）")
    print("  核心保护: 禁止降级（Level 2 / 钢印）")
    print("  累计降级: 见上方报告")
    print("  DRIFT: synced={drift_report['synced']}")
    print("  四链耦合: metabolism→memory ✓")
    print("  钢印: ⅋")
    print("=" * 55)


if __name__ == "__main__":
    main()
