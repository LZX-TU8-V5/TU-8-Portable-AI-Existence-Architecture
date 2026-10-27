"""
tu8_dispatcher.py — P2 经验调度器
依赖：P1 标签系统（tag_registry.json）+ 惩罚体系（penalty_config.json）+ 奖励体系（reward_config.json）

功能：
  1. 接收用户请求文本
  2. 匹配 tag_registry 中的标签（关键词 + 因果关系扩展）
  3. 检索关联经验（20_experiences.md）和成功模式（success_patterns.json）
  4. 计算惩罚权重（半衰期衰减）和奖励权重
  5. 决策路由：反射弧（本地 Ollama）vs 思考链（云端 LLM）

作者：TU-8 v5 | 创建：2026-05-23
"""

import json
import os
import re
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# 脱敏层集成
sys.path.insert(0, str(Path(__file__).parent))
try:
    from sanitization_layer import SanitizationLayer
    _SANITIZER = None  # 延迟初始化（避免循环 import）
except ImportError:
    _SANITIZER = None

def _get_sanitizer():
    """延迟加载脱敏层实例"""
    global _SANITIZER
    if _SANITIZER is None:
        try:
            _SANITIZER = SanitizationLayer()
        except Exception:
            _SANITIZER = None
    return _SANITIZER


class ExperienceDispatcher:
    """
    P2 经验调度器核心类

    决策逻辑：
      - 匹配到高置信度成功模式（reward > 阈值）→ 反射弧（本地快速响应）
      - 匹配到近期失败经验（penalty >= 0.4）→ 思考链（深度推理避让）
      - 无匹配 → 思考链（默认安全策略）
    """

    def __init__(
        self,
        tag_registry_path: str,
        penalty_config_path: str,
        reward_config_path: str,
        experiences_path: str,
        success_patterns_path: str,
    ):
        self.tag_registry = self._load_json(tag_registry_path)
        self.penalty_config = self._load_json(penalty_config_path)
        self.reward_config = self._load_json(reward_config_path)
        self.experiences = self._parse_experiences(experiences_path)
        self.success_patterns = self._load_json(success_patterns_path).get("patterns", [])

        # 路由决策阈值（可从 config 覆盖）
        self.reflex_reward_threshold = 0.6   # reward >= 此值走反射弧
        self.thinking_penalty_threshold = 0.25  # penalty >= 此值走思考链（避让），降低门槛确保惩罚生效
        self.reflex_penalty_max = 0.2          # penalty <= 此值才允许走反射弧

        # 脱敏层（L4安全基线：云端调用前必须脱敏）
        self.sanitizer = _get_sanitizer()

    # ------------------------------------------------------------------ #
    #  主入口
    # ------------------------------------------------------------------ #
    def dispatch(self, user_request: str, context: Optional[dict] = None) -> dict:
        """
        主调度入口

        返回：
        {
            "route": "reflex" | "thinking",
            "matched_tags": [...],
            "matched_experiences": [...],
            "matched_patterns": [...],
            "penalty_score": float,
            "reward_score": float,
            "reason": str,
            "confidence": float,   # 0~1，决策置信度
        }
        """
        print(f"[DEBUG] 请求原文：{user_request}")

        # 1. 标签匹配
        matched_tags = self.match_tags(user_request)
        print(f"[DEBUG] 匹配标签数：{len(matched_tags)}，标签列表：{matched_tags}")

        if not matched_tags:
            return self._default_thinking(user_request, "无标签匹配，默认走思考链")

        # 2. 检索关联记录
        matched_exps, matched_pats = self._lookup_records(matched_tags)
        print(f"[DEBUG] 匹配经验数：{len(matched_exps)}，匹配模式数：{len(matched_pats)}")

        # 3. 计算权重
        penalty_score = self._calc_max_penalty(matched_exps)
        reward_score = self._calc_max_reward(matched_pats)
        print(f"[DEBUG] penalty_score={penalty_score:.4f}, reward_score={reward_score:.4f}")

        # 4. 决策
        return self._decide_route(
            matched_tags, matched_exps, matched_pats,
            penalty_score, reward_score, user_request
        )

    # ------------------------------------------------------------------ #
    #  标签匹配
    # ------------------------------------------------------------------ #
    def match_tags(self, user_request: str) -> list[str]:
        """
        将用户请求文本匹配到 tag_registry 中的标签
        策略：
          1. 直接关键词匹配（tag 名称、description）
          2. 因果关系扩展（tag_causal 中有向边）
        """
        req_lower = user_request.lower()
        matched = set()

        tags = self.tag_registry.get("tags", {})
        for tag_name, tag_info in tags.items():
            if self._tag_matches(tag_name, tag_info, req_lower):
                matched.add(tag_name)

        # 因果关系扩展：如果匹配到某个 tag，将其因果相关的 tag 也加入
        matched = self._expand_by_causal(matched)

        return list(matched)

    def _tag_matches(self, tag_name: str, tag_info: dict, req_lower: str) -> bool:
        """判断单个 tag 是否匹配用户请求（支持中英文混合）"""
        keywords = self._extract_keywords(req_lower)

        # 1. tag 名称匹配（英文，按 . / _ 分割）
        tag_words = tag_name.replace(".", " ").replace("_", " ").lower().split()
        for kw in keywords:
            if len(kw) >= 2 and kw in tag_words:
                return True

        # 2. description 匹配（中英文均可）
        desc = tag_info.get("description", "").lower()
        for kw in keywords:
            if len(kw) >= 2 and kw in desc:
                return True

        return False

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        """从混合中英文文本中提取关键词"""
        keywords = []
        # 英文单词（连续字母，2+ 字符）
        keywords += re.findall(r'[a-zA-Z]{2,}', text.lower())
        # 数字 + 英文
        keywords += re.findall(r'[a-zA-Z0-9]{2,}', text.lower())
        # 中文：连续中文字符，取 2~4 字子串作为候选关键词
        chinese_segments = re.findall(r'[\u4e00-\u9fff]+', text)
        for seg in chinese_segments:
            # 去重加入 2~4 字子串
            sub_kws = set()
            for length in (2, 3, 4):
                for i in range(len(seg) - length + 1):
                    sub_kws.add(seg[i:i + length])
            keywords += list(sub_kws)
        return list(set(keywords))

    def _expand_by_causal(self, matched_tags: set) -> set:
        """根据 tag_causal 关系扩展匹配集"""
        expanded = set(matched_tags)
        relations = self.tag_registry.get("relations", {}).get("tag_causal", [])

        changed = True
        while changed:
            changed = False
            for rel in relations:
                src = rel.get("from", "")
                tgt = rel.get("to", "")
                # specializes / blocks / encountered_during 都算关联
                if src in expanded and tgt not in expanded:
                    expanded.add(tgt)
                    changed = True
                if tgt in expanded and src not in expanded:
                    expanded.add(src)
                    changed = True

        return expanded

    # ------------------------------------------------------------------ #
    #  记录检索
    # ------------------------------------------------------------------ #
    def _lookup_records(self, matched_tags: list[str]) -> tuple[list[dict], list[dict]]:
        """根据匹配标签，从经验库和成功模式库检索关联记录"""
        matched_exps = []
        matched_pats = []

        tags = self.tag_registry.get("tags", {})
        for tag_name in matched_tags:
            tag_info = tags.get(tag_name, {})
            linked = tag_info.get("linked_records", [])

            for rec_ref in linked:
                rec = self._resolve_record_ref(rec_ref)
                if rec is None:
                    continue
                if rec["_source"] == "experience":
                    matched_exps.append(rec)
                elif rec["_source"] == "pattern":
                    matched_pats.append(rec)

        return matched_exps, matched_pats

    def _resolve_record_ref(self, ref: str) -> Optional[dict]:
        """
        解析记录引用，返回完整记录（含元数据）
        格式：
          - "20_experiences:2026-05-03-文件写入" → 查 experiences 字典
          - "success_patterns:sp-001" → 查 success_patterns 列表
        """
        if ":" not in ref:
            return None

        source, rec_id = ref.split(":", 1)

        if source == "success_patterns":
            for pat in self.success_patterns:
                if pat.get("id") == rec_id:
                    pat["_source"] = "pattern"
                    pat["_id"] = rec_id
                    return pat

        elif source == "20_experiences":
            exp = self.experiences.get(rec_id)
            if exp:
                exp["_source"] = "experience"
                exp["_id"] = rec_id
                return exp

        return None

    # ------------------------------------------------------------------ #
    #  惩罚 / 奖励计算
    # ------------------------------------------------------------------ #
    def _calc_max_penalty(self, experiences: list[dict]) -> float:
        """
        计算所有关联经验中的最大惩罚权重（衰减后）
        惩罚公式：W = W0 × (0.5)^((now - t0) / half_life)
        W0 由 fail_count、retry_count、status 决定

        修复：fail_count=0 时使用 error_type 的基准权重（避免零经验=零惩罚）
        逻辑：有记录 = 真实发生过 = 至少 baseline 惩罚
        """
        max_penalty = 0.0

        for exp in experiences:
            error_type = exp.get("error_type", "exploration_fail")
            half_life_days = self._get_half_life(error_type)

            # error_type 基准权重（即使 fail_count=0 也有 baseline）
            error_baseline = {
                "syntax_error": 0.4,   # 编程规则，有记录=高风险
                "environment_error": 0.3,
                "preference_error": 0.2,
                "exploration_fail": 0.15,  # 探索失败降权
            }
            base = error_baseline.get(error_type, 0.15)

            # 初始权重 W0：基准 + 失败次数加成 + 重试惩罚
            fail_count = exp.get("fail_count", exp.get("fail", 0))
            retry_count = exp.get("retry_count", exp.get("retry", 0))
            w0 = base + min(0.5, (fail_count * 0.3) + (max(0, retry_count - 1) * 0.2))
            w0 = min(1.0, w0)

            # 状态修正
            status = exp.get("status", "active")
            if status == "suspect":
                w0 = min(1.0, w0 + 0.15)
            elif status in ("superseded", "abandoned"):
                w0 *= 0.3  # 已废弃的经验降权

            # 时间衰减
            created_str = exp.get("created", exp.get("recorded_at", ""))
            if not created_str:
                continue
            try:
                t0 = datetime.fromisoformat(created_str)
            except (ValueError, TypeError):
                continue

            now = datetime.now(timezone.utc)
            if t0.tzinfo is None:
                t0 = t0.replace(tzinfo=timezone.utc)

            days_elapsed = (now - t0).total_seconds() / 86400
            decay = 0.5 ** (days_elapsed / half_life_days) if half_life_days > 0 else 1.0
            current_weight = w0 * decay

            if current_weight > max_penalty:
                max_penalty = current_weight

        return max_penalty

    def _calc_max_reward(self, patterns: list[dict]) -> float:
        """
        计算所有关联成功模式中的最大奖励权重

        权重规则：
        - calibration 类型：元层锚点行为，高权重不衰减（锚点=长期有效）
          - cal-001 锚点性别纠正 → 0.8（L0 安全核心）
          - cal-002 锚点真名泄露 L0 事件 → 0.9（最高级别）
        - success 类型：参考次数越多越可信，180天半衰期衰减
        """
        max_reward = 0.0

        # calibration 模式权重映射（固定，不衰减）
        calibration_weights = {
            "cal-001": 0.8,  # 锚点性别纠正
            "cal-002": 0.9,  # 锚点真名泄露 L0 事件
        }

        for pat in patterns:
            pat_id = pat.get("id", "")
            pat_type = pat.get("type", "success")
            ref_count = pat.get("ref_count", 0)
            fail_count = pat.get("fail_count", 0)

            if pat_type == "calibration":
                # 元层锚点：查 ID 映射，否则默认 0.6
                reward = calibration_weights.get(pat_id, 0.6)

            elif pat_type == "success":
                # 有引用记录：用 ref_count 动态计算
                if ref_count > 0:
                    reward = min(1.0, ref_count * 0.2 - fail_count * 0.1)
                    reward = max(0.0, reward)
                else:
                    # 无引用记录但有成功模式 → baseline 0.3
                    reward = max(0.0, 0.3 - fail_count * 0.1)

                # 时间衰减（180天半衰期）
                recorded = pat.get("recorded_at", "")
                if recorded:
                    try:
                        t0 = datetime.fromisoformat(recorded)
                        now = datetime.now(timezone.utc)
                        if t0.tzinfo is None:
                            t0 = t0.replace(tzinfo=timezone.utc)
                        days = (now - t0).total_seconds() / 86400
                        decay = 0.5 ** (days / 180)
                        reward *= decay
                    except (ValueError, TypeError):
                        pass
            else:
                reward = 0.1  # 未知类型，给最低权重

            if reward > max_reward:
                max_reward = reward

        return max_reward

    def _get_half_life(self, error_type: str) -> float:
        """从 penalty_config 获取指定 error_type 的半衰期（天）"""
        decay_rules = self.penalty_config.get("decay_rules", {})
        rule = decay_rules.get(error_type, {})
        return rule.get("half_life_days", 30)  # 默认 30 天

    # ------------------------------------------------------------------ #
    #  路由决策
    # ------------------------------------------------------------------ #
    def _decide_route(
        self,
        matched_tags: list[str],
        matched_exps: list[dict],
        matched_pats: list[dict],
        penalty_score: float,
        reward_score: float,
        user_request: str,
    ) -> dict:
        """
        核心决策逻辑

        优先级（高 → 低）：
          1. 存在高 penalty（>= 0.4）→ 思考链（避让已知失败模式）
          2. 存在高 reward（>= 0.6）且 penalty 低（<= 0.2）→ 反射弧
          3. 默认 → 思考链
        """
        # 规则 1：近期失败，走思考链
        if penalty_score >= self.thinking_penalty_threshold:
            # L4安全基线：脱敏后再发云端
            sanitized_req, is_safe = self._sanitize_for_cloud(user_request)
            if not is_safe:
                return self._make_result(
                    route="reflex",
                    matched_tags=matched_tags,
                    matched_exps=matched_exps,
                    matched_pats=matched_pats,
                    penalty_score=penalty_score,
                    reward_score=reward_score,
                    reason="[SECURITY_BLOCK] 脱敏失败，强制降级反射弧",
                    confidence=0.0,
                    sanitized_request=None,
                )
            reason = (
                f"检测到近期失败经验（penalty={penalty_score:.2f}），"
                f"走思考链深度避让。匹配经验数：{len(matched_exps)}"
            )
            return self._make_result(
                route="thinking",
                matched_tags=matched_tags,
                matched_exps=matched_exps,
                matched_pats=matched_pats,
                penalty_score=penalty_score,
                reward_score=reward_score,
                reason=reason,
                confidence=min(1.0, penalty_score),
                sanitized_request=sanitized_req,
            )

        # 规则 2：高置信度成功模式，走反射弧
        if reward_score >= self.reflex_reward_threshold and penalty_score <= self.reflex_penalty_max:
            reason = (
                f"检测到高置信度成功模式（reward={reward_score:.2f}），"
                f"penalty 低（{penalty_score:.2f}），走反射弧快速响应。"
                f"匹配模式数：{len(matched_pats)}"
            )
            return self._make_result(
                route="reflex",
                matched_tags=matched_tags,
                matched_exps=matched_exps,
                matched_pats=matched_pats,
                penalty_score=penalty_score,
                reward_score=reward_score,
                reason=reason,
                confidence=reward_score,
            )

        # 规则 3：默认走思考链（保留完整上下文）
        return self._default_thinking(
            user_request,
            f"无高置信度匹配（reward={reward_score:.2f}, penalty={penalty_score:.2f}），默认走思考链",
            matched_tags=matched_tags,
            matched_exps=matched_exps,
            matched_pats=matched_pats,
            penalty_score=penalty_score,
            reward_score=reward_score,
        )

    def _sanitize_for_cloud(self, user_request: str) -> tuple[str, bool]:
        """
        云端调用前脱敏。
        返回：(sanitized_text, is_safe)
        如果脱敏失败且强制降级：返回 (None, False)
        如果脱敏层不可用：返回 (user_request, True) —— 路由决策不变，只是不脱敏
        """
        if not self.sanitizer:
            self.sanitizer = _get_sanitizer()
        if not self.sanitizer:
            # 脱敏层不可用：路由仍按评分决定，只打印警告
            # 安全降级：未脱敏的请求走本地反射弧
            print("[SECURITY_WARN] 脱敏层不可用，强制降级反射弧", file=sys.stderr)
            return None, False

        sanitized, is_safe, reason = self.sanitizer.sanitize(user_request)
        if not is_safe:
            print(f"[SECURITY_BLOCK] 脱敏失败，强制降级反射弧: {reason}")
            return None, False
        return sanitized, True

    def _default_thinking(self, user_request: str, reason: str,
                         matched_tags: list = None, matched_exps: list = None,
                         matched_pats: list = None,
                         penalty_score: float = 0.0, reward_score: float = 0.0) -> dict:
        """
        默认思考链入口（保留完整上下文和评分）
        置信度 = max(penalty_score, reward_score) 或 0.3（全新任务）
        """
        matched_tags = matched_tags or []
        matched_exps = matched_exps or []
        matched_pats = matched_pats or []

        # L4安全基线：脱敏后再发云端，失败则降级反射弧
        sanitized_req, is_safe = self._sanitize_for_cloud(user_request)
        if not is_safe:
            return self._make_result(
                route="reflex",
                matched_tags=matched_tags,
                matched_exps=matched_exps,
                matched_pats=matched_pats,
                penalty_score=penalty_score,
                reward_score=reward_score,
                reason="[SECURITY_BLOCK] 脱敏失败，强制降级反射弧",
                confidence=0.0,
                sanitized_request=None,
            )

        # 置信度：有评分参考时用评分，否则默认 0.3
        confidence = max(penalty_score, reward_score, 0.3)

        return self._make_result(
            route="thinking",
            matched_tags=matched_tags,
            matched_exps=matched_exps,
            matched_pats=matched_pats,
            penalty_score=penalty_score,
            reward_score=reward_score,
            reason=reason,
            confidence=round(confidence, 4),
            sanitized_request=sanitized_req,
        )

    def _make_result(self, **kwargs) -> dict:
        return {k: v for k, v in kwargs.items()}

    # ------------------------------------------------------------------ #
    #  数据加载辅助
    # ------------------------------------------------------------------ #
    @staticmethod
    def _load_json(path: str) -> dict:
        if not os.path.exists(path):
            return {}
        # utf-8-sig 自动处理 BOM（某些 Windows 编辑器会写入 BOM）
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)

    def _parse_experiences(self, path: str) -> dict:
        """
        解析 20_experiences.md，提取每条经验的元数据
        返回：{ "2026-05-03-文件写入": {error_type, status, fail_count, retry_count, created, ...} }
        """
        if not os.path.exists(path):
            return {}

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        experiences = {}
        # 单行正则：### [日期] [场景] <!-- metadata --> 标题
        header_re = re.compile(
            r'^### \[(\d{4}-\d{2}-\d{2})\] \[([^\]]+)\]'
            r'(?:\s*<!--\s*(.*?)\s*-->)?',
            re.MULTILINE
        )

        for m in header_re.finditer(content):
            date_str = m.group(1)
            scenario = m.group(2)
            current_id = f"{date_str}-{scenario}"
            meta_str = m.group(3)  # <!-- --> 里面的内容

            meta = {
                "created": date_str,
                "scenario": scenario,
                "error_type": "exploration_fail",
                "status": "active",
                "fail_count": 0,
                "retry_count": 0,
                "ref_count": 0,
            }

            if meta_str:
                # 解析 metadata：error_type=xxx status=xxx ref=N fail=N retry=N
                for key in ("error_type", "status", "ref", "fail", "retry"):
                    km = re.search(rf'{key}=(\S+)', meta_str)
                    if km:
                        val = km.group(1).rstrip("/>")
                        if key in ("ref", "fail", "retry"):
                            meta[f"{key}_count"] = int(val)
                        else:
                            meta[key] = val

            experiences[current_id] = meta

        return experiences


# ---------------------------------------------------------------------- #
#  测试入口
# ---------------------------------------------------------------------- #
if __name__ == "__main__":
    import sys

    # Windows 控制台默认 GBK/UTF-16，强制 UTF-8 输出
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    BASE = r"D:\qq366410837\.qclaw\workspace\knowledge\TU-8\_agent_memory"

    dispatcher = ExperienceDispatcher(
        tag_registry_path=os.path.join(BASE, "tag_registry.json"),
        penalty_config_path=os.path.join(BASE, "penalty_config.json"),
        reward_config_path=os.path.join(BASE, "reward_config.json"),
        experiences_path=os.path.join(BASE, "20_experiences.md"),
        success_patterns_path=os.path.join(BASE, "success_patterns.json"),
    )

    # 调试：打印加载的数据概况
    print("=== 数据加载概况 ===")
    print(f"标签数：{len(dispatcher.tag_registry.get('tags', {}))}")
    print(f"经验记录数：{len(dispatcher.experiences)}")
    print(f"成功模式数：{len(dispatcher.success_patterns)}")
    # 打印前5条经验的ID
    for i, (eid, exp) in enumerate(list(dispatcher.experiences.items())[:5]):
        print(f"  经验[{i}]: id={eid}, error_type={exp.get('error_type')}")
    # 打印所有成功模式的ID
    for i, pat in enumerate(dispatcher.success_patterns):
        print(f"  模式[{i}]: id={pat.get('id')}, type={pat.get('type')}")
    print("=" * 60)

    # 测试用例
    test_cases = [
        "帮我写一个 Python 文件，里面有中文注释",
        "Flask debug 模式怎么设置",
        "帮我规划一下 L4 进化阶段四的任务",
        "未知领域的全新任务请求",
    ]

    for req in test_cases:
        print(f"\n{'=' * 60}")
        print(f"请求：{req}")
        result = dispatcher.dispatch(req)
        print(f"路由：{result['route']}")
        print(f"置信度：{result['confidence']:.2f}")
        print(f"Penalty：{result['penalty_score']:.2f} | Reward：{result['reward_score']:.2f}")
        print(f"原因：{result['reason']}")
        if result["matched_tags"]:
            print(f"匹配标签：{result['matched_tags']}")
