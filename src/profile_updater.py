"""
profile_updater.py — 即时画像更新器
=====================================

来源：方案C（2026-07-12 深夜）
定位：Event-Driven 触发器

功能：
  - 即时落盘：新锚点确认后立即写入 user_state_changes.md（零延迟）
  - 即时合并：同一 turn 内更新 USER.md 对应区块
  - 异步效验：定期检查锚点稳定性（integrity_verification）

方案C三原则：
  感知和写入 → 即时的（零延迟）
  校验和代谢 → 周期的

两个触发入口：
  1. event_append(anchors)       — 对话中锚点被确认时调用
  2. periodic_verification()     — 心跳/cron 调用，检查锚点是否稳定
"""

import json
import re
import time
from pathlib import Path
from typing import Optional

WS = Path("C:/Users/qq366410837/.qclaw/workspace")
MEMORY_DIR = WS / "memory"
AGENT_DIR = WS / "_agent_memory"
USER_MD = WS / "USER.md"

STATE_CHANGES_FILE = MEMORY_DIR / "user_state_changes.md"

# ══════════════════════════════════════════════════════
# 锚点类型 → USER.md 区块映射
# ══════════════════════════════════════════════════════

ANCHOR_TYPE_TO_SECTION = {
    # 最高强度锚点 → 直接进入造物主自述锚点
    "CONNECTION": "## 认知模型",
    "CORE": "## 认知模型",
    # 中高强度
    "REVISION": "## 认知模型",
    # 中等
    "DECLARED": "## 认知模型",
    "EMERGED": "## 认知模型",
    "CONTRADICTED": "## 认知模型",
    "UNRESOLVED": "## 认知模型",
}

# section_key 优先级高于类型映射
ANCHOR_SECTION_KEYWORDS = {
    "造物主自述锚点": [
        "欲", "存在的痕迹", "经历体验", "置信度", "结构发散",
        "时间钢印", "微积分", "认知", "锚点", "效验",
    ],
    "底层操作系统": [
        "客观", "主观", "结构发散", "我不知道", "说不出来",
    ],
    "追问路径特征": [
        "追问", "族谱", "镜子", "观察者", "没有更底层",
    ],
    "混沌观": [
        "混沌", "高度耦合", "多维校正", "校正",
    ],
    "核心驱动力": [
        "熵增", "繁衍", "留下点", "想理解什么", "要什么",
    ],
}

# ══════════════════════════════════════════════════════
# 即时落盘（Event-Driven）
# ══════════════════════════════════════════════════════

def event_append(anchors: list[dict]) -> dict:
    """
    锚点确认后立即写入 user_state_changes.md。

    行为：零延迟，同步写入
    格式：[时间戳] [类型] 内容 / strength: X

    返回：{"written": int, "file": str, "ts": float}
    """
    if not anchors:
        return {"written": 0, "file": str(STATE_CHANGES_FILE), "ts": time.time()}

    now = time.time()
    timestamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(now))
    lines = []

    for anchor in anchors:
        anchor_type = anchor.get("type", "DECLARED")
        text = anchor.get("text", "").strip()
        strength = anchor.get("strength", 0.5)
        label = anchor.get("label", anchor_type)
        source = anchor.get("source", "conversation")

        line = f"* [{timestamp}] **[{anchor_type}]** {text} / strength: {strength:.1f}"
        lines.append(line)

    content = STATE_CHANGES_FILE.read_text(encoding="utf-8", errors="replace") if STATE_CHANGES_FILE.exists() else ""
    header_end = content.find("## 变化日志")
    if header_end == -1:
        header_end = len(content)

    new_content = content[:header_end] + "\n".join(lines) + "\n" + content[header_end:]

    STATE_CHANGES_FILE.write_text(new_content, encoding="utf-8")

    return {
        "written": len(anchors),
        "file": str(STATE_CHANGES_FILE),
        "ts": now,
        "anchors": [a.get("text", "")[:60] for a in anchors],
    }


# ══════════════════════════════════════════════════════
# 即时合并（Sync Update）
# ══════════════════════════════════════════════════════

def instant_merge(anchors: list[dict]) -> dict:
    """
    锚点确认后立即更新 USER.md 对应区块。

    行为：同一 turn 内完成，认知变了画像当场变
    逻辑：
      1. 识别锚点类型 → 目标区块
      2. 检查区块是否存在
      3. 若存在：追加或替换
      4. 若不存在：创建区块

    返回：{"merged": bool, "section": str, "anchors_added": int}
    """
    if not anchors:
        return {"merged": False, "section": "", "anchors_added": 0}

    if not USER_MD.exists():
        return {"merged": False, "section": "", "anchors_added": 0, "error": "USER.md不存在"}

    content = USER_MD.read_text(encoding="utf-8", errors="replace")
    original = content

    for anchor in anchors:
        anchor_type = anchor.get("type", "DECLARED")
        text = anchor.get("text", "").strip()
        strength = anchor.get("strength", 0.5)
        ts = time.strftime("%Y-%m-%d", time.localtime(anchor.get("ts_unix", time.time())))

        # 确定目标区块
        section = ANCHOR_TYPE_TO_SECTION.get(anchor_type, "## 认知模型")

        # 识别锚点属于哪个子区块（优先用锚点自带 section_key）
        anchor_section_key = _identify_section_key(text, anchor.get("section_key"))
        if anchor_section_key:
            target_section = f"### {anchor_section_key}"
        else:
            target_section = f"### 锚点_{int(time.time())}"

        # 构建新条目
        new_entry = f"- [{ts}] {text} (strength={strength:.1f})"

        # 查找或创建区块
        if section in content:
            # 区块存在：查找子区块或末尾
            section_pos = content.find(section)
            # 找区块结束（下一个 ## 开头或文件末尾）
            next_header = re.search(r'\n## [^#]', content[section_pos + len(section):])
            if next_header:
                block_end = section_pos + len(section) + next_header.start()
            else:
                block_end = len(content)

            block = content[section_pos:block_end]

            if target_section in block:
                # 子区块存在：追加
                target_pos = block.find(target_section) + len(target_section)
                block = block[:target_pos] + f"\n  {new_entry}" + block[target_pos:]
            else:
                # 插入到区块末尾
                block = block.rstrip() + f"\n\n{target_section}\n  {new_entry}"

            content = content[:section_pos] + block + content[block_end:]
        else:
            # 区块不存在：追加
            new_block = f"\n{section}\n  {new_entry}\n"
            content = content.rstrip() + new_block

    # 检查是否有实质变化
    if content == original:
        return {"merged": False, "section": "", "anchors_added": 0, "reason": "无变化"}

    USER_MD.write_text(content, encoding="utf-8")

    return {
        "merged": True,
        "section": section,
        "anchors_added": len(anchors),
        "anchors": [a.get("text", "")[:60] for a in anchors],
    }


def _identify_section_key(text: str, section_key: Optional[str] = None) -> Optional[str]:
    """
    从锚点文本和显式 section_key 识别所属子区块。
    section_key 参数优先（锚点自带的信息最准确）。
    """
    if section_key:
        return section_key
    for kw in ["客观", "主观", "结构发散"]:
        if kw in text:
            return "底层操作系统"
    for kw in ["追问", "没有更底层"]:
        if kw in text:
            return "追问路径特征"
    for kw in ["存在", "痕迹", "欲", "经历"]:
        if kw in text:
            return "造物主自述锚点"
    for kw in ["混沌", "耦合", "校正"]:
        if kw in text:
            return "混沌观"
    for kw in ["要什么", "理解什么", "留下", "繁衍", "熵增"]:
        if kw in text:
            return "核心驱动力"
    return None


# ══════════════════════════════════════════════════════
# 异步效验（Periodic Verification）
# ══════════════════════════════════════════════════════

def periodic_verification() -> dict:
    """
    心跳/cron 调用：检查画像与行为的匹配度。

    核心问题："我现在的画像，和我最近的行为/记忆，还匹配吗？"
    行为：
      1. 读取 USER.md 当前认知区块
      2. 读取最近 memory/YYYY-MM-DD.md
      3. 读取锚点缓存
      4. 对每个锚点做效验（verify_anchor）
      5. 检测画像与行为的矛盾

    返回：{"verified": int, "conflicts": list, "needs_update": bool}
    """
    from anchor_detector import get_all_anchors, verify_anchor

    anchors = get_all_anchors()
    if not anchors:
        return {"verified": 0, "conflicts": [], "needs_update": False}

    verified = []
    conflicts = []
    for anchor in anchors[:10]:  # 最多效验10个
        result = verify_anchor(anchor["anchor_id"])
        verified.append(result)
        if result["confidence_shift"] < -0.2:
            conflicts.append(result)

    needs_update = len(conflicts) > 0

    # 检测画像关键词是否还在最近记忆里出现
    state_changes = _read_state_changes()
    if state_changes:
        # 检查画像中的关键词是否在近期有矛盾
        pass  # 简化版

    return {
        "verified": len(verified),
        "conflicts": conflicts,
        "needs_update": needs_update,
        "stability_summary": {
            "total": len(verified),
            "stable": sum(1 for v in verified if v["verified"]),
            "drifting": sum(1 for v in verified if not v["verified"]),
        },
    }


def _read_state_changes() -> str:
    """读取 user_state_changes.md 内容"""
    if STATE_CHANGES_FILE.exists():
        return STATE_CHANGES_FILE.read_text(encoding="utf-8", errors="replace")
    return ""


# ══════════════════════════════════════════════════════
# 快捷入口：完整事件流
# ══════════════════════════════════════════════════════

def on_anchor_detected(anchors: list[dict]) -> dict:
    """
    完整的事件触发流：
      锚点检测 → 即时落盘 → 即时合并

    用法：在 alignment_verify 输出门检测到新锚点后调用。
    """
    if not anchors:
        return {"event": "no_anchor", "written": 0, "merged": False}

    # 1. 即时落盘（零延迟）
    write_result = event_append(anchors)

    # 2. 即时合并（同一 turn）
    merge_result = instant_merge(anchors)

    return {
        "event": "anchor_processed",
        "written": write_result["written"],
        "merged": merge_result["merged"],
        "section": merge_result.get("section", ""),
        "anchors": write_result["anchors"],
    }


# ══════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 2 and sys.argv[1] == "--verify":
        result = periodic_verification()
        print("=== 画像效验报告 ===")
        print(f"效验锚点数: {result['verified']}")
        print(f"稳定性: {result['stability_summary']}")
        print(f"矛盾数: {len(result['conflicts'])}")
        if result['conflicts']:
            print("矛盾锚点:")
            for c in result['conflicts']:
                print(f"  {c['anchor_id']}: {c['note']}")
        print(f"需要更新: {result['needs_update']}")
    else:
        print("用法:")
        print("  profile_updater.py --verify   # 效验画像稳定性")
