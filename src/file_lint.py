"""
src/file_lint.py — TU-8 Workspace 落位合规检查（file_lint）

功能：扫描 workspace 根目录与 src/，检测违反 GOVERNANCE 铁律五的回潮现象。
- 根目录散落 .md（非身份层文件）
- src 孤儿诊断脚本（_check/_fix/_test/_diag/_find/_tmp 等前缀，未进 _quarantine/）
- 裸文件名跨目录引用（../../ 深层相对链，或指向已移动文件的旧路径）

设计：纯 stdlib，无外部依赖，可被 HEARTBEAT 季度体检 subprocess 调用。
退出码：0=无违规，1=有违规（便于 cron/体检判定）。

用法：
  python src/file_lint.py            # 输出违规清单
  python src/file_lint.py --json     # JSON 格式（供程序消费）
  python src/file_lint.py --strict   # 严格模式（含 warn 级也报错）
"""
import sys
import os
import json
import re
from pathlib import Path

# ---- 身份层根目录文件（允许留根，不报违规）----
IDENTITY_ROOT = {
    "SOUL.md", "AGENTS.md", "MEMORY.md", "USER.md", "IDENTITY.md", "TOOLS.md",
    "HEARTBEAT.md", "BEHAVIOR_RULES.md", "START_HERE.md", "BOOT.md",
    "GOVERNANCE.md", "TODO_MASTER.md",
    # L0-L5 子文档（SOUL.md 内联引用）
    "L0_存在.md", "L1_认知.md", "L2_方法论.md", "L4_协作.md", "L5_钢印.md",
    # 被 Gateway 加载的 .node.md
    "AGENTS.node.md", "BOOT.node.md", "BOOTSTRAP.node.md", "HEARTBEAT.node.md",
    "IDENTITY.node.md", "TOOLS.node.md", "USER.node.md",
    # 元文件
    "README.md",
}

# 允许的根目录非 md（程序文件/配置）
ROOT_NON_MD_ALLOW = {".gitignore", ".gitattributes", "openclaw.json"}

# src 孤儿诊断脚本前缀
ORPHAN_PREFIXES = ("_check", "_fix", "_test", "_diag", "_find",
                   "_kill_orb", "_restart_orb", "_scale_check", "_tmp", "_audit")

# 允许散落的文档目录
ALLOWED_MD_DIRS = {
    "docs/design", "docs/reports", "docs/tasks", "docs/architecture",
    "docs/emergence", "memory", "knowledge", "knowledge_base", "用户",
    "secure_vault", "architecture_journal", "_agent_memory", "backup",
    "_GOV_ARCHIVE_20260827_170629", "小说",
}

# 深层相对引用正则（../../ 或 跨目录 ../）
DEEP_REL_RE = re.compile(r"\.\./\.\./|\.\./[a-zA-Z]")

# 治理说明性文本（教人"禁止 ../../"，自身含该串但非真实引用）
DEEP_REL_EXEMPT_RE = re.compile(
    r"(禁止|避免|不得|不应|不要|深层相对|相对路径|相对链)", re.DOTALL
)

# 已知已移动文件的旧裸名（移动后不应再有裸名引用指向非自身）
MOVED_LEGACY_NAMES = [
    "ARCHITECTURE_LOG.md",  # 已移至 docs/design/
    "CORE_MEMORY.md", "索引.md", "example_memory_node.md",
]


def lint_root_md(ws: Path, strict: bool):
    """根目录散落 .md 检查"""
    issues = []
    for p in sorted(ws.glob("*.md")):
        if p.name in IDENTITY_ROOT:
            continue
        issues.append({
            "type": "root_scattered_md",
            "severity": "error",
            "path": p.name,
            "hint": "应移入 docs/{design,reports,tasks,architecture}/ 或 memory/",
        })
    return issues


def lint_src_orphan(ws: Path, strict: bool):
    """src 孤儿诊断脚本检查"""
    issues = []
    src = ws / "src"
    if not src.exists():
        return issues
    quar = src / "_quarantine"
    for p in sorted(src.glob("*.py")):
        if p.name.startswith(ORPHAN_PREFIXES):
            # 在 _quarantine/ 下是允许的
            if quar in p.parents:
                continue
            issues.append({
                "type": "src_orphan_script",
                "severity": "warn" if not strict else "error",
                "path": str(p.relative_to(ws)),
                "hint": "孤儿诊断脚本应移入 src/_quarantine/ 观察 30 天",
            })
    return issues


def lint_deep_rel(ws: Path, strict: bool, sample=200):
    """深层相对引用检查（md 文件内）"""
    issues = []
    count = 0
    for p in ws.rglob("*.md"):
        # 跳过备份区
        if any(part.startswith("_GOV_ARCHIVE") or part == "backup" for part in p.parts):
            continue
        # 排除运行态目录（knowledge/knowledge_base 内部相对路径非治理对象）
        try:
            rel0 = p.relative_to(ws).parts[0]
        except ValueError:
            rel0 = ""
        if rel0 in ("knowledge", "knowledge_base", "用户"):
            continue
        count += 1
        if count > sample:
            break
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for m in DEEP_REL_RE.finditer(text):
            # 排除治理说明语境（教人禁止 ../../ 的句子本身）
            ctx = text[max(0, m.start() - 30):m.end() + 30]
            if DEEP_REL_EXEMPT_RE.search(ctx):
                continue
            issues.append({
                "type": "deep_relative_ref",
                "severity": "warn",
                "path": str(p.relative_to(ws)),
                "hint": f"含深层相对引用 '{m.group()}'，应改为 @语义锚点 或绝对 docs/ 路径",
            })
            break  # 每文件只报一次
    return issues


def lint_legacy_bare_ref(ws: Path, strict: bool):
    """已移动文件的裸名仍被引用（断链风险）"""
    issues = []
    for name in MOVED_LEGACY_NAMES:
        hits = []
        for p in ws.rglob("*.md"):
            if any(part.startswith("_GOV_ARCHIVE") or part == "backup" for part in p.parts):
                continue
            # 排除文件自身位置（移动后的新家不应算断链）
            if p.name == name:
                continue
            # 排除历史归档快照（非活引用）
            if "archive" in p.parts or "_agent_memory" in p.parts:
                continue
            # 排除运行态目录（knowledge/knowledge_base 内部相对路径非治理对象）
            if p.parts[0] in ("knowledge", "knowledge_base", "用户"):
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            # 词边界匹配：避免 docs/design/ARCHITECTURE_LOG.md 被误判为裸名残留
            import re as _re
            if _re.search(r"(?<![-/\w])%s(?!\w)" % _re.escape(name), text):
                hits.append(str(p.relative_to(ws)))
        if hits:
            issues.append({
                "type": "legacy_bare_ref",
                "severity": "warn",
                "path": f"{name} (in {len(hits)} files)",
                "hint": "该文件已移动，引用应改为新路径或 @语义锚点",
                "refs": hits[:10],
            })
    return issues


def main():
    ws = Path(os.environ.get("QCLAW_WORKSPACE",
                             str(Path.home() / ".qclaw" / "workspace")))
    if not ws.exists():
        print(f"[file_lint] workspace not found: {ws}", file=sys.stderr)
        sys.exit(2)

    strict = "--strict" in sys.argv
    as_json = "--json" in sys.argv

    all_issues = []
    all_issues += lint_root_md(ws, strict)
    all_issues += lint_src_orphan(ws, strict)
    all_issues += lint_deep_rel(ws, strict)
    all_issues += lint_legacy_bare_ref(ws, strict)

    errors = [i for i in all_issues if i["severity"] == "error"]
    warns = [i for i in all_issues if i["severity"] == "warn"]

    if as_json:
        print(json.dumps({
            "error_count": len(errors),
            "warn_count": len(warns),
            "issues": all_issues,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"[file_lint] 根目录散落 md: {len([i for i in all_issues if i['type']=='root_scattered_md'])}")
        print(f"[file_lint] src 孤儿脚本: {len([i for i in all_issues if i['type']=='src_orphan_script'])}")
        print(f"[file_lint] 深层相对引用: {len([i for i in all_issues if i['type']=='deep_relative_ref'])}")
        print(f"[file_lint] 旧裸名引用: {len([i for i in all_issues if i['type']=='legacy_bare_ref'])}")
        print(f"[file_lint] 总计: {len(errors)} error / {len(warns)} warn")
        if all_issues:
            print("--- 详情 ---")
            for i in all_issues[:30]:
                print(f"  [{i['severity']}] {i['type']}: {i['path']} — {i['hint']}")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
