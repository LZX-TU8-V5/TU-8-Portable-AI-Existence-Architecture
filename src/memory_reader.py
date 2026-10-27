"""
memory_reader.py — 读时投影引擎 [H级结构优化·读取侧]

职责：替代 Gateway 全量加载 MEMORY.md（约 120KB），按任务查询投影召回相关段。
设计：read_for_task(query) -> 切段 -> 每段与查询算连续余弦相似度 -> 召回 top_k 相关段。

关键修正（2026-08-29 夜）：
- 原探针版 ranking 只比较 sem 轴粗标签（二值 1.0），丢弃查询↔段向量相似度，
  导致所有查询都返回文档顺序前 8 段（与查询无关，等于失效）。
- 改用「查询-段连续余弦」做主排序信号（真正的读时投影）。
- 共享 TFIDFEmbedder 对中文的 tokenize 把单字中文全滤掉（len>1 过滤），
  致中文向量近正交（中位余弦 0.0）。本引擎内嵌 CJK-aware 向量器，自洽、零 blast radius。
- 另接 memory_layer_index.json：L0 系统锚点轻微加权（系统锚点优先召回，符合设计意图）。

降级：coord 落空段用余弦兜底（已无 75% 落空问题，因本引擎自带中文 tokenize）。

注：当前为探针版，不接 Gateway 加载（SOUL/AGENTS 核心文件清单改造属 H 级，待引擎验证后签）。
"""
import os
import re
import hashlib
import math
from pathlib import Path
from typing import Optional

WORKSPACE = Path(os.environ.get("QCLAW_WORKSPACE", r"C:\Users\qq366410837\.qclaw\workspace"))
MEMORY = WORKSPACE / "MEMORY.md"
SHORT_TERM = WORKSPACE / "memory" / "short"  # TU8MemoryEngine.short_term 目录
LAYER_INDEX = WORKSPACE / "_agent_memory" / "memory_layer_index.json"
EMBED_DIM = 256  # 本地向量维度：高于共享 128，缓解中文哈希稀疏

_ASCII_RE = re.compile(r"[a-z0-9_]+")
_CJK_LO, _CJK_HI = ord("\u4e00"), ord("\u9fff")


def _cjk_tokenize(text: str) -> list[str]:
    """ASCII 走空白/词边界；CJK 走 单字 + 2gram（解决共享 embedder 单字被 len>1 滤掉）。"""
    text = text.lower()
    tokens: list[str] = _ASCII_RE.findall(text)
    cjk = [c for c in text if _CJK_LO <= ord(c) <= _CJK_HI]
    if cjk:
        tokens.extend(cjk)  # 单字 unigram，保留语义原子
        for i in range(len(cjk) - 1):
            tokens.append(cjk[i] + cjk[i + 1])  # 2gram 抗分词缺失
    return tokens


def _vectorize(text: str, dim: int = EMBED_DIM) -> list[float]:
    """轻量哈希 TF 向量（L2 归一），与共享 embedder 同构但带 CJK 感知。"""
    toks = _cjk_tokenize(text)
    vec = [0.0] * dim
    for t in toks:
        h = int(hashlib.md5(t.encode("utf-8")).hexdigest(), 16) % dim
        vec[h] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def _cos(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def _load_working_window(n: int = 10) -> str:
    """坑一修复：读短期记忆滑动窗口（最近 n 条 short_term 文件），作 WorkingMemory。"""
    if not SHORT_TERM.exists():
        return ""
    files = sorted(SHORT_TERM.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:n]
    chunks = []
    for f in files:
        body = f.read_text(encoding="utf-8", errors="ignore").strip()
        if body:
            chunks.append(f"# [短期记忆] {f.stem}\n{body[:800]}")
    return "\n\n".join(chunks)


def _load_layer_index() -> dict:
    if not LAYER_INDEX.exists():
        return {}
    try:
        import json
        return json.loads(LAYER_INDEX.read_text(encoding="utf-8"))
    except Exception:
        return {}


class MemoryReader:
    def __init__(self):
        # TopicMatrix 仍用于 coord/layer 辅助信息；主排序用本引擎余弦，避免共享 embedder 中文缺陷。
        try:
            from topic_matrix import TopicMatrix
            self.tm = TopicMatrix()
            self._have_tm = True
        except Exception:
            self.tm = None
            self._have_tm = False
        self._layer_idx = _load_layer_index()

    def _split_sections(self, text: str) -> list[tuple[str, str]]:
        """按 ## 切段，返回 [(title, body)]。"""
        lines = text.splitlines()
        heads = [i for i, l in enumerate(lines, 1) if l.startswith("## ")]
        out = []
        for idx, h in enumerate(heads):
            title = lines[h - 1]
            end = heads[idx + 1] - 1 if idx + 1 < len(heads) else len(lines)
            body = "\n".join(lines[h:end])
            out.append((title, body))
        return out

    def _section_layer(self, title: str) -> Optional[str]:
        """从外置索引查该段 layer（L0/L1/L2），用于 L0 轻微加权。"""
        if not self._layer_idx:
            return None
        order = self._layer_idx.get("order") or []
        for rec in order:
            if rec.get("title") == title.strip():
                return rec.get("layer")
        return None

    def _scored_sections(self, query: str, top_k: int = 8, tau: float = 0.0) -> tuple[str, list[tuple[float, str]]]:
        """核心：返回 (投影文本, [(score, title)...])，title 取自切段时真实标题。"""
        if not MEMORY.exists():
            return "", []
        text = MEMORY.read_text(encoding="utf-8", errors="ignore")
        sections = self._split_sections(text)
        if not sections:
            return text, []

        q_vec = _vectorize(query)
        q_tokens = set(_ASCII_RE.findall(query.lower()))

        scored: list[tuple[float, str]] = []
        for title, body in sections:
            s_vec = _vectorize(title + "\n" + body[:600])
            score = _cos(q_vec, s_vec)
            layer = self._section_layer(title)
            if layer == "L0":
                score *= 1.15
            if score <= 0 and q_tokens:
                s_tokens = set(_ASCII_RE.findall((title + body[:600]).lower()))
                if q_tokens & s_tokens:
                    score = 0.05
            scored.append((score, title.strip()))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = [(s, t) for s, t in scored[:top_k] if s > tau]
        # 按 title 映射回 body，拼回投影文本
        title_to_body = {t.strip(): b for t, b in sections}
        proj = "\n\n".join(f"{t}\n{title_to_body.get(t, '')[:1500]}" for s, t in top)

        wm = _load_working_window(10)
        if wm:
            proj = f"# [WorkingMemory 短期窗口]\n{wm}\n\n# [长期记忆投影]\n{proj}"
        return proj, top

    def read_for_task(self, query: str, top_k: int = 8, tau: float = 0.0,
                      working_window: int = 10) -> str:
        """读时投影召回：返回与 query 余弦相关的 top_k 段拼接文本。
        - 主信号：查询-段连续余弦（真正的读时投影）
        - L0 系统锚点轻微加权（×1.15）
        - 降级：余弦全 0 时回退到关键词重叠（ASCII 词边界）
        """
        proj, _ = self._scored_sections(query, top_k=top_k, tau=tau)
        return proj

    def estimate_compression(self, query: str, top_k: int = 8) -> dict:
        """返回投影后字符数 vs 全文，验证降维。召回段数 = 实际命中的 ## 段数。"""
        full = MEMORY.read_text(encoding="utf-8", errors="ignore")
        proj, top = self._scored_sections(query, top_k=top_k)
        return {
            "full_chars": len(full),
            "projected_chars": len(proj),
            "ratio": round(len(proj) / len(full), 3) if full else 0,
            "sections_recalled": len(top),
        }

    def validate(self, queries: Optional[list[str]] = None) -> dict:
        """§1.4 step5/6 验收：投影召回，确认查询相关且去重降维。"""
        if queries is None:
            queries = ["钢印冲突怎么处理", "代谢通道优化", "千问对话关于架构", "七七两岁成长小说"]
        report = {}
        for q in queries:
            est = self.estimate_compression(q)
            _, top = self._scored_sections(q)
            report[q] = {
                "full_chars": est["full_chars"],
                "projected_chars": est["projected_chars"],
                "ratio": est["ratio"],
                "recalled": est["sections_recalled"],
                "top_titles": [t[:40] for _, t in top[:6]],
            }
        return report


if __name__ == "__main__":
    mr = MemoryReader()
    rep = mr.validate()
    for q, r in rep.items():
        print(f"\n查询「{q}」")
        print(f"  全文 {r['full_chars']}B -> 投影 {r['projected_chars']}B (比 {r['ratio']}, 召回 {r['recalled']} 段)")
        for t in r["top_titles"][:6]:
            print(f"    - {t}")
