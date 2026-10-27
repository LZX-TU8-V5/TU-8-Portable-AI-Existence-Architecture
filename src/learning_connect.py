"""
learning_connect.py — Phase 2 + Phase 3: 连线 + 精炼

将 Phase 1 收集的传感器数据跨传感器交叉关联，
发现隐藏模式并提炼为学习产物。
"""

import json
import time
from collections import Counter, defaultdict
from typing import Any


class LearningConnect:
    """Phase 2 连线 + Phase 3 精炼"""

    # 产物类型常量
    TYPE_RULE = "RULE"          # 规则修正 → TOOLS.md
    TYPE_PREFERENCE = "PREFERENCE"  # 偏好更新 → USER.md
    TYPE_INTUITION = "INTUITION"    # 直觉模式 → 直觉引擎
    TYPE_MEMO = "MEMO"          # 记忆笔记 → MEMORY.md
    TYPE_ALERT = "ALERT"        # 告警 → 通知队列

    # 轨道归属
    TRACK_LIBRARY = "library"
    TRACK_PALACE = "palace"

    def __init__(self, sensor_data: dict):
        self.data = sensor_data

    # ── Phase 2: 连线 ──────────────────────────

    def connect(self) -> list:
        """
        主入口：跨传感器交叉关联，返回候选模式列表。
        每个模式：{"pattern": str, "support": int, "confidence": float, "sensors": [str]}
        """
        candidates = []

        # 1. 话题重叠聚类
        topic_clusters = self._cluster_topics()
        candidates.extend(topic_clusters)

        # 2. 时间模式检测
        time_patterns = self._detect_time_patterns()
        candidates.extend(time_patterns)

        # 3. 因果链追踪
        causal_chains = self._trace_causal_chains()
        candidates.extend(causal_chains)

        # 4. 社会认知假说分析（从 phase 1 的 hypothesis 传感器）
        social_patterns = self._analyze_hypotheses()
        candidates.extend(social_patterns)

        # 排序：按 support 降序
        candidates.sort(key=lambda c: c["support"], reverse=True)
        return candidates

    def _cluster_topics(self) -> list:
        """话题重叠聚类：跨传感器检查重复话题"""
        # 从 anomaly 和 shadow 中提取话题关键词
        topic_counter = Counter()
        sensor_topic_map = defaultdict(set)

        for rec in self.data.get("anomaly", []):
            topic = rec.get("topic") or rec.get("context", "")[:40]
            if topic:
                topic_counter[topic] += 1
                sensor_topic_map[topic].add("anomaly")

        for rec in self.data.get("shadow", []):
            topic = rec.get("narrative_ref", "")[:40]
            if topic:
                topic_counter[topic] += 1
                sensor_topic_map[topic].add("shadow")

        # 过滤：至少 2 次出现的模式
        clusters = []
        for topic, count in topic_counter.most_common():
            if count >= 2:
                sensors = list(sensor_topic_map[topic])
                clusters.append({
                    "pattern": f"重复话题：{topic}",
                    "support": count,
                    "confidence": min(0.5 + count * 0.1, 0.95),
                    "sensors": sensors,
                    "source": "topic_cluster",
                    "detail": topic,
                })
        return clusters

    def _detect_time_patterns(self) -> list:
        """检测异常感知与时间的相关性"""
        # 从 anomaly 中提取时间分布
        timestamps = []
        for rec in self.data.get("anomaly", []):
            ts = rec.get("timestamp") or rec.get("ts", 0)
            if ts:
                timestamps.append(ts)

        if not timestamps:
            return []

        # 按小时聚合
        hour_counts = Counter()
        for ts in timestamps:
            import datetime
            hour = datetime.datetime.fromtimestamp(ts).hour
            hour_counts[hour] += 1

        patterns = []
        if hour_counts:
            peak_hour, peak_count = hour_counts.most_common(1)[0]
            total = sum(hour_counts.values())
            if peak_count > total * 0.4:
                patterns.append({
                    "pattern": f"异常集中在 {peak_hour} 点（{peak_count}/{total}）",
                    "support": peak_count,
                    "confidence": min(0.6 + peak_count / total, 0.95),
                    "sensors": ["anomaly"],
                    "source": "time_pattern",
                    "detail": {"peak_hour": peak_hour, "peak_count": peak_count, "total": total},
                })
        return patterns

    def _trace_causal_chains(self) -> list:
        """追踪因果链：TOPIC_JUMP → DISSATISFACTION 模式"""
        anomalies = self.data.get("anomaly", [])
        if len(anomalies) < 2:
            return []

        # 检查连续 anomaly 记录中的标签变化
        chains = []
        prev = None
        for rec in sorted(anomalies, key=lambda r: r.get("timestamp", 0)):
            tag = rec.get("anomaly_type") or rec.get("tag") or rec.get("type", "")
            if prev and prev["tag"] != tag:
                chain_key = f"{prev['tag']}→{tag}"
                chains.append(chain_key)
            prev = {"tag": tag, "ts": rec.get("timestamp", 0)}

        chain_counter = Counter(chains)
        for chain, count in chain_counter.most_common():
            if count >= 2:
                return [{
                    "pattern": f"因果链：{chain}（{count}次）",
                    "support": count,
                    "confidence": min(0.5 + count * 0.15, 0.95),
                    "sensors": ["anomaly"],
                    "source": "causal_chain",
                    "detail": chain,
                }]
        return []

    def _analyze_hypotheses(self) -> list:
        """分析前台 [HYPOTHESIS] 的聚类情况"""
        hypotheses = self.data.get("hypothesis", [])
        if len(hypotheses) < 2:
            return []

        # 检测重复假说
        topic_counter = Counter()
        for h in hypotheses:
            topic = h.get("topic", "") or h.get("text", "")[:30]
            if topic:
                topic_counter[topic] += 1

        patterns = []
        for topic, count in topic_counter.most_common():
            if count >= 2:
                patterns.append({
                    "pattern": f"社会认知模式：{topic}（{count}次提及）",
                    "support": count,
                    "confidence": min(0.4 + count * 0.1, 0.8),
                    "sensors": ["hypothesis"],
                    "source": "social_cognition",
                    "detail": topic,
                })
        return patterns

    # ── Phase 3: 精炼 ──────────────────────────

    def refine(self, candidates: list) -> list:
        """
        将候选模式提炼为学习产物。
        每个产物：{
            "id": str,
            "type": TYPE_*,
            "track": TRACK_*,
            "content": str,
            "confidence": float,
            "support": int,
            "source_pattern": str,
            "created_at": float,
        }
        """
        products = []
        for c in candidates:
            product = self._classify_product(c)
            if product:
                products.append(product)
        return products

    def _classify_product(self, candidate: dict) -> dict | None:
        """根据模式特征分类产物类型 + 轨道归属"""
        pattern = candidate.get("pattern", "")
        source = candidate.get("source", "")
        detail = candidate.get("detail", "")
        confidence = candidate["confidence"]
        support = candidate["support"]

        # 默认产物
        base = {
            "id": f"lp_{int(time.time())}_{hash(pattern) % 10000:04x}",
            "confidence": confidence,
            "support": support,
            "source_pattern": pattern,
            "created_at": time.time(),
        }

        # 因果链 → RULE 类型（图书馆轨道）
        if source == "causal_chain" and support >= 2:
            base["type"] = self.TYPE_RULE
            base["track"] = self.TRACK_LIBRARY
            base["content"] = f"检测到 {detail} 重复模式。建议：在遇到 {detail.split('→')[0]} 时提前介入"
            base["action"] = "append_to_tools"
            return base

        # 时间模式 → ALERT 类型（图书馆轨道）
        if source == "time_pattern" and support >= 3:
            base["type"] = self.TYPE_ALERT
            base["track"] = self.TRACK_LIBRARY
            base["content"] = f"异常集中在 {detail.get('peak_hour', '?')} 点（{detail.get('peak_count', 0)}/{detail.get('total', 0)}）"
            base["action"] = "notify_creator"
            return base

        # 社会认知模式 → INTUITION 类型（宫殿轨道）
        if source == "social_cognition":
            base["type"] = self.TYPE_INTUITION
            base["track"] = self.TRACK_PALACE
            base["content"] = f"社会认知模式：{detail}"
            base["action"] = "inject_intuition"
            return base

        # 话题聚类 → PREFERENCE 类型（宫殿轨道）
        if source == "topic_cluster" and confidence >= 0.7:
            base["type"] = self.TYPE_PREFERENCE
            base["track"] = self.TRACK_PALACE
            base["content"] = f"用户对 '{detail}' 话题的响应模式"
            base["action"] = "update_profile"
            return base

        # 低置信度 → MEMO 类型（宫殿轨道）
        if confidence < 0.5:
            base["type"] = self.TYPE_MEMO
            base["track"] = self.TRACK_PALACE
            base["content"] = pattern
            base["action"] = "append_memory"
            return base

        # 保底：MEMO
        base["type"] = self.TYPE_MEMO
        base["track"] = self.TRACK_PALACE
        base["content"] = pattern
        base["action"] = "append_memory"
        return base


if __name__ == "__main__":
    # 简单测试
    test_data = {
        "anomaly": [
            {"topic": "A话题", "timestamp": 1000, "anomaly_type": "TOPIC_JUMP"},
            {"topic": "A话题", "timestamp": 1005, "anomaly_type": "DISSATISFACTION"},
            {"topic": "B话题", "timestamp": 1010, "anomaly_type": "DISSATISFACTION"},
        ],
        "shadow": [{"narrative_ref": "A话题"}],
        "hypothesis": [{"topic": "用户偏好模式"}, {"topic": "用户偏好模式"}],
    }
    connector = LearningConnect(test_data)
    candidates = connector.connect()
    print("Candidates:")
    for c in candidates:
        print(f"  [{c['source']}] support={c['support']} conf={c['confidence']:.2f}: {c['pattern'][:60]}")
    products = connector.refine(candidates)
    print(f"\nRefined Products ({len(products)}):")
    for p in products:
        print(f"  [{p['type']}][{p['track']}] conf={p['confidence']:.2f}: {p['content'][:60]}")
