"""
metabolic_pipeline.py — TU-8 自动代谢管道

模拟大自然「用进废退」的完整代谢周期：
  1. 提炼：将日记文件（memory/YYYY-MM-DD.md）精华迁移到 MEMORY.md
  2. 回收：运行 memory_gc.py，根据代谢分淘汰/降级记忆
  3. 归档：将已提炼的日记移入 archive/，释放 workspace

触发时机：
  - 每日深睡期（dream_check 后）
  - Token 预算告警时（> 60000 tokens）
  - 手动触发
"""

import os
import re
import json
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

WORKSPACE = Path(os.environ.get("QCLAW_WORKSPACE", r"C:\Users\qq366410837\.qclaw\workspace"))
MEMORY_MD  = WORKSPACE / "MEMORY.md"
ARCHIVE_DIR = WORKSPACE / "memory" / "archive"
PIPELINE_LOG = WORKSPACE / "memory" / "metabolic_pipeline_log.jsonl"


class MetabolicPipeline:
    # 批次3 密文库：已知高频繁体词典（压 sym_* 短码用）
    # 演进：未来由 topic_semantic_matrix v1.3 L2.5 grounding_refs 行为性浮现，不写死
    _KNOWN_ENTITIES = ["苹果", "TU-8", "七七", "李奥", "钢印", "千问", "牛顿", "PROMOTE"]

    def __init__(self, workspace: Optional[Path] = None):
        self.workspace = workspace or WORKSPACE
        self.now = time.time()

    # ------------------------------------------------------------------ #
    #  Stage 1: 提炼（Distillation）
    # ------------------------------------------------------------------ #
    def distill(self, dry_run: bool = False) -> dict:
        """
        将 memory/YYYY-MM-DD.md 中的精华段落迁移到 MEMORY.md。
        
        策略：
        - 扫描所有日记文件
        - 提取包含「钢印」「核心洞见」「架构升级」「## 总结」的段落
        - 按时间倒序追加到 MEMORY.md（避免重复）
        """
        report = {"stage": "distill", "files_scanned": 0, "sections_extracted": 0, "dry_run": dry_run}

        # 动态匹配所有「YYYY-MM-DD」日期日记，排除 MEMORY.md 与 archive 子目录
        diary_files = sorted(
            p for p in self.workspace.glob("memory/*.md")
            if re.match(r"\d{4}-\d{2}-\d{2}", p.stem)
            and p.name != "MEMORY.md"
            and "archive" not in str(p)
        )
        existing_memory = self._read_file(MEMORY_MD)

        # 上游水源：architecture_journal 的 ACTIVE 架构决策（PROMOTE 设计稿 §8.6）
        # journal 是水源，记忆区是河道；journal ACTIVE 断言经 distill 提取进 MEMORY.md 正常代谢
        new_sections = []
        new_sections.extend(self._journal_active_sections())

        new_sections_raw = []
        for f in diary_files:
            if f.name == "MEMORY.md" or "archive" in str(f):
                continue
            content = self._read_file(f)
            sections = self._extract_key_sections(content, f.stem)
            new_sections_raw.extend(sections)
            report["files_scanned"] += 1

        # journal 来源已带 content 结构；日记来源需包装为统一 dict
        for sec in new_sections_raw:
            new_sections.append(sec)

        # B 类遥测埋点（H 级，2026-08-28）：为每段补充行为性遥测字段
        # 向后兼容：旧段无字段时 get(key, default) 兜底，不破坏已落地 MEMORY.md 178 段
        new_sections = self._enrich_telemetry(new_sections, existing_memory)

        # 去重：以「内容指纹」为主键，标题不再单独作为跳过依据。
        # 修复 (2026-08-19)：旧逻辑用「标题命中即跳过整段」，导致 08-12 日记提取段首行
        # 为 H1「# 2026-08-12 日志」，而 MEMORY.md 心跳已收同名异内容条目 → 整段被误杀，
        # 真架构洞察「欧拉连续 vs 流水线离散采样」跟着丢失。改为：仅当段内 >=2 句代表句
        # 同时已在 MEMORY.md 时才判重复（标题同名但内容不同 → 不误杀）。
        existing_lower = existing_memory.lower()

        # 机械复盘/审计摘要指纹（HEARTBEAT 协议已处理的纯遥测，勿二次追加）
        _MECH_SIGNS = ("覆盖率", "钢印链条共", "生命年轮处于", "待办", "叙事")
        # 纯机械块标题（文件清单式复盘，无真洞察）
        _MECH_TITLES = ("下午复盘", "23个归档文件", "时间线")

        def _rep_sentences(sec_text: str) -> list:
            """取段内显著句（非标题、非注释、长度>=12 的中文行）作为内容指纹"""
            out = []
            for l in sec_text.splitlines():
                s = l.strip()
                if not s or s.startswith("#") or s.startswith("<!--"):
                    continue
                if len(s) < 12:
                    continue
                out.append(s)
            return out

        deduped = []
        for sec in new_sections:
            sec_content = sec["content"]
            sec_title = sec_content.split("\n", 1)[0].strip()
            reps = _rep_sentences(sec_content)
            # 1) 内容指纹去重：>=2 句代表句已同时存在于 MEMORY.md → 视为重复整段
            hits = sum(1 for r in reps if r.lower() in existing_lower)
            if reps and hits >= 2:
                continue
            # 2) 机械复盘摘要段（覆盖率/钢印链条/生命年轮/待办/叙事）跳过，不限标题级
            if any(s in sec_content for s in _MECH_SIGNS):
                continue
            # 2b) 纯机械清单块（下午复盘/归档文件清单/时间线）跳过
            if any(s in sec_title for s in _MECH_TITLES):
                continue
            deduped.append(sec)

        report["sections_extracted"] = len(deduped)

        if not dry_run and deduped:
            with open(MEMORY_MD, "a", encoding="utf-8") as f:
                for sec in deduped:
                    f.write(f"\n\n<!-- meta: last_accessed={self.now}, count=1 -->\n")
                    f.write(sec["content"])
                    f.write("\n")

        return report

    def _journal_active_sections(self) -> list[dict]:
        """从 workspace/architecture_journal 读取 ACTIVE 条目，转为与日记同源的 section 结构。

        加固1：journal ACTIVE = 运行时强制权威源；此处只做 distill 上游提取，
        不干预 GC 强制逻辑（GC 直接读 journal，见 memory_gc）。
        """
        try:
            from architecture_journal import ArchitectureJournal
            aj = ArchitectureJournal(self.workspace)
            out = []
            for a in aj.get_active_assertions():
                # 每条断言包成 ## 块，标题=决策标题，正文=断言；进入内容指纹去重
                block = f"## {a['title']}\n- 架构决策断言：{a['assertion']}\n"
                out.append({"source": "architecture_journal", "content": block})
            return out
        except Exception:
            return []

    def _extract_key_sections(self, content: str, source: str) -> list[dict]:
        """从日记内容中提取关键段落（按 ## 标题切块，避免整文件塌缩）

        修复 (2026-08-19)：旧逻辑只在出现关键词时开 in_key_section，且在一整文件内
        仅遇 ## 才重置 → 开头关键词命中后整文件被并成一个以 H1 开头的巨型块，
        去重只看 H1 标题 → 与 MEMORY 同名异内容条目冲突 → 整段（含真洞察）被误杀。
        新逻辑：每个 ## 二级标题独立成块；块是否「关键」由 (a) 标题含结论性信号词 或
        (b) 块内含洞察关键词 决定。H1 前言无关键词则不收，避免巨型块。
        """
        keywords = ["钢印", "核心洞见", "架构升级", "## 总结", "核心结论",
                    "💡", "矛盾", "结论", "洞察", "洞见", "机制", "公式", "收敛"]
        section_signals = ("矛盾", "结论", "架构", "洞察", "洞见", "升级",
                          "机制", "公式", "收敛", "总结", "核心")

        def _qualify(title_line: str, body_lines: list) -> bool:
            if any(s in title_line for s in section_signals):
                return True
            return any(kw in ln for ln in body_lines for kw in keywords)

        sections = []
        lines = content.splitlines(keepends=True)
        cur = []
        qualify = False

        def _flush(buf: list, ok: bool):
            if buf and ok:
                # B 类：统一 dict，content + source + citation_id（稳定复用，允许多快照）
                sections.append({
                    "source": source,
                    "content": "".join(buf),
                    "citation_id": str(uuid.uuid4())[:12],
                })

        for line in lines:
            if line.startswith("## "):
                _flush(cur, qualify)
                cur = [line]
                qualify = any(s in line for s in section_signals)
            else:
                cur.append(line)
                if any(kw in line for kw in keywords):
                    qualify = True
        _flush(cur, qualify)
        return sections

    def _enrich_telemetry(self, sections: list[dict], existing_memory: str) -> list[dict]:
        """B 类遥测埋点：为每段补充 topic_tag / citation_id / linkage_map + R/S/C 派生。

        信号来源（禁写死，L0 涌现铁律）：
          R (ref_events): 全文扫描统计该段代表句在其他日记/涌现时刻中被引用次数
          S (survival):   读 memory_gc 评分派生（抗 DEGRADE 能力），无则 None
          C (coverage):    语义矩阵跨域覆盖（暂 fall back 到日期窗口 ≥7 天，待 v1.3 投影就位）
        向后兼容：旧段缺字段用 get(key, default) 兜底；fallback 不破坏已落地内容。
        """
        import re as _re
        # 预计算：所有日记/涌现时刻正文（用于 R 信号扫描）
        corpus = []
        for p in self.workspace.glob("memory/*.md"):
            if "archive" in str(p) or p.name == "MEMORY.md":
                continue
            corpus.append(self._read_file(p))
        corpus_text = "\n".join(corpus)

        # S 信号：读取最新 GC 评分（若存在）
        try:
            from memory_gc import MemoryGC
            gc_scores = MemoryGC(self.workspace)._load_scores() if hasattr(MemoryGC, "_load_scores") else {}
        except Exception:
            gc_scores = {}

        enriched = []
        for sec in sections:
            content = sec.get("content", "")
            # R: 代表句跨情景命中计数
            reps = [l.strip() for l in content.splitlines()
                    if len(l.strip()) >= 12 and not l.startswith("#") and not l.startswith("<!--")]
            ref_count = 0
            for r in reps:
                if r.lower() in corpus_text.lower():
                    ref_count += 1
            # topic_tag: 暂由语义矩阵投影推导（未就位时空 list，不写死）
            topic_tag = self._project_topic(content)
            # C: 覆盖域（fallback 到日期窗口 ≥7 天判定不同情景）
            cov = self._coverage_domains(sec, topic_tag)
            enriched_sec = dict(sec)
            # coord: L1 语义矩阵投影 (sem/ctx/act 三维坐标)，落空返回 None
            coord = self._project_coord(content, sec.get("citation_id", ""))
            enriched_sec.update({
                "topic_tag": topic_tag,
                "ref_events": ref_count,
                "survival_score": gc_scores.get(sec.get("citation_id"), None),
                "coverage_domains": cov,
                "linkage_map": self._build_linkage(sec, existing_memory),
                "entity_syms": self._compress_entities(content),
                "coord": coord,
            })
            enriched.append(enriched_sec)
        return enriched

    def _compress_entities(self, content: str) -> list:
        """批次3 密文库接线：提取高频实体压 sym_* 短码。
        范围（§12 决策）：仅注册表（不含 entity_resolver）。
        实体词典 = TU-8 已知高频繁体（苹果/TU-8/七七/李奥/钢印等），
        演进：未来由 topic_semantic_matrix v1.3 L2.5 grounding_refs 自动浮现，不写死。
        """
        try:
            from codebook import Codebook
            cb = Codebook()
            syms = []
            for ent in self._KNOWN_ENTITIES:
                if ent in content:
                    syms.append(cb.register(ent, f"distill_{abs(hash(content))%100000}"))
            return syms
        except Exception:
            return []

    def _project_coord(self, content: str, event_id: str = "") -> Optional[dict]:
        """L1 语义矩阵投影：content -> {sem, ctx, act} 三维坐标。
        接 topic_matrix.classify_event（v1.3 L1 三正交轴投影判区）。
        落空（低于 τ 或无语义）返回 None，不写死。
        """
        try:
            from topic_matrix import TopicMatrix
            tm = TopicMatrix()
            r = tm.classify_event(content, event_id or f"distill_{abs(hash(content))%100000}")
            return r.get("coord")
        except Exception:
            return None

    def _project_topic(self, content: str) -> list:
        """语义矩阵投影推导 topic_tag。未就位时返回 []（禁写死静态字典）。
        演进路线见 B 稿 §7.3：未来接 topic_semantic_matrix v1.3 L1 轴投影。"""
        # TODO（H 级后续）：接入 topic_semantic_matrix 向量投影
        return []

    def _coverage_domains(self, sec: dict, topic_tag: list) -> list:
        """跨域覆盖 C 信号。有 topic_tag 用其跨域分布；无则 fallback 日期窗口 ≥7 天。
        fallback 是 L0 涌现铁律的稳健性设计（禁手写白名单→临时占位）。"""
        if topic_tag:
            return topic_tag  # 演进后接矩阵跨域判定
        # fallback：按段日期窗口判定情景隔离
        src = sec.get("source", "")
        m = __import__("re").search(r"\d{4}-\d{2}-\d{2}", src)
        if m:
            return [f"date_window:{m.group(0)}"]
        return []

    def _build_linkage(self, sec: dict, existing_memory: str) -> dict:
        """linkage_map: parent→child 边，由 distill 扫描自动构建，禁手工编辑。
        当前实现：若段内容引用了 existing_memory 中某段标题，记为边（轻量版）。"""
        edges = {}
        cid = sec.get("citation_id", "")
        # 取段首标题作为 potential parent 锚
        first = sec.get("content", "").split("\n", 1)[0].strip()
        if first.startswith("## ") and first[3:] in existing_memory:
            edges[cid] = [first[3:]]
        return edges

    # ------------------------------------------------------------------ #
    #  Stage 2: 回收（Garbage Collection）
    # ------------------------------------------------------------------ #
    def gc(self, mode: str = "deep", dry_run: bool = False) -> dict:
        """运行 memory_gc.py 的回收逻辑"""
        try:
            from memory_gc import MemoryGC
            gc = MemoryGC(self.workspace)
            report = gc.run_gc(mode=mode)
            if dry_run:
                report["dry_run"] = True
            return report
        except Exception as e:
            return {"stage": "gc", "error": str(e)}

    # ------------------------------------------------------------------ #
    #  Stage 3: 归档（Archive）
    # ------------------------------------------------------------------ #
    def archive(self, days_old: int = 7, dry_run: bool = False) -> dict:
        """
        将 > N 天的日记文件移入 archive/。
        前提：该文件的内容已被提炼到 MEMORY.md。
        """
        report = {"stage": "archive", "files_moved": 0, "dry_run": dry_run}
        cutoff = self.now - (days_old * 24 * 3600)

        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

        # 动态匹配所有「YYYY-MM-DD」日期日记（原硬编码 2026-07 已失效）
        for f in sorted(
            p for p in self.workspace.glob("memory/*.md")
            if re.match(r"\d{4}-\d{2}-\d{2}", p.stem)
            and "archive" not in str(p)
            and p.name != "MEMORY.md"
        ):
            if "archive" in str(f) or f.name == "MEMORY.md":
                continue
            if f.stat().st_mtime < cutoff:
                if not dry_run:
                    shutil.move(str(f), str(ARCHIVE_DIR / f.name))
                report["files_moved"] += 1

        return report

    # ------------------------------------------------------------------ #
    #  完整管道运行
    # ------------------------------------------------------------------ #
    # ------------------------------------------------------------------ #
    #  Stage 1.5: 去重（Dedup）
    # ------------------------------------------------------------------ #
    def dedup(self, dry_run: bool = False) -> dict:
        """运行 memory_dedup.py 两级去重"""
        try:
            from memory_dedup import dedup_sections, dedup_content
            section_r = dedup_sections(dry_run=dry_run)
            content_r = dedup_content(dry_run=dry_run)
            return {
                "stage": "dedup",
                "section": section_r,
                "content": content_r,
            }
        except Exception as e:
            return {"stage": "dedup", "error": str(e)}

    def run(self, dry_run: bool = False) -> dict:
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dry_run": dry_run,
            "stages": {},
        }
        result["stages"]["distill"] = self.distill(dry_run=dry_run)
        result["stages"]["dedup"]  = self.dedup(dry_run=dry_run)
        result["stages"]["gc"]      = self.gc(dry_run=dry_run)
        result["stages"]["archive"] = self.archive(dry_run=dry_run)

        # 写日志
        self._log(result)
        return result

    def _read_file(self, path: Path) -> str:
        if not path.exists():
            return ""
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _log(self, result: dict):
        with open(PIPELINE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="预览，不实际写入")
    parser.add_argument("--stage", choices=["distill", "dedup", "gc", "archive", "all"], default="all")
    args = parser.parse_args()

    pipe = MetabolicPipeline()
    if args.stage == "all":
        result = pipe.run(dry_run=args.dry_run)
    else:
        result = {"stages": {}}
        if args.stage == "distill":
            result["stages"]["distill"] = pipe.distill(dry_run=args.dry_run)
        elif args.stage == "dedup":
            result["stages"]["dedup"] = pipe.dedup(dry_run=args.dry_run)
        elif args.stage == "gc":
            result["stages"]["gc"] = pipe.gc(dry_run=args.dry_run)
        elif args.stage == "archive":
            result["stages"]["archive"] = pipe.archive(dry_run=args.dry_run)

    print(json.dumps(result, indent=2, ensure_ascii=False))
