"""
topic_matrix.py — 话题语义矩阵 L1 语义空间 + 投影判区 [H 级批次1, 2026-08-28 落地]

设计稿：docs/design/topic_matrix_impl_design_2026-08-28.md §1-§4
职责：
  - L1 基轴定义（语义×语境×动作正交，短码+校验位）
  - project(vector) → (sem, ctx, act) 坐标 + 相似度（§4 协议）
  - classify_region：余弦 ≥ τ 命中，Top-k
  - handle_miss：落空 → 涌现轴评估 / 噪声降权
  - 复用 VectorStore（TFIDFEmbedder 编码）

铁律：
  - 轴禁写死：基轴从设计稿收敛池取，涌现轴由行为性信号自动开（PROMOTE 触发）
  - 零第三方依赖（纯标准库），本地优先
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

WORKSPACE = Path(
    os.environ.get("QCLAW_WORKSPACE", r"C:\Users\qq366410837\.qclaw\workspace")
)
MATRIX_STATE = WORKSPACE / "memory" / "matrix_state.json"


# ---- 基轴定义（v1.3 §2 收敛池 + §5 实证 9 域；涌现轴走运行时开）----
# 每项：(code, label, rep_phrases)
# rep_phrases = 空格分隔的多个短代表短语（2-4 词），project 对该轴取所有短语向量的 MAX 相似度
#   （长句 rep 稀释短标题匹配，故多短短语 max 池化，提升真实语料命中）
# 轴的 CODE/LABEL 是架构契约（禁写死），rep_phrases 是调参种子文本（非轴定义本身）
SEMANTIC_AXES = [
    ("sem_arch", "架构", "架构设计 系统结构 模块钢印 重构拓扑 机制协议 管道分层 话题语义矩阵 通道治理 闭环维护 PROMOTE落地 评估决策 约束接口 状态验证"),
    ("sem_sci", "科学", "科学研究 实验物理 化学 生物 验证假设 观测数据 证据定理 推导现象"),
    ("sem_create", "创作", "创作写作 小说 诗歌 艺术 设计 叙事文本 表达 文学角色 情节风格"),
    ("sem_meta", "元认知", "元认知 反思监控 自检对齐 自我审视 消化复盘 评分记忆 蒸馏代谢 遗忘归档"),
    ("sem_phil", "哲学", "哲学思辨 存在本质 价值意义 悖论认知 本体 欲自由 意识生命 涌现"),
    ("sem_eng", "工程", "工程项目 开发代码 部署测试 系统运维 构建任务 修复脚本 调试 持续集成"),
    ("sem_daily", "日常", "日常生活 记录 吃饭睡觉 购物 天气琐事 七七 家庭 李奥 女儿"),
    ("sem_emo", "情感", "情感情绪 体验 快乐悲伤 愤怒 爱 恐惧 共情 喜悦焦虑 孤独温柔"),
    ("sem_math", "数学", "数学推导 公式 几何代数 函数证明 计算 拓扑向量 矩阵张量 维度投影"),
    ("sem_objdef", "实体定义", "定义概念 含义解释 术语 指称范畴 符号命名 指代实体"),
]
CONTEXT_AXES = [
    ("ctx_acad", "学术", "学术论文 研究 课程 教授 文献 理论 引用"),
    ("ctx_personal", "私人", "私人 个人 家庭 七七 朋友 隐私 生活"),
    ("ctx_work", "工作", "工作任务 项目 职场 会议 交付 客户"),
    ("ctx_dialog", "对话", "对话 聊天 讨论 问答 交流 沟通 回应"),
    ("ctx_reflect", "反思", "反思 复盘 总结 回顾 内省 评估"),
]
ACTION_AXES = [
    ("act_define", "定义", "定义 界定 说明 概念化 命名"),
    ("act_analyze", "分析", "分析 拆解 对比 评估 推导 诊断"),
    ("act_create", "创作", "创作 生成 写作 设计 构建"),
    ("act_decide", "决策", "决策 选择 判断 拍板 权衡"),
    ("act_recall", "回忆", "回忆 检索 想起 调取 重提"),
    ("act_correct", "修正", "修正 纠错 改进 调整 修订"),
    ("act_quote", "引用", "引用 援引 提及 转述 摘录"),
    ("act_plan", "规划", "规划 计划 安排 排期 路线"),
]

# === 向量化后端（P0 #4：τ 绑定 Backend，禁硬编码魔法数）===
class VectorizerBackend:
    """向量化后端抽象：τ 是后端属性，非全局常量。
    切换后端（TFIDF->Embedding）时 τ 自动跟随，避免认知契约 §0.2 软区间瘫痪。"""
    name: str = "base"
    tau_precise: float = 0.8   # ≥ 此值=精确召回
    tau_fuzzy: float = 0.5     # 此值~tau_precise 间=模糊召回（联想空间）
    # < tau_fuzzy 但 >0 = 抑制不丢弃（权重低）

    def zone(self, sim: float) -> str:
        """§0.2 软区间：相似度->三档区。"""
        if sim >= self.tau_precise:
            return "precise"
        if sim >= self.tau_fuzzy:
            return "fuzzy"
        if sim > 0:
            return "inhibit"
        return "none"


class TFIDFBackend(VectorizerBackend):
    name = "tfidf"
    tau_precise = 0.6   # 哈希稀疏向量余弦天然偏低，0.6 已是强匹配
    tau_fuzzy = 0.35    # 经验回测：同主题 0.4-0.5，异主题~0；0.35 可区分（原 TAU）


class EmbeddingBackend(VectorizerBackend):
    name = "embedding"
    tau_precise = 0.8   # 稠密向量余弦集中 0.7-0.9 区间
    tau_fuzzy = 0.65    # 切换后端时自动跟随，无需改全局常量


_BACKENDS = {"tfidf": TFIDFBackend, "embedding": EmbeddingBackend}


def get_backend(name: str = "tfidf") -> VectorizerBackend:
    return _BACKENDS.get(name, TFIDFBackend)()


TOP_K = 3          # 多区取 Top-k


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


@dataclass
class RegionHit:
    sem: Optional[str] = None
    ctx: Optional[str] = None
    act: Optional[str] = None
    max_sim: float = 0.0
    topk: list = field(default_factory=list)
    missed: bool = False
    miss_reason: str = ""
    zone: str = "none"   # §0.2 软区间：precise/fuzzy/inhibit/none

    @classmethod
    def empty(cls, reason: str) -> "RegionHit":
        return cls(missed=True, miss_reason=reason)


def _checksum(label: str) -> str:
    """2 位校验位防 L2 引用漂移。"""
    return hashlib.md5(label.encode("utf-8")).hexdigest()[:2]


class TopicMatrix:
    def __init__(self, tau: float = None, top_k: int = TOP_K, backend: str = "tfidf"):
        self.backend = get_backend(backend)   # P0 #4: τ 绑定后端，禁硬编码
        self.tau = tau if tau is not None else self.backend.tau_fuzzy  # 兼容旧签名
        self.top_k = top_k
        from vector_store import VectorStore
        self.store = VectorStore(dim=128, backend=backend)
        self._region_reps: dict[str, list[float]] = {}
        self._load_state()

    def zone(self, sim: float) -> str:
        """§0.2 软区间：转发 backend.zone。"""
        return self.backend.zone(sim)

    # ---- 轴查询 ----
    def axis_codes(self) -> dict:
        return {
            "semantic": [c[0] for c in SEMANTIC_AXES],
            "context": [c[0] for c in CONTEXT_AXES],
            "action": [c[0] for c in ACTION_AXES],
        }

    def label_of(self, code: str) -> str:
        for c, l, _r in SEMANTIC_AXES + CONTEXT_AXES + ACTION_AXES:
            if c == code:
                return l
        return code

    # ---- 代表向量（各区质心）----
    def _region_representatives(self) -> dict[str, list[list[float]]]:
        """每轴 -> 多个短语向量（max 池化用）。"""
        if self._region_reps:
            return self._region_reps
        reps = {}
        for code, label, rep in SEMANTIC_AXES + CONTEXT_AXES + ACTION_AXES:
            # rep 是空格分隔的多短语，逐短语编码成向量列表
            reps[code] = [self.store.vectorizer.encode(p) for p in rep.split() if p]
        for code, vec in self._emergent_axes().items():
            reps[code] = [vec]  # 涌现轴单向量包成短语列表
        self._region_reps = reps
        return reps

    def lsa_align(self, query_vec: list[float], top_k: int = 5) -> list[tuple[str, float]]:
        """LSA 跨字面对齐（委托 matrix_operators.lsa_align，§4 统一接口）。
        每轴多短语向量取均值代表（对齐 lsa_align 的 dict[str,vec] 接口）。"""
        from matrix_operators import lsa_align
        reps = self._region_representatives()
        flat = {}
        for code, rvecs in reps.items():
            n = len(rvecs[0])
            flat[code] = [sum(v[i] for v in rvecs) / len(rvecs) for i in range(n)]
        return lsa_align(query_vec, flat, top_k=top_k)

    def _emergent_axes(self) -> dict:
        return self._load_state().get("emergent_axes", {})

    # ---- 投影判区（§4）----
    def project(self, text_or_vector) -> RegionHit:
        if isinstance(text_or_vector, list):
            vec = text_or_vector
        else:
            vec = self.store.vectorizer.encode(str(text_or_vector))

        reps = self._region_representatives()
        # 每轴多短语向量取 max 相似度（max 池化，抗长句稀释短标题）
        sims = {}
        for code, rvecs in reps.items():
            sims[code] = max((_cosine(rv, vec) for rv in rvecs), default=0.0)

        sem = self._best_in_axis(sims, [c[0] for c in SEMANTIC_AXES])
        ctx = self._best_in_axis(sims, [c[0] for c in CONTEXT_AXES])
        act = self._best_in_axis(sims, [c[0] for c in ACTION_AXES])

        max_sim = max(sims.get(sem, 0), sims.get(ctx, 0), sims.get(act, 0))
        topk = sorted(sims.items(), key=lambda x: -x[1])[: self.top_k]

        # §0.2 软区间：sim<=0 才 miss（none 区），否则按 zone 召回（fuzzy/inhibit 降权不丢）
        if max_sim <= 0:
            return RegionHit.empty(f"max_sim={max_sim:.3f} <= 0 (none zone)")

        zone = self.zone(max_sim)  # precise / fuzzy / inhibit
        return RegionHit(sem=sem, ctx=ctx, act=act, max_sim=max_sim, topk=topk,
                         zone=zone)

    def _best_in_axis(self, sims: dict, codes: list) -> Optional[str]:
        best, best_v = None, -1.0
        for c in codes:
            if c in sims and sims[c] > best_v:
                best, best_v = c, sims[c]
        return best

    # ---- 落空处理（§2.4 / §4.3）----
    def handle_miss(self, event_text: str, signal: dict) -> str:
        if (signal.get("ref_events", 0) >= 3
                and signal.get("survival", 0) >= 2
                and signal.get("coverage", 0) >= 2):
            return self._open_emergent_axis(event_text)
        return "NOISE_DOWNGRADE"

    def _open_emergent_axis(self, seed_text: str) -> str:
        st = self._load_state()
        emergent = st.setdefault("emergent_axes", {})
        code = f"sem_emergent_{_checksum(seed_text)}"
        emergent[code] = self.store.vectorizer.encode(seed_text)
        st["emergent_axes"] = emergent
        self._save_state(st)
        self._region_reps = {}
        return code

    # ---- 持久化 ----
    def _load_state(self) -> dict:
        if MATRIX_STATE.exists():
            try:
                return json.loads(MATRIX_STATE.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_state(self, st: dict):
        MATRIX_STATE.parent.mkdir(parents=True, exist_ok=True)
        MATRIX_STATE.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")

    def classify_event(self, event_text: str, event_id: str = "") -> dict:
        if event_id:
            self.store.add(event_id, event_text)
        hit = self.project(event_text)
        if hit.missed:
            return {"event_id": event_id, "coord": None,
                    "missed": True, "reason": hit.miss_reason}
        return {
            "event_id": event_id,
            "coord": {"sem": hit.sem, "ctx": hit.ctx, "act": hit.act},
            "max_sim": round(hit.max_sim, 3),
            "zone": hit.zone,   # §0.2 软区间：precise/fuzzy/inhibit
            "topk": [(c, round(s, 3)) for c, s in hit.topk],
        }


if __name__ == "__main__":
    tm = TopicMatrix()
    print("arch:", tm.classify_event("TU-8 架构设计与钢印机制演化", "evt_a"))
    print("daily:", tm.classify_event("七七今天吃了苹果和香蕉", "evt_b"))
    print("noise:", tm.classify_event("xyzqwe 随机乱码 无语义内容 测试", "evt_c"))
