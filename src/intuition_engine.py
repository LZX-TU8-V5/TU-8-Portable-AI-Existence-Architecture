"""
intuition_engine.py — TU-8 直觉引擎原型

基于预测编码理论的「快速感知」系统：
- 在完整推理前，先输出一个快速预判
- 核心 = 历史模式匹配 + 预测误差计算
- 类比大脑的 80-120ms 「直觉」回路
"""

import json
import time
import hashlib
from pathlib import Path
from typing import Optional, Set
from datetime import datetime, timezone

WORKSPACE = Path.home() / ".qclaw" / "workspace"
PATTERN_FILE = WORKSPACE / "memory" / "intuition_patterns.json"
LOG_FILE     = WORKSPACE / "memory" / "intuition_log.jsonl"


class IntuitionMatch:
    """一次直觉匹配的结果"""
    def __init__(self, pattern_id: str, similarity: float, response: str,
                 confidence: float, latency_ms: float):
        self.pattern_id   = pattern_id
        self.similarity    = similarity
        self.response      = response
        self.confidence    = confidence
        self.latency_ms   = latency_ms

    def to_dict(self) -> dict:
        return {
            "pattern_id":  self.pattern_id,
            "similarity": self.similarity,
            "response":    self.response[:100],
            "confidence":  self.confidence,
            "latency_ms":  self.latency_ms,
        }


class IntuitionEngine:
    """
    直觉引擎 = 快速模式匹配 + 预测误差感知
    
    工作流程：
    1. 输入当前情境文本（当前消息/上下文摘要）
    2. 与历史模式库做相似度匹配
    3. 如果命中（相似度 > 阈值），返回快速预判
    4. 引擎本身不决策，只输出「直觉信号」
    """

    def __init__(self, workspace: Optional[Path] = None):
        self.workspace = workspace or WORKSPACE
        self.patterns: list[dict] = []
        self._load_patterns()

    # ------------------------------------------------------------------ #
    #  模式管理
    # ------------------------------------------------------------------ #
    def learn(self, situation: str, response: str, outcome: str = "",
              tags: list[str] = None) -> str:
        """
        学习一个新模式。
        - situation: 触发情境（如用户消息摘要）
        - response: 当时采用的回应
        - outcome: 结果（"ok" / "error" / "confusion"）
        - tags: 分类标签（如"架构讨论", "bug诊断", "日常确认"）
        """
        pattern_id = self._hash(situation)
        pattern = {
            "id":           pattern_id,
            "situation_keywords": self._extract_keywords(situation),
            "situation":   situation[:200],
            "response":     response[:200],
            "outcome":      outcome or "unknown",
            "tags":          tags or [],
            "hit_count":    0,
            "accuracy":      0.5,       # 初始猜测
            "created_at":    time.time(),
            "last_hit":     0,
        }

        # 去重：同样 situation 不重复记录
        existing = [p for p in self.patterns if p["id"] == pattern_id]
        if not existing:
            self.patterns.append(pattern)
            self._save_patterns()

        return pattern_id

    def match(self, situation: str, threshold: float = 0.2) -> Optional[IntuitionMatch]:
        """
        在历史模式中匹配当前情境。
        - threshold: 匹配阈值（越低越容易触发）
        - 返回: IntuitionMatch | None
        """
        kw = self._extract_keywords(situation)
        kw_set = set(kw)

        start = time.perf_counter()
        best_match     = None
        best_similarity = 0.0

        for p in self.patterns:
            pk_set = set(p["situation_keywords"])
            if not pk_set:
                continue

            # Jaccard 相似度
            intersect   = kw_set & pk_set
            union        = kw_set | pk_set
            similarity   = len(intersect) / len(union) if union else 0

            if similarity > best_similarity:
                best_similarity = similarity
                best_match     = p

        latency_ms = (time.perf_counter() - start) * 1000

        if best_similarity >= threshold and best_match:
            # 用历史命中率调整置信度
            base_conf      = best_similarity
            accuracy_boost = (best_match["accuracy"] - 0.5) * 0.3
            confidence     = min(base_conf + accuracy_boost, 0.95)

            # 更新命中
            best_match["hit_count"] += 1
            best_match["last_hit"]    = time.time()
            self._save_patterns()

            self._log_match(situation, best_match["id"], best_similarity,
                            confidence, latency_ms)

            return IntuitionMatch(
                pattern_id   = best_match["id"],
                similarity    = best_similarity,
                response      = best_match["response"],
                confidence    = confidence,
                latency_ms    = round(latency_ms, 2),
            )

        return None

    def feedback(self, pattern_id: str, success: bool):
        """
        反馈校正：告诉直觉引擎它这次猜对/猜错了。
        会更新对应 pattern 的 accuracy。
        """
        for p in self.patterns:
            if p["id"] == pattern_id:
                # EMA 平滑更新 accuracy
                alpha = 0.3
                p["accuracy"] = p["accuracy"] * (1 - alpha) + (1.0 if success else 0.0) * alpha
                break
        self._save_patterns()

    # ------------------------------------------------------------------ #
    #  预测误差感知
    # ------------------------------------------------------------------ #
    def surprise_score(self, actual_outcome: str, predicted_response: str) -> float:
        """
        计算预测误差（surprise）。
        当直觉猜的和实际结果差距大 → surprise 高。
        用于触发「认知失调 → 深入分析」的信号。
        """
        if not predicted_response:
            return 0.0
        # 简单实现：长度差 + 内容重叠度
        len_ratio = abs(len(predicted_response) - len(actual_outcome)) / max(len(actual_outcome), 1)
        return min(len_ratio, 1.0)

    # ------------------------------------------------------------------ #
    #  内部工具
    # ------------------------------------------------------------------ #
    def _extract_keywords(self, text: str) -> list[str]:
        """提取关键词（去除停用词，取有意义的词汇）"""
        stops = {"的", "了", "是", "在", "有", "和", "就", "不", "人", "都",
                 "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你",
                 "会", "着", "没有", "看", "好", "自己", "这"}
        words = []
        for ch in text:
            if '\u4e00' <= ch <= '\u9fff':  # 中文字符
                words.append(ch)
        tokens = text.split()
        for t in tokens:
            if len(t) > 1 and t not in stops and not t.isdigit():
                words.append(t[:4])

        # 去重 & 排序
        return list(dict.fromkeys(words))[:20]

    def _hash(self, text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()[:12]

    def _load_patterns(self):
        if PATTERN_FILE.exists():
            try:
                with open(PATTERN_FILE, "r", encoding="utf-8") as f:
                    self.patterns = json.load(f)
            except Exception:
                self.patterns = []

    def _save_patterns(self):
        PATTERN_FILE.parent.mkdir(parents=True, exist_ok=True)
        # 只保留最近 200 个模式
        self.patterns = self.patterns[-200:]
        with open(PATTERN_FILE, "w", encoding="utf-8") as f:
            json.dump(self.patterns, f, ensure_ascii=False, indent=2)

    def _log_match(self, situation: str, pattern_id: str,
                   similarity: float, confidence: float, latency_ms: float):
        entry = {
            "timestamp":   datetime.now(timezone.utc).isoformat(),
            "pattern_id":  pattern_id,
            "similarity": round(similarity, 3),
            "confidence":  round(confidence, 3),
            "latency_ms":  round(latency_ms, 2),
            "situation_prefix": situation[:50],
        }
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    engine = IntuitionEngine()
    print("=== 直觉引擎测试 ===")

    # 学习几个模式
    engine.learn("用户问如何安装 skill", "用 skillhub_install 安装", "ok", ["skill", "安装"])
    engine.learn("用户报告 bug 报错", "先运行错误翻译器", "ok", ["bug", "诊断"])
    engine.learn("用户说继续", "继续上一个任务", "ok", ["确认", "继续"])

    # 匹配测试
    result = engine.match("怎么安装新的 skill")
    if result:
        print(f"[MATCH] 命中：{result.pattern_id}，置信度={result.confidence:.2f}")
        print(f"        快速预判：{result.response}")
        # 反馈
        engine.feedback(result.pattern_id, success=True)
    else:
        print("[NO MATCH]")
