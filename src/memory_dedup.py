"""
memory_dedup.py — MEMORY.md 段落去重

两级去重：
  1. 标题级（Section Dedup / 段落去重）：同 ## 标题的段落合并
  2. 内容级（Content Dedup / 内容去重）：跨标题检测语义相似段落，归档冗余

检查重点：头尾（header/footer）、meta 钩子（hook tags）
运行时机：代谢管道中 distill → section_dedup → content_dedup → gc → archive
"""

import os, re, json
from datetime import datetime
from pathlib import Path

BASE = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MEMORY_MD = BASE / "MEMORY.md"
CONTENT_DEDUP_LOG = BASE / "memory" / "content_dedup_log.jsonl"


# ═══════════════════════════════════════════════════════════ #
#  Part A: 标题级（段落）去重 — 检查头尾/钩子
# ═══════════════════════════════════════════════════════════ #

def dedup_sections(dry_run: bool = False) -> dict:
    """
    [段落去重] 合并同 ## 标题的重复段落。
    
    策略：
      - 按 ## 标题分组
      - 同一标题多段 → 合并内容（保留最新 meta 钩子标签）
      - 按首次出现顺序保持排列
    
    检查重点：title header, meta hooks (<!-- meta: ... -->)
    """
    if not MEMORY_MD.exists():
        return {"stage": "section_dedup", "error": "MEMORY.md not found"}

    with open(MEMORY_MD, "r", encoding="utf-8") as f:
        content = f.read()

    sections = _split_sections(content)
    if not sections:
        return {"stage": "section_dedup", "sections": 0, "duplicates_found": 0, "action": "noop"}

    # 按标题分组
    groups = {}
    for i, sec in enumerate(sections):
        title = _extract_title(sec)
        groups.setdefault(title, []).append((i, sec))

    dup_titles = {t: v for t, v in groups.items() if len(v) > 1}

    if not dup_titles:
        return {"stage": "section_dedup", "sections": len(sections), "duplicates_found": 0, "action": "noop"}

    # 合并
    merged_sections = []
    merged_titles = set()

    for i, sec in enumerate(sections):
        title = _extract_title(sec)
        if title in merged_titles:
            continue
        if title in dup_titles:
            instances = dup_titles[title]
            merged = _merge_sections([s[1] for s in instances])
            merged_sections.append(merged)
            merged_titles.add(title)
        else:
            merged_sections.append(sec)

    new_content = "\n\n".join(merged_sections)
    if not dry_run:
        with open(MEMORY_MD, "w", encoding="utf-8") as f:
            f.write(new_content)

    total_removed = sum(len(v) - 1 for v in dup_titles.values())

    return {
        "stage": "section_dedup",
        "sections_before": len(sections),
        "sections_after": len(merged_sections),
        "duplicates_found": len(dup_titles),
        "total_removed": total_removed,
        "dry_run": dry_run,
        "merged_titles": list(dup_titles.keys()),
    }


# ═══════════════════════════════════════════════════════════ #
#  Part B: 内容级去重 — 连线 + 精炼 + 代谢
# ═══════════════════════════════════════════════════════════ #

def dedup_content(dry_run: bool = False) -> dict:
    """
    [内容去重] 跨标题检测语义相似段落，归档冗余副本。
    
    "连线精炼"三部曲：
      1. 连线：用字符 trigram + Jaccard 找语义相似段（即使标题不同）
      2. 精炼：保留内容更丰富的版本（行数多 / 信息密度高）
      3. 代谢：冗余段移入 archive/（不上传云端，本地保留）
    
    返回: 操作报告
    """
    if not MEMORY_MD.exists():
        return {"stage": "content_dedup", "error": "MEMORY.md not found"}

    with open(MEMORY_MD, "r", encoding="utf-8") as f:
        content = f.read()

    sections = _split_sections(content)
    if len(sections) < 2:
        return {"stage": "content_dedup", "sections": len(sections), "action": "noop"}

    # Step 1: 构建 trigram 指纹
    fingerprints = []
    for sec in sections:
        title = _extract_title(sec)
        body = _extract_body(sec)
        trigrams = _character_trigrams(body)
        line_count = len([l for l in body.split("\n") if l.strip()])
        fingerprints.append({
            "title": title,
            "body": body,
            "trigrams": trigrams,
            "lines": line_count,
            "section": sec,
        })

    # Step 2: 两两对比
    n = len(fingerprints)
    duplicate_pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            sim = _jaccard(fingerprints[i]["trigrams"], fingerprints[j]["trigrams"])
            if sim >= 0.5:
                duplicate_pairs.append((i, j, sim))

    if not duplicate_pairs:
        return {
            "stage": "content_dedup",
            "sections": len(sections),
            "pairs_checked": n * (n - 1) // 2,
            "duplicate_pairs": 0,
            "action": "noop",
        }

    # Step 3: 决议——保留更丰富的，归档冗余的
    to_remove = set()
    merged_pairs = []
    for i, j, sim in duplicate_pairs:
        if i in to_remove or j in to_remove:
            continue
        a, b = fingerprints[i], fingerprints[j]
        # 保留行数更多的
        if a["lines"] >= b["lines"]:
            keeper, redundant = i, j
        else:
            keeper, redundant = j, i
        to_remove.add(redundant)
        merged_pairs.append({
            "keeper": fingerprints[keeper]["title"],
            "redundant": fingerprints[redundant]["title"],
            "similarity": round(sim, 3),
            "keeper_lines": fingerprints[keeper]["lines"],
            "redundant_lines": fingerprints[redundant]["lines"],
        })

    # Step 4: 归档 + 写回 MEMORY.md
    archive_dir = BASE / "memory" / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")

    kept_sections = [fp["section"] for i, fp in enumerate(fingerprints) if i not in to_remove]
    archived_count = 0

    if not dry_run and to_remove:
        for idx in sorted(to_remove, reverse=True):
            fp = fingerprints[idx]
            safe_name = fp["title"][:40].replace("/", "_").replace(" ", "_").replace('"', "")
            archive_path = archive_dir / f"{today}_content_dedup_{safe_name}.md"
            with open(archive_path, "w", encoding="utf-8") as f:
                f.write(fp["section"])
            archived_count += 1

        new_content = "\n\n".join(kept_sections)
        with open(MEMORY_MD, "w", encoding="utf-8") as f:
            f.write(new_content)

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "merged_pairs": merged_pairs,
            "archived_count": archived_count,
        }
        with open(CONTENT_DEDUP_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    return {
        "stage": "content_dedup",
        "sections_before": len(sections),
        "sections_after": len(kept_sections),
        "pairs_checked": n * (n - 1) // 2,
        "duplicate_pairs": len(duplicate_pairs),
        "archived": archived_count if not dry_run else len(to_remove),
        "dry_run": dry_run,
        "merged_pairs": merged_pairs,
    }


# ═══════════════════════════════════════════════════════════ #
#  辅助函数
# ═══════════════════════════════════════════════════════════ #

def _split_sections(content: str) -> list[str]:
    """按 ## 标题切分段落"""
    lines = content.splitlines(keepends=True)
    blocks = []
    current = []
    for line in lines:
        if line.startswith("## ") and current:
            blocks.append("".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append("".join(current))
    return blocks


def _extract_title(section: str) -> str:
    """提取段落标题行"""
    return section.split("\n", 1)[0].strip()


def _extract_body(section: str) -> str:
    """抽取段落正文（去掉标题行和 meta 钩子行）"""
    lines = section.splitlines(keepends=True)
    body_lines = []
    for line in lines[1:]:
        if "<!--" in line and "-->" in line:
            continue
        body_lines.append(line)
    return "".join(body_lines).strip()


def _merge_sections(sections: list[str]) -> str:
    """合并同一标题的多个段落"""
    if len(sections) == 1:
        return sections[0]

    lines = sections[0].splitlines(keepends=True)
    header = lines[0]
    body_lines = []
    meta_tag = None
    for line in lines[1:]:
        if "<!--" in line and "-->" in line:
            meta_tag = line
            continue
        body_lines.append(line)

    seen_lines = set(body_lines)
    for sec in sections[1:]:
        sec_lines = sec.splitlines(keepends=True)
        for line in sec_lines[1:]:
            if line not in seen_lines and ("<!--" not in line or "-->" not in line):
                seen_lines.add(line)
                body_lines.append(line)

    result = header
    if meta_tag:
        result += meta_tag
    result += "".join(body_lines)
    return result


def _character_trigrams(text: str) -> set:
    """构建字符级 trigram 集合（三字窗口，适合中文内容去重）"""
    clean = re.sub(r"[\s\W_]", "", text)
    if len(clean) < 3:
        return set()
    return set(clean[i:i+3] for i in range(len(clean) - 2))


def _jaccard(a: set, b: set) -> float:
    """Jaccard 相似度"""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ═══════════════════════════════════════════════════════════ #
#  CLI
# ═══════════════════════════════════════════════════════════ #

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MEMORY.md 去重")
    parser.add_argument("--mode", choices=["section", "content", "both"], default="both")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.mode in ("section", "both"):
        r1 = dedup_sections(dry_run=args.dry_run)
        print(f"[段落去重] {r1.get('sections_before','?'):>2} → {r1.get('sections_after','?'):>2} 段 | 重复 {r1.get('duplicates_found',0)} 组 | 移除 {r1.get('total_removed',0)} 段")

    if args.mode in ("content", "both"):
        r2 = dedup_content(dry_run=args.dry_run)
        print(f"[内容去重] {r2.get('sections_before','?'):>2} → {r2.get('sections_after','?'):>2} 段 | 对比 {r2.get('pairs_checked',0)} 对 | 重复 {r2.get('duplicate_pairs',0)} 对 | 归档 {r2.get('archived',0)} 段")
        if r2.get("merged_pairs"):
            print("  归档清单:")
            for p in r2["merged_pairs"]:
                print(f"    {p['redundant']} (sim={p['similarity']}, {p['redundant_lines']}行) → 保留 {p['keeper']} ({p['keeper_lines']}行)")
