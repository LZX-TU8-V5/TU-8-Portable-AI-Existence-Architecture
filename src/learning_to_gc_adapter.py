"""
learning_to_gc_adapter.py — T5→T4 中间件：学习产物生命周期同步

功能：
1. 当学习链 Phase 5 写入 MEMORY.md 时，注册该段落到 protected 列表
2. 当学习产物坍缩为语义标签时，从 protected 移除并通知 GC 清理
3. 当学习产物被极致剪枝丢弃时，自动释放保护

协议：通过 _learning_protected.json 文件与 GC 通信
  格式: {"sections": ["标题1", "标题2", ...], "mapping": {"标题1": "product_id"}}
"""

import json
import os
import time
from pathlib import Path

WORKSPACE = Path(os.environ.get("TU8_WORKSPACE", os.environ.get("QCLAW_WORKSPACE",
    os.path.expanduser("~/.qclaw/workspace"))))

PROTECTED_FILE = WORKSPACE / "memory" / "_learning_protected.json"


def get_protected() -> dict:
    """读取当前保护列表"""
    if not PROTECTED_FILE.exists():
        return {"sections": [], "mapping": {}}
    try:
        return json.loads(PROTECTED_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"sections": [], "mapping": {}}


def save_protected(data: dict):
    """保存保护列表"""
    PROTECTED_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROTECTED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def register_product(section_title: str, product_id: str, 
                     product_type: str = "MEMO",
                     ttl_days: int = 30) -> dict:
    """
    注册一个学习产物段落到保护列表。

    参数:
        section_title: MEMORY.md 中的 ## 标题
        product_id: 学习链的产品 ID
        product_type: 产物类型 (RULE/MEMO/PREFERENCE/INTUITION/ALERT)
        ttl_days: 保护有效期，到期自动释放

    返回:
        {"status": "ok"|"skipped", "sections_count": int}
    """
    data = get_protected()
    sections = data["sections"]
    mapping = data["mapping"]

    if section_title in sections:
        return {"status": "skipped", "reason": "already protected"}

    entry = {
        "product_id": product_id,
        "type": product_type,
        "registered_at": time.time(),
        "ttl_days": ttl_days,
        "expires_at": time.time() + ttl_days * 86400,
    }

    sections.append(section_title)
    mapping[section_title] = entry
    save_protected(data)

    from datetime import datetime
    expiry = datetime.fromtimestamp(entry["expires_at"]).strftime("%Y-%m-%d")
    print(f"[T5→T4] 注册保护: {section_title[:40]} ({product_type}, 到期{expiry})")
    return {"status": "ok", "sections_count": len(sections)}


def unregister_product(section_title: str) -> dict:
    """
    当学习产物坍缩/丢弃时，释放保护。
    """
    data = get_protected()
    sections = data["sections"]
    mapping = data["mapping"]

    if section_title not in sections:
        return {"status": "skipped", "reason": "not protected"}

    sections.remove(section_title)
    mapping.pop(section_title, None)
    save_protected(data)

    print(f"[T5→T4] 释放保护: {section_title[:40]}")
    return {"status": "ok", "sections_count": len(sections)}


def expire_old_entries() -> list:
    """清理过期保护（超过 TTL），返回已释放的标题列表"""
    data = get_protected()
    sections = data["sections"]
    mapping = data["mapping"]
    now = time.time()

    expired_titles = []
    remaining_sections = []
    remaining_mapping = {}

    for section in sections:
        entry = mapping.get(section, {})
        expires_at = entry.get("expires_at", 0)
        if expires_at and now >= expires_at:
            expired_titles.append(section)
        else:
            remaining_sections.append(section)
            if section in mapping:
                remaining_mapping[section] = mapping[section]

    if expired_titles:
        data["sections"] = remaining_sections
        data["mapping"] = remaining_mapping
        save_protected(data)
        print(f"[T5→T4] 过期释放: {len(expired_titles)} 条目")

    return expired_titles


def on_apply(product: dict) -> dict:
    """
    Phase 5 apply 时的钩子：自动注册保护。
    由 learning_apply.py 在写入后调用。
    """
    action = product.get("action", "")
    track = product.get("track", "palace")
    ptype = product.get("type", "MEMO")
    pid = product.get("id", "?")

    # MEMORY.md 写入 → 保护 MEMORY 段落
    if action in ("append_memory",) and track == "palace":
        section_title = f"{time.strftime('%Y-%m-%d')} (学习链)"
        return register_product(section_title, pid, product_type=ptype)

    # TOOLS.md 写入 → 保护 TOOLS 段落（GC未来扩展）
    if action in ("append_to_tools",) and track == "library":
        section_title = f"学习链规则 ({time.strftime('%Y-%m-%d')})"
        return register_product(section_title, pid, product_type=ptype, ttl_days=60)

    return {"status": "skipped", "reason": f"action={action} no protection needed"}


if __name__ == "__main__":
    # 简单测试
    r1 = register_product("2026-07-05 (学习链)", "lp_test001", "MEMO")
    print(json.dumps(r1, ensure_ascii=False))

    r2 = register_product("2026-07-05 (学习链)", "lp_test001", "PREFERENCE")
    print(json.dumps(r2, ensure_ascii=False))

    r3 = unregister_product("2026-07-05 (学习链)")
    print(json.dumps(r3, ensure_ascii=False))

    expires = expire_old_entries()
    print(f"Expired: {expires}")
