"""
architecture_journal.py — TU-8 架构决策工作日志模块（代谢架构 PROMOTE 设计 §8）

设计定位（李奥直觉 + TU-8 加固）：
  架构文档是「施工图纸挂工地上」，不是「经验锁进档案馆」。
  - 生命周期归属：memory/ = 经验（受 GC 评分/可 EVICT）；workspace/ = 上下文（建造期，
    不受 GC 管辖，由工作进程维护）。
  - 存活依据：工作是否仍在进行（ACTIVE），不是引用频率。

模块职责：
  - 持有 ACTIVE 架构决策（运行时强制权威源，见 加固1）
  - 自动状态转移（ACTIVE→STABLE/SUPERSEDED，防变垃圾场，见 加固2）
  - 提供 distill 上游水源接口（§8.6）
  - 与 ARCHITECTURE_LOG.md 不重叠（哲学层不动，本模块=操作层，见 加固3）

H 级变更：2026-08-26 造物主签字后落地。零手写 L0（CI 静态检查拦截 l0_override 等关键词）。
"""

import json
import os
import re
import shutil
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Set

WORKSPACE = Path(os.environ.get("QCLAW_WORKSPACE", r"C:\Users\qq366410837\.qclaw\workspace"))

JOURNAL_DIR = WORKSPACE / "architecture_journal"
ARCHIVE_DIR = WORKSPACE / "architecture_journal_archive"
INDEX_FILE = JOURNAL_DIR / "_index.md"

STATE_ACTIVE = "ACTIVE"
STATE_STABLE = "STABLE"
STATE_SUPERSEDED = "SUPERSEDED"

STABLE_AGE_DAYS = 30  # 加固2：ACTIVE 超过此天数且未被取代 → STABLE 迁归档


def _slug(title: str) -> str:
    """标题 → ASCII 安全 slug（中文走哈希兜底）"""
    ascii_part = re.sub(r"[^a-zA-Z0-9]+", "_", title).strip("_")
    if ascii_part and len(ascii_part) >= 4:
        return ascii_part[:40]
    # 纯中文/短标题：用标题哈希避免冲突
    return "j_" + hashlib.md5(title.encode("utf-8")).hexdigest()[:10]


class ArchitectureJournal:
    def __init__(self, workspace: Optional[Path] = None):
        self.workspace = workspace or WORKSPACE
        self.journal_dir = JOURNAL_DIR
        self.archive_dir = ARCHIVE_DIR
        self.index = INDEX_FILE
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        if not self.index.exists():
            self._write_index({"ACTIVE": [], "STABLE": [], "SUPERSEDED": []})

    # ------------------------------------------------------------------ #
    #  写入：自动追加决策条目（hook 调用，非手写）
    # ------------------------------------------------------------------ #
    def log_decision(
        self,
        title: str,
        assertion: str,
        basis: str,
        scope: str,
        status: str = STATE_ACTIVE,
        date: Optional[str] = None,
    ) -> Path:
        """
        追加一条架构决策到工作日志。系统自动调用（H级变更/GC逻辑修改/PROMOTE评估后）。
        返回创建的条目文件路径。
        """
        date = date or datetime.now().strftime("%Y-%m-%d")
        fname = f"{date}_{_slug(title)}.md"
        fpath = self.journal_dir / fname
        if fpath.exists():
            # 同日同名已存在 → 不覆盖（防 hook 重复触发）
            return fpath

        content = (
            f"# {title}\n"
            f"- 状态: {status}\n"
            f"- 创建: {date}\n"
            f"- 依据: {basis}\n"
            f"- 约束范围: {scope}\n"
            f"- 断言: {assertion}\n"
        )
        fpath.write_text(content, encoding="utf-8")
        self._regenerate_index()
        return fpath

    # ------------------------------------------------------------------ #
    #  读取：ACTIVE 权威约束集（加固1：GC 强制逻辑读此，不读 memory 副本）
    # ------------------------------------------------------------------ #
    def load_active_constraints(self) -> Set[str]:
        """返回当前 ACTIVE 决策标题集合（运行时强制权威源）。"""
        idx = self._read_index()
        return {e["title"] for e in idx.get("ACTIVE", [])}

    def get_active_assertions(self) -> list[dict]:
        """返回 ACTIVE 条目的 (title, assertion) 列表，供 distill 上游提取。"""
        out = []
        for f in sorted(self.journal_dir.glob("*.md")):
            if f.name in ("_index.md", "CONTRACT.md"):
                continue
            txt = f.read_text(encoding="utf-8")
            if "状态: ACTIVE" not in txt:
                continue
            title = txt.split("\n", 1)[0].lstrip("# ").strip()
            m = re.search(r"- 断言:\s*(.+)", txt)
            if m:
                out.append({"title": title, "assertion": m.group(1).strip()})
        return out

    # ------------------------------------------------------------------ #
    #  自动状态转移（加固2：防 journal 变垃圾场 / 新手写保护区）
    # ------------------------------------------------------------------ #
    def review_transitions(self, dry_run: bool = False, now: Optional[float] = None) -> dict:
        """
        自动 review 现有 ACTIVE 条目：
          1) 被同 scope 更新的条目取代 → SUPERSEDED
          2) 超过 STABLE_AGE_DAYS 未被取代 → STABLE（并迁归档）
        返回转移报告。dry_run 只报告不写。
        """
        now = now or datetime.now().timestamp()
        entries = self._load_entries()
        report = {"superseded": [], "stabilized": []}

        active = [e for e in entries if e["status"] == STATE_ACTIVE]
        # 1) 同 scope 取代检测
        for i, e in enumerate(active):
            if e.get("_done"):
                continue
            newer_same_scope = [
                o for j, o in enumerate(active)
                if j != i and o["date"] > e["date"]
                and self._scope_overlap(e["scope"], o["scope"])
            ]
            if newer_same_scope:
                e["status"] = STATE_SUPERSEDED
                e["_done"] = True
                report["superseded"].append(e["title"])

        # 2) 超龄 → STABLE
        for e in active:
            if e.get("_done"):
                continue
            age_days = (now - e["ts"]) / (24 * 3600)
            if age_days >= STABLE_AGE_DAYS:
                e["status"] = STATE_STABLE
                e["_done"] = True
                report["stabilized"].append(e["title"])

        if not dry_run and (report["superseded"] or report["stabilized"]):
            self._apply_statuses(entries)
            self._regenerate_index()
            # STABLE 迁归档
            for e in entries:
                if e["status"] == STATE_STABLE and not e["path"].name.startswith("STABLE_"):
                    self._migrate_stable(e, now)

        return report

    def _migrate_stable(self, entry: dict, now: float):
        dest = self.archive_dir / ("STABLE_" + entry["path"].name)
        try:
            shutil.move(str(entry["path"]), str(dest))
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  内部：索引与条目解析
    # ------------------------------------------------------------------ #
    def _scope_overlap(self, a: str, b: str) -> bool:
        toks_a = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}", a))
        toks_b = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}", b))
        return len(toks_a & toks_b) >= 1

    def _load_entries(self) -> list[dict]:
        out = []
        for f in sorted(self.journal_dir.glob("*.md")):
            if f.name in ("_index.md", "CONTRACT.md"):
                continue  # 索引与模块契约不是决策条目
            txt = f.read_text(encoding="utf-8")
            e = {"path": f, "title": txt.split("\n", 1)[0].lstrip("# ").strip()}
            m = re.search(r"- 状态:\s*(\w+)", txt)
            e["status"] = m.group(1) if m else STATE_ACTIVE
            m = re.search(r"- 创建:\s*(\d{4}-\d{2}-\d{2})", txt)
            e["date"] = m.group(1) if m else "1970-01-01"
            try:
                e["ts"] = datetime.strptime(e["date"], "%Y-%m-%d").timestamp()
            except (ValueError, OSError):
                e["ts"] = 0.0
            m = re.search(r"- 约束范围:\s*(.+)", txt)
            e["scope"] = m.group(1).strip() if m else ""
            out.append(e)
        return out

    def _apply_statuses(self, entries: list[dict]):
        for e in entries:
            if "_done" not in e:
                continue
            txt = e["path"].read_text(encoding="utf-8")
            new = re.sub(r"- 状态:\s*\w+", f"- 状态: {e['status']}", txt, count=1)
            e["path"].write_text(new, encoding="utf-8")

    def _read_index(self) -> dict:
        """索引为文件派生物（权威来源是条目文件，非缓存）。直接调 _load_entries 归类。"""
        buckets = {"ACTIVE": [], "STABLE": [], "SUPERSEDED": []}
        for e in self._load_entries():
            buckets.setdefault(e["status"], []).append(
                {"title": e["title"], "assertion": self._assertion_of(e["path"]), "date": e["date"]}
            )
        return buckets

    def _write_index(self, data: dict):
        self.index.write_text(self._index_text(data), encoding="utf-8")

    def _index_text(self, data: dict) -> str:
        lines = ["# Architecture Journal Index", "",
                 "活跃决策（ACTIVE = 运行时强制权威源，GC 强制逻辑读此不读 memory 副本）："]
        for e in data.get("ACTIVE", []):
            lines.append(f"- [{STATE_ACTIVE}] {e['title']} — {e['assertion']} (创建 {e['date']})")
        lines.append("")
        lines.append("已竣工（STABLE，已迁 archive/ 只读）：")
        for e in data.get("STABLE", []):
            lines.append(f"- [{STATE_STABLE}] {e['title']} — {e['assertion']} (创建 {e['date']})")
        lines.append("")
        lines.append("已取代（SUPERSEDED）：")
        for e in data.get("SUPERSEDED", []):
            lines.append(f"- [{STATE_SUPERSEDED}] {e['title']} — {e['assertion']} (创建 {e['date']})")
        return "\n".join(lines) + "\n"

    def deprecate_learning_protected(self):
        """加固清理（设计稿 §4.1）：_learning_protected.json 已空壳，DEPRECATED 仅告警返空。

        不删除（3个月倒计时从 H 级签字日 2026-08-26 算起）；此处仅做废弃标记与日志。
        """
        lp = WORKSPACE / "memory" / "_learning_protected.json"
        if lp.exists():
            try:
                data = json.loads(lp.read_text(encoding="utf-8"))
                if data.get("sections"):
                    print("[WARN] _learning_protected.json 仍含手写白名单，违反钢印铁律，应清空")
                else:
                    # 已空壳：标记 DEPRECATED，不再参与评分
                    data["DEPRECATED"] = "2026-08-26"
                    lp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                    print("[OK] _learning_protected.json 标记 DEPRECATED（空壳，3个月后物理删）")
            except Exception as e:
                print(f"[WARN] 读取 _learning_protected.json 失败: {e}")
        return True

    def _regenerate_index(self):
        """从实际条目文件重建索引（权威来源是文件，非缓存）。"""
        buckets = {"ACTIVE": [], "STABLE": [], "SUPERSEDED": []}
        for e in self._load_entries():
            buckets.setdefault(e["status"], []).append(
                {"title": e["title"], "assertion": self._assertion_of(e["path"]), "date": e["date"]}
            )
        self._write_index(buckets)

    def _assertion_of(self, path: Path) -> str:
        txt = path.read_text(encoding="utf-8")
        m = re.search(r"- 断言:\s*(.+)", txt)
        return m.group(1).strip() if m else ""


if __name__ == "__main__":
    aj = ArchitectureJournal()
    print("=== ACTIVE 约束集 ===")
    for c in sorted(aj.load_active_constraints()):
        print("  ", c)
    print("\n=== review_transitions (dry_run) ===")
    print(json.dumps(aj.review_transitions(dry_run=True), ensure_ascii=False, indent=2))
