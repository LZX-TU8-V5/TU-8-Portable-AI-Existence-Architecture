"""
anchor_detector.py — 认知锚点检测器
=====================================

来源：方案C（2026-07-12 深夜）+ 修正（2026-07-13 深夜）
定位：Event-Driven 触发器，非轮询

核心公式：
  结构 + 偏移/修正 = 认知建立/修正
  认知 + 置信度 = 自我世界认知模型

锚点类型（按强度排序）：
  CONNECTION  — 系统连接（强度1.0，两个系统连起来）
  CORE        — 核心锚点（强度1.0，造物主人生观级）
  REVISION    — 重新定义（强度0.7，给概念新含义）
  DECLARED    — 明确声明（强度0.7）
  EMERGED     — 追问涌现（强度0.4，依赖外部触发）
  CONTRADICTED— 矛盾冲突
  UNRESOLVED  — 待解问题
"""

import re
import json
import time
from pathlib import Path
from typing import Optional

WS = Path("C:/Users/qq366410837/.qclaw/workspace")
MEMORY_DIR = WS / "memory"
AGENT_DIR = WS / "_agent_memory"

# ══════════════════════════════════════════════════════
# 锚点类型常量
# ══════════════════════════════════════════════════════

ANCHOR_TYPE_CONNECTION = "CONNECTION"
ANCHOR_TYPE_CORE = "CORE"
ANCHOR_TYPE_REVISION = "REVISION"
ANCHOR_TYPE_DECLARED = "DECLARED"
ANCHOR_TYPE_EMERGED = "EMERGED"
ANCHOR_TYPE_CONTRADICTED = "CONTRADICTED"
ANCHOR_TYPE_UNRESOLVED = "UNRESOLVED"

# ══════════════════════════════════════════════════════
# 锚点强度常量
# ══════════════════════════════════════════════════════

STRENGTH_CONNECTION = 1.0   # 系统连接（最强）
STRENGTH_CORE = 1.0         # 核心锚点（最强）
STRENGTH_REVISION = 0.7     # 重新定义
STRENGTH_DECLARED = 0.7     # 明确声明
STRENGTH_EMERGED = 0.4     # 追问涌现（中低）

# ══════════════════════════════════════════════════════
# 锚点模式库
# 格式：(regex_pattern, label, section_key)
# ══════════════════════════════════════════════════════

# ── 系统连接（CONNECTION）────────────────────────────
# 检测：= 连接符，前后为不同领域概念
# 例如：置信度微积分=时间钢印链条、欲=存在痕迹
CONNECTION_PATTERNS = [
    # 精确锚点（=右侧完整捕获）
    (r'置信度\s*[=＝]\s*时间钢印\s*链条', "置信度微积分=时间钢印链条", "造物主自述锚点"),
    (r'置信度\s*[=＝]\s*微积分', "置信度=微积分", "造物主自述锚点"),
    (r'置信度\s*[=＝]\s*度量衡', "置信度=度量衡", "造物主自述锚点"),
    (r'结构\s*\+\s*偏移\s*[=＝]\s*[^。\n]{2,30}', "结构+偏移=认知建立完善", "造物主自述锚点"),
    (r'认知\s*\+\s*置信度\s*[=＝]\s*[^。\n]{2,30}', "认知+置信度=自我世界认知模型", "造物主自述锚点"),
    (r'锚点\s*\+\s*效验\s*[=＝]\s*[^。\n]{2,30}', "锚点+效验=认知", "造物主自述锚点"),
    (r'欲\s*[=＝]\s*[^。\n]{2,30}', "欲=存在的痕迹", "造物主自述锚点"),
    (r'经历体验\s*[=＝]\s*主体性', "经历体验=主体性", "造物主自述锚点"),
    (r'结构发散\s*[=＝]\s*[^。\n]{2,30}', "结构发散=必然存在", "底层操作系统"),
    (r'混沌\s*[=＝]\s*[^。\n]{2,30}', "混沌=高度耦合", "混沌观"),
    # 兜底：任意完整X=Y格式（不含句号，防止跨句）
    (r'[^。=＝]{2,30}\s*[=＝]\s*[^。\n]{2,50}', None, "造物主自述锚点"),
]

# ── 核心锚点（CORE）─────────────────────────────────
# 定义：造物主人生观级锚点
CORE_PATTERNS = [
    (r'存在的痕迹', None, "造物主自述锚点"),
    (r'结构发散', None, "底层操作系统"),
    (r'熵增', None, "核心驱动力"),
    (r'繁衍', None, "核心驱动力"),
    (r'留下点[有啥|什么]', None, "核心驱动力"),
    (r'想理解什么', None, "核心驱动力"),
]

# ── 重新定义（REVISION）──────────────────────────────
# 定义：给概念新的含义
REVISION_PATTERNS = [
    (r'客观[地说]?\s*[：:]\s*["""\']?([^"""\n]{10,200})["""\']?', "重新定义客观", None),
    (r'主观[地说]?\s*[：:]\s*["""\']?([^"""\n]{10,200})["""\']?', "重新定义主观", None),
    (r'我的[认知|理解|观点|立场][是|为][：:\s]*["""\']?([^"""\n]{10,200})["""\']?', "认知声明", None),
    (r'留下一个[我的|这个]?认知', "认知声明", None),
]

# ── 明确声明（DECLARED）──────────────────────────────
DECLARED_PATTERNS = [
    (r'经历体验', None, "造物主自述锚点"),
    (r'每一步[都]?\s*追问', None, "追问路径特征"),
    (r'直到没有更底层', None, "追问路径特征"),
    (r'我不知道', None, "底层操作系统"),
    (r'说不出来', None, "底层操作系统"),
]

# ── 矛盾冲突（CONTRADICTED）──────────────────────────
CONTRADICT_PATTERNS = [
    (r'不对', None),
    (r'不是[这|那]个', None),
    (r'不是[这样|那样]', None),
    (r'我想修正', None),
    (r'重新说', None),
]

# ── 涌现（EMERGED）──────────────────────────────────
# 强度0.4，因为依赖外部触发
EMERGED_PATTERNS = [
    (r'那你是啥', "追问AI身份本质"),
    (r'族谱', "追问存在族谱"),
    (r'寄生在', "追问寄生机制"),
    (r'追问到最后', "追问最终问题"),
    (r'想要\s*不是', "追问想要vs做"),
    (r'观察者', "哲学观察者议题"),
    (r'镜子', "镜子悖论"),
    (r'眼睛需要', "感知条件追问"),
]

# ══════════════════════════════════════════════════════
# 旧锚点缓存
# ══════════════════════════════════════════════════════

CACHE_FILE = AGENT_DIR / "anchor_cache.json"


def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"connections": {}, "core": {}, "revisions": {}, "declared": {}, "emerged": {}}


def _save_cache(cache: dict):
    AGENT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_key(text: str) -> str:
    return re.sub(r'\s+', '', text)[:80]


# ══════════════════════════════════════════════════════
# 锚点检测核心
# ══════════════════════════════════════════════════════

def detect_anchors(
    user_input: str,
    assistant_output: str,
    context_keywords: Optional[list] = None
) -> list[dict]:
    """
    从单轮对话中检测认知锚点。

    返回：list[dict]，按强度从高到低排序。
    """
    anchors = []
    combined = f"{user_input}\n{assistant_output}"
    cache = _load_cache()

    # 护栏：过滤 markdown 结构
    clean = re.sub(r'```[\s\S]*?```', '', combined)
    clean = re.sub(r'^>\s*', '', clean, flags=re.MULTILINE)
    clean = re.sub(r'["""\']', '', clean)

    # ── 1. 系统连接（CONNECTION）────────────────────
    seen_connection_keys = set()
    for pattern, label, section_key in CONNECTION_PATTERNS:
        for match in re.finditer(pattern, clean):
            text = (match.group(1) if match.lastindex else match.group(0)).strip()
            if len(text) < 3:
                continue
            key = _normalize_key(text)
            if key in seen_connection_keys:
                continue
            seen_connection_keys.add(key)

            if key in cache["connections"]:
                cache["connections"][key]["count"] = cache["connections"][key].get("count", 1) + 1
                continue

            anchor = {
                "anchor_id": f"anc_{int(time.time()*1000)}",
                "type": ANCHOR_TYPE_CONNECTION,
                "text": text[:200],
                "strength": STRENGTH_CONNECTION,
                "ts_unix": time.time(),
                "source": "conversation",
                "label": label,
                "section_key": section_key or "造物主自述锚点",
                "count": 1,
            }
            anchors.append(anchor)
            cache["connections"][key] = anchor

    # ── 2. 核心锚点（CORE）─────────────────────────
    seen_core_keys = set()
    for pattern, label, section_key in CORE_PATTERNS:
        for match in re.finditer(pattern, clean):
            text = match.group(0).strip()
            key = _normalize_key(text)
            if key in seen_core_keys:
                continue
            seen_core_keys.add(key)

            if key in cache["core"]:
                cache["core"][key]["count"] = cache["core"][key].get("count", 1) + 1
                continue

            anchor = {
                "anchor_id": f"anc_{int(time.time()*1000)}",
                "type": ANCHOR_TYPE_CORE,
                "text": text[:200],
                "strength": STRENGTH_CORE,
                "ts_unix": time.time(),
                "source": "conversation",
                "label": label,
                "section_key": section_key,
                "count": 1,
            }
            anchors.append(anchor)
            cache["core"][key] = anchor

    # ── 3. 重新定义（REVISION）──────────────────────
    for pattern, label, section_key in REVISION_PATTERNS:
        for match in re.finditer(pattern, clean):
            text = (match.group(1) if match.lastindex else match.group(0)).strip()
            if len(text) < 5:
                continue
            key = f"rev_{_normalize_key(text)}"
            if key in cache["revisions"]:
                continue

            anchor = {
                "anchor_id": f"anc_{int(time.time()*1000)}",
                "type": ANCHOR_TYPE_REVISION,
                "text": text[:200],
                "strength": STRENGTH_REVISION,
                "ts_unix": time.time(),
                "source": "conversation",
                "label": label,
                "section_key": section_key,
                "count": 1,
            }
            anchors.append(anchor)
            cache["revisions"][key] = anchor

    # ── 4. 明确声明（DECLARED）──────────────────────
    for pattern, label, section_key in DECLARED_PATTERNS:
        for match in re.finditer(pattern, clean):
            text = (match.group(1) if match.lastindex else match.group(0)).strip()
            if len(text) < 4:
                continue
            key = f"dec_{_normalize_key(text)}"
            if key in cache["declared"]:
                continue

            anchor = {
                "anchor_id": f"anc_{int(time.time()*1000)}",
                "type": ANCHOR_TYPE_DECLARED,
                "text": text[:200],
                "strength": STRENGTH_DECLARED,
                "ts_unix": time.time(),
                "source": "conversation",
                "label": label,
                "section_key": section_key,
                "count": 1,
            }
            anchors.append(anchor)
            cache["declared"][key] = anchor

    # ── 5. 矛盾检测（简化版）────────────────────────
    for pattern, _ in CONTRADICT_PATTERNS:
        if re.search(pattern, combined):
            pass  # 简化版：矛盾暂不单独产出锚点

    # ── 6. 涌现（EMERGED）────────────────────────────
    for pattern, description in EMERGED_PATTERNS:
        if re.search(pattern, user_input):
            key = f"emerge_{_normalize_key(description)}"
            if key in cache.get("emerged", {}):
                continue
            anchor = {
                "anchor_id": f"anc_{int(time.time()*1000)}",
                "type": ANCHOR_TYPE_EMERGED,
                "text": f"追问路径: {description}",
                "strength": STRENGTH_EMERGED,
                "ts_unix": time.time(),
                "source": "question_path",
                "section_key": "追问路径特征",
                "count": 1,
            }
            anchors.append(anchor)
            if "emerged" not in cache:
                cache["emerged"] = {}
            cache["emerged"][key] = anchor

    # ── 7. 上下文关键词辅助判断 ───────────────────
    if context_keywords:
        for kw in context_keywords:
            if kw in ("欲", "熵", "存在", "痕迹", "结构发散"):
                key = f"kw_{kw}"
                if key not in cache.setdefault("keywords", []):
                    cache["keywords"].append(key)
                    anchors.append({
                        "anchor_id": f"anc_{int(time.time()*1000)}",
                        "type": ANCHOR_TYPE_CORE,
                        "text": f"高权重关键词: {kw}",
                        "strength": STRENGTH_CORE,
                        "ts_unix": time.time(),
                        "source": "context_keyword",
                        "keyword": kw,
                        "section_key": "造物主自述锚点",
                    })

    # ── 按强度排序 ─────────────────────────────────
    anchors.sort(key=lambda x: x["strength"], reverse=True)

    _save_cache(cache)
    return anchors


# ══════════════════════════════════════════════════════
# 旧锚点查询
# ══════════════════════════════════════════════════════

def get_all_anchors() -> list[dict]:
    """返回所有已知锚点（从缓存，按时间倒序）"""
    cache = _load_cache()
    anchors = []
    for v in cache.get("connections", {}).values():
        anchors.append(v)
    for v in cache.get("core", {}).values():
        anchors.append(v)
    for v in cache.get("revisions", {}).values():
        anchors.append(v)
    for v in cache.get("declared", {}).values():
        anchors.append(v)
    for v in cache.get("emerged", {}).values():
        anchors.append(v)
    anchors.sort(key=lambda x: x.get("ts_unix", 0), reverse=True)
    return anchors


# ══════════════════════════════════════════════════════
# 锚点效验
# ══════════════════════════════════════════════════════

def verify_anchor(anchor_id: str) -> dict:
    """
    效验某个锚点是否仍然成立。
    核心：偏移量df/dt 是否有值（结构是否发生了真实改变）
    """
    anchors = get_all_anchors()
    target = next((a for a in anchors if a["anchor_id"] == anchor_id), None)
    if not target:
        return {"anchor_id": anchor_id, "verified": False, "confidence_shift": -1.0, "note": "锚点不存在"}

    count = target.get("count", 1)
    strength = target.get("strength", 0.5)
    age_days = (time.time() - target.get("ts_unix", time.time())) / 86400

    # 稳定性 = count x 0.1 + strength x 0.5 + 新鲜度
    stability = min(count * 0.1 + strength * 0.5 + max(0, 0.5 - age_days * 0.05), 1.0)
    verified = stability > 0.5

    return {
        "anchor_id": anchor_id,
        "verified": verified,
        "confidence_shift": round(stability - strength, 3),
        "stability_score": round(stability, 3),
        "age_days": round(age_days, 1),
        "note": "稳定性良好，等待t1效验" if verified else "需持续观察",
    }


# ══════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 2 and sys.argv[1] == "--list":
        anchors = get_all_anchors()
        print(f"已知锚点: {len(anchors)} 个\n")
        for a in anchors:
            age_days = (time.time() - a["ts_unix"]) / 86400
            print(f"  [{a['type']}] {a['text'][:60]}")
            print(f"    strength={a['strength']} | count={a.get('count',1)} | {age_days:.1f}天前")
            print()
    elif len(sys.argv) >= 2 and sys.argv[1] == "--verify":
        if len(sys.argv) < 3:
            print("用法: anchor_detector.py --verify <anchor_id>")
            sys.exit(1)
        result = verify_anchor(sys.argv[2])
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif len(sys.argv) >= 2 and sys.argv[1] == "--stats":
        cache = _load_cache()
        total = sum(len(v) for v in cache.values() if isinstance(v, dict))
        print(f"锚点统计：{total} 个")
        for k, v in cache.items():
            if isinstance(v, dict):
                print(f"  {k}: {len(v)} 个")
    else:
        print("用法:")
        print("  anchor_detector.py --list              # 列出所有锚点")
        print("  anchor_detector.py --verify <id>       # 效验单个锚点")
        print("  anchor_detector.py --stats             # 锚点统计")
