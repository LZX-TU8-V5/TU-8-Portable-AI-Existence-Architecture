"""
memory_gc.py — TU-8 记忆垃圾回收机制（代谢触发器）v2

设计哲学：模拟大自然「用进废退」
  - 显性规则（常用）→ 保留/升级
  - 隐性规则（偶尔用）→ 压缩/降级
  - 废弃规则（长期不用）→ 淘汰

触发时机：
  1. 每次对话结束（轻量级）
  2. 每日深睡期（重量级）
  3. Token 预算告警时（紧急回收）

指标：
  - last_accessed: 最后访问时间
  - access_count: 累计访问次数（带90天时间折扣）
  - confidence: 钢印置信度（如有）
  - token_cost: 存储该记忆的 Token 开销

改进 v2：
  - access_count 时间折扣（90天半衰）
  - last_accessed 自动刷新（根据上下文关键词匹配）
  - meta 标签写回机制
"""

import os
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Set

# T4→T5 适配器
try:
    from gc_to_learning_adapter import record_gc_result
except ImportError:
    def record_gc_result(report): return {"recorded": False, "reason": "adapter not found"}

# T2→T4 适配器
try:
    from seal_to_gc_adapter import compute_seal_bonus
except ImportError:
    def compute_seal_bonus(title, content=""): return 0.0

WORKSPACE = Path(os.environ.get("QCLAW_WORKSPACE", r"C:\Users\qq366410837\.qclaw\workspace"))
MEMORY_MD = WORKSPACE / "MEMORY.md"
USER_MD   = WORKSPACE / "USER.md"
ARCHIVE_DIR = WORKSPACE / "memory" / "archive"

# 代谢等级
GC_LIGHT = "light"   # 对话结束触发，仅标记
GC_DEEP  = "deep"    # 深睡期触发，执行压缩/迁移
GC_EMERG = "emerg"   # Token 告警触发，强制淘汰

# 阈值（秒）
ACCESS_TIMEOUT_NS = 30 * 24 * 3600   # 30天未访问 → 候选淘汰
ACCESS_TIMEOUT_S  = 7  * 24 * 3600   # 7天未访问  → 候选降级


class MemoryGC:
    def __init__(self, workspace: Optional[Path] = None):
        self.workspace = workspace or WORKSPACE
        self.now = time.time()

    # ------------------------------------------------------------------ #
    #  保护列表
    # ------------------------------------------------------------------ #
    def _load_protected_sections(self) -> set:
        """加载学习产物保护的段落标题列表"""
        protected_path = WORKSPACE / "memory" / "_learning_protected.json"
        if not protected_path.exists():
            return set()
        try:
            data = json.loads(protected_path.read_text(encoding="utf-8"))
            return set(data.get("sections", []))
        except (json.JSONDecodeError, OSError):
            return set()

    # ------------------------------------------------------------------ #
    #  公共工具
    # ------------------------------------------------------------------ #
    def _read_file(self, path: Path) -> str:
        if not path.exists():
            return ""
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _write_file(self, path: Path, content: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _extract_keywords(self, text: str) -> Set[str]:
        """提取关键词（去停用词）"""
        stops = {"的", "了", "是", "在", "有", "和", "就", "不", "人", "都",
                 "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你",
                 "会", "着", "没有", "看", "好", "自己", "这"}
        words = set()
        # 中文字符
        for ch in text:
            if '\u4e00' <= ch <= '\u9fff':
                words.add(ch)
        # 英文 token
        for t in text.split():
            if len(t) > 1 and t not in stops and not t.isdigit():
                words.add(t[:4])
        return words

    # ------------------------------------------------------------------ #
    #  代谢分析：扫描 MEMORY.md，给每段打代谢分
    # ------------------------------------------------------------------ #
    def analyze_memory(self, context_keywords: Optional[Set[str]] = None) -> list[dict]:
        """
        解析 MEMORY.md，逐段计算代谢指标。
        
        改进 v2：
          - 如果传入 context_keywords，自动刷新匹配段落的 last_accessed
          - 返回结果按 score 升序（最该淘汰的在最前）
        """
        content = self._read_file(MEMORY_MD)
        if not content:
            return []

        sections = self._split_sections(content)
        results = []

        for sec in sections:
            meta = self._extract_meta(sec)
            
            # 改进 v2：根据上下文自动刷新 last_accessed
            if context_keywords:
                sec_keywords = self._extract_keywords(sec)
                if sec_keywords & context_keywords:  # 有交集
                    meta["last_accessed"] = self.now
                    # 写回 meta 标签
                    self._write_meta(sec, last_accessed=self.now)

            age = self.now - meta["last_accessed"]
            age_unknown = meta.get("age_unknown", False)
            score = self._metabolic_score(
                age=age,
                access_count=meta["access_count"],
                token_est=meta["token_est"],
                has_seal=meta["has_seal"],
            )

            # T2→T4: 钢印关键词加权（在推荐动作之前）
            section_title = meta["title"][:60]
            seal_bonus = compute_seal_bonus(section_title, sec)
            if seal_bonus > 0:
                score = score + seal_bonus

            action = self._recommend_action(score, age, age_unknown=age_unknown)

            # P0: 学习产物保护（已废弃空壳，仅兜底兼容）
            protected = self._load_protected_sections()
            if section_title in protected:
                action = "KEEP"

            # 加固1（PROMOTE 设计 §8.5）：architecture_journal ACTIVE 为运行时强制权威源
            # GC 强制规则读 journal ACTIVE，不读 memory 副本。若段落标题命中某 ACTIVE 架构约束，
            # 强制 KEEP（journal 持有的决策在记忆区的派生条目不被淘汰；记忆区衰减不影响强制）。
            try:
                from architecture_journal import ArchitectureJournal
                aj = ArchitectureJournal()
                if section_title in aj.load_active_constraints():
                    action = "KEEP"
            except Exception:
                pass

            results.append({
                "section": section_title,
                "last_accessed": meta["last_accessed"],
                "access_count": meta["access_count"],
                "token_est": meta["token_est"],
                "score": round(score, 3),
                "action": action,
            })

        return sorted(results, key=lambda x: x["score"])

    # ------------------------------------------------------------------ #
    #  分段解析
    # ------------------------------------------------------------------ #
    def _split_sections(self, content: str) -> list[str]:
        """按 ## 标题 切分 MEMORY.md"""
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

    def _extract_meta(self, section: str) -> dict:
        """
        从段落提取元数据。修复 (2026-08-19)：age/access 真实化。

        旧逻辑：last_accessed 对所有段 fallback 到 MEMORY.md 整个文件 mtime
        → 刚 distill 后所有段 age≈0 → 频率地板把 179 段全推入 DEGRADE（退化）。
        access_count 纯靠关键词密度硬算，无真实访问计数。

        新逻辑（用真实可得信号，不臆造）：
          last_accessed 优先级：
            1) 段内 <!-- meta: last_accessed=epoch -->（distill 写入的真实时间戳）
            2) 段标题/首行 YYYY-MM-DD 日期（真实提炼日，age 真实）
            3) 都不在 → age_unknown=True（保护，交 _recommend_action 走 WATCH，不盲降）
          access_count：meta 标签 count > 信息密度估算(保底) > 1
        """
        import re
        title = section.split("\n", 1)[0][:60]
        last_accessed = None
        age_unknown = False
        info_keywords = ["钢印", "核心", "架构", "洞见", "⅋", "SEAL", "SOUL"]
        info_density = sum(kw in section for kw in info_keywords)
        access_count = max(1, info_density * 3)  # 每个关键词加3分，保底1
        token_est = len(section) // 2   # 粗略：2字符≈1 token
        has_seal = "钢印" in section or "⅋" in section

        # 1) 段内 meta 标签（最权威，distill 写入的真实时间戳 + count）
        if "<!-- meta:" in section:
            try:
                meta_str = section.split("<!-- meta:", 1)[1].split("-->", 1)[0]
                for pair in meta_str.split(","):
                    k, v = pair.strip().split("=", 1)
                    if k.strip() == "last_accessed":
                        last_accessed = float(v.strip())
                    elif k.strip() == "count":
                        access_count = int(v.strip())
            except Exception:
                pass

        # 2) 无 meta 标签 → 用段标题/首行真实日期（YYYY-MM-DD）；找不到则 age_unknown
        if last_accessed is None:
            m = re.search(r"(\d{4})-(\d{2})-(\d{2})", section)
            if m:
                try:
                    y, mo, d = (int(x) for x in m.groups())
                    last_accessed = datetime(y, mo, d).timestamp()
                except Exception:
                    age_unknown = True
            else:
                age_unknown = True

        # 兜底：仍无有效信号（无 meta 标签、无标题/首行日期）→ 标记 age_unknown，
        # 交 _recommend_action 走 WATCH 保护，绝不 fallback 文件 mtime（会让 legacy 段 age 虚高→误判 EVICT）。
        # 修复 (2026-08-27)：08-19 修复遗漏——文件 mtime fallback 使无日期段 age 巨大，
        # 绕过 age_unknown 保护被误判 EVICT（虽 _evict_section 是 no-op 零破坏，但属误标）。
        if last_accessed is None:
            age_unknown = True
            last_accessed = self.now  # 占位，age_unknown=True 后不用于阈值

        return {
            "title": title,
            "last_accessed": last_accessed,
            "age_unknown": age_unknown,
            "access_count": access_count,
            "token_est": token_est,
            "has_seal": has_seal,
        }

    def _get_file_mtime(self, path: Path) -> float:
        try:
            return path.stat().st_mtime
        except Exception:
            return self.now

    def _write_meta(self, section: str, **kwargs):
        """
        改进 v2：写回 meta 标签到 MEMORY.md。
        
        找到对应段落，更新或添加 <!-- meta: ... --> 标签。
        kwargs: last_accessed=float, count=int
        """
        content = self._read_file(MEMORY_MD)
        lines = content.splitlines(keepends=True)
        new_lines = []
        in_target = False
        meta_written = False
        target_title = section.split("\n", 1)[0][:60]

        for i, line in enumerate(lines):
            # 检测是否进入目标段落
            if line.startswith("## ") and target_title in line:
                in_target = True
            elif line.startswith("## ") and in_target:
                # 上一个段落结束，检查是否需要追加 meta
                if not meta_written:
                    new_meta = "<!-- meta: last_accessed=%.0f" % kwargs.get("last_accessed", self.now)
                    if "count" in kwargs:
                        new_meta += ", count=%d" % kwargs["count"]
                    new_meta += " -->"
                    new_lines.append(new_meta + "\n")
                    meta_written = True
                in_target = False

            # 替换现有 meta 标签
            if "<!-- meta:" in line and in_target:
                new_meta = "<!-- meta: last_accessed=%.0f" % kwargs.get("last_accessed", self.now)
                if "count" in kwargs:
                    new_meta += ", count=%d" % kwargs["count"]
                new_meta += " -->"
                new_lines.append(new_meta + "\n")
                meta_written = True
                continue  # 跳过原 meta 行

            new_lines.append(line)

        # 文件末尾的段落（没有下一个 ## 标题）
        if in_target and not meta_written:
            new_meta = "<!-- meta: last_accessed=%.0f" % kwargs.get("last_accessed", self.now)
            if "count" in kwargs:
                new_meta += ", count=%d" % kwargs["count"]
            new_meta += " -->"
            new_lines.append(new_meta + "\n")

        self._write_file(MEMORY_MD, "".join(new_lines))

    # ------------------------------------------------------------------ #
    #  代谢分计算（改进 v2）
    # ------------------------------------------------------------------ #
    def _metabolic_score(self, age: float, access_count: int,
                           token_est: int, has_seal: bool) -> float:
        """
        代谢分：越高 = 越值得保留（参考大自然「用进废退」）
        
        改进 v2：
          - access_count 加入90天时间折扣（防止历史高频垄断）
          - effective_count = access_count * exp(-age / decay_half_life)
        """
        # 时间折扣因子（90天半衰）
        decay_half_life = 90 * 24 * 3600
        effective_count = access_count * (2.718 ** (-age / decay_half_life))

        # 代谢分计算
        half_life = 30 * 24 * 3600  # 30天半衰
        recency = 2.718 ** (-age / half_life)
        frequency = (effective_count + 1) ** 0.3  # 用 effective_count 替代 access_count
        cost_penalty = 0.001 * token_est

        score = recency * frequency - cost_penalty

        if has_seal:
            score += 2.0  # 钢印记忆保底

        return max(score, 0.0)

    def _recommend_action(self, score: float, age: float,
                           age_unknown: bool = False) -> str:
        """根据代谢分推荐动作。修复：保护未知年龄/新鲜内容。
        - age_unknown=True（无 meta 也无日期的 legacy 段）：走 WATCH，不盲降/淘汰
        - age < 7天（刚 distill/访问的新鲜内容）：KEEP，不该立刻归档
        """
        if age_unknown:
            return "WATCH"
        if age < 7 * 24 * 3600:
            return "KEEP"
        if score > 1.5:
            return "KEEP"       # 保留，可能升级
        elif score > 0.3:
            return "DEGRADE"   # 降级（阈值从0.5降至0.3，减少误判）
        elif age > ACCESS_TIMEOUT_NS:
            return "EVICT"      # 淘汰（移到 /dev/null）
        else:
            return "WATCH"

    # ------------------------------------------------------------------ #
    #  执行回收
    # ------------------------------------------------------------------ #
    def run_gc(self, mode: str = GC_DEEP, context_keywords: Optional[Set[str]] = None) -> dict:
        """
        执行垃圾回收，返回报告。

        改进 v2：传入 context_keywords 以触发自动刷新。
        PROMOTE §8.5 加固2：GC 启动时自动 review architecture_journal 状态转移
        （ACTIVE→SUPERSEDED/STABLE，防变垃圾场），并标记 _learning_protected.json 废弃。
        """
        # 加固2 + §4.1：GC 逻辑修改后自动维护 journal 状态机 + 清理手写后门
        try:
            from architecture_journal import ArchitectureJournal
            aj = ArchitectureJournal()
            trans = aj.review_transitions(dry_run=(mode == GC_LIGHT))
            if trans["superseded"] or trans["stabilized"]:
                print(f"[GC] journal transition: SUPERSEDED={trans['superseded']} STABLE={trans['stabilized']}")
            aj.deprecate_learning_protected()
        except Exception:
            pass

        analysis = self.analyze_memory(context_keywords=context_keywords)
        report = {
            "mode": mode,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_sections": len(analysis),
            "actions": {"KEEP": 0, "DEGRADE": 0, "EVICT": 0, "WATCH": 0},
            "details": [],
        }

        for item in analysis:
            action = item["action"]
            report["actions"][action] += 1
            report["details"].append({
                "section": item["section"],
                "score": item["score"],
                "action": action,
            })

            if mode == GC_DEEP:
                if action in ("DEGRADE", "EVICT"):
                    # 元认知监督（PROMOTE §3）：自述与动作同事务原子写。
                    # 自述失败 → 动作回滚 no-op（反思不可后置补写）。
                    reason = (
                        f"score={item['score']:.3f} 低于保留阈值"
                        f"{'；含钢印保底仍被判' if '钢印' in item['section'] else ''}"
                    )
                    evidence = f"access_count={item.get('access_count','?')}，无显式引用事件"
                    narrated = False
                    try:
                        from gc_decisions import append_decision
                        narrated = append_decision(
                            action=action,
                            section=item["section"],
                            reason=reason,
                            evidence=evidence,
                        )
                    except Exception:
                        narrated = False
                    if not narrated:
                        # 回滚：保持 no-op 安全态，不执行实际移动/删除
                        report["details"][-1]["action"] = "WATCH"
                        report["actions"][action] -= 1
                        report["actions"]["WATCH"] += 1
                        continue
                if action == "DEGRADE":
                    self._archive_section(item["section"])
                elif action == "EVICT":
                    self._evict_section(item["section"])

        # T4→T5: GC 反馈到学习链
        try:
            record_gc_result(report)
        except Exception:
            pass

        # T4→T3: GC 完成后通知调度器
        try:
            from t3_middleware import on_gc_completed
            on_gc_completed(report)
        except Exception:
            pass

        return report

    def _archive_section(self, section_title: str):
        """将段落从 MEMORY.md 移除，写入 archive/{date}_{title}.md"""
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        # 清洗 Windows 非法文件名字符： < > : " / \ | ? * 以及 #
        _illegal = '<>:"/\\|?*#'
        safe_title = section_title[:30]
        for ch in _illegal:
            safe_title = safe_title.replace(ch, '_')
        safe_title = safe_title.replace(' ', '_').strip('.')
        archive_path = ARCHIVE_DIR / f"{datetime.now().strftime('%Y-%m-%d')}_{safe_title}.md"
        
        content = self._read_file(MEMORY_MD)
        lines = content.splitlines(keepends=True)
        new_lines = []
        archived_section = []
        in_target = False
        found = False
        
        for line in lines:
            if line.startswith("## ") and section_title in line:
                in_target = True
                found = True
                archived_section = [line]
            elif line.startswith("## ") and in_target:
                in_target = False
                new_lines.append(line)  # 不吞掉下一段的标题
            elif in_target:
                archived_section.append(line)
            else:
                new_lines.append(line)
        
        if found:
            self._write_file(archive_path, "".join(archived_section))
            self._write_file(MEMORY_MD, "".join(new_lines))
            print(f"[GC] ARCHIVE: {section_title} -> archive/{safe_title}.md  (moved)")
        else:
            print(f"[GC] ARCHIVE: {section_title} -> not found, skip")

    def _evict_section(self, section_title: str):
        """彻底淘汰（写入 /dev/null 即不保留）"""
        print(f"[GC] EVICT: {section_title}")

    def _load_scores(self) -> dict:
        """B 类 S 信号接口：返回 {citation_id: score} 派生映射。

        GC 本身不直接存 citation_id→score 的轻量索引，此处从 analyze_memory 的
        评分结果中提取（若存在），否则返回空 dict（promote_channel 容错处理）。
        演进：未来接 memory_gc 评分持久化后真实返回。
        """
        try:
            report = self.analyze_memory(mode="light")
            scores = {}
            for sec in report.get("sections", []):
                cid = sec.get("citation_id")
                sc = sec.get("score")
                if cid and sc is not None:
                    scores[cid] = sc
            return scores
        except Exception:
            return {}

    # ------------------------------------------------------------------ #
    #  状态查询
    # ------------------------------------------------------------------ #
    def token_budget_status(self) -> dict:
        """估算当前记忆系统 Token 开销"""
        memory_content = self._read_file(MEMORY_MD)
        user_content   = self._read_file(USER_MD)
        return {
            "MEMORY.md_tokens": len(memory_content) // 2,
            "USER.md_tokens":   len(user_content)   // 2,
            "total_est_tokens":  len(memory_content) // 2 + len(user_content) // 2,
        }


if __name__ == "__main__":
    gc = MemoryGC()
    print("=== Token Budget ===")
    print(json.dumps(gc.token_budget_status(), indent=2, ensure_ascii=False))
    print()
    print("=== 代谢分析（全量）===")
    analysis = gc.analyze_memory()
    for item in analysis:
        action = item['action']
        score  = item['score']
        title  = item['section']
        count  = item['access_count']
        print("  [%s] %-40s score=%.3f  count=%d" % (action, title[:40], score, count))
