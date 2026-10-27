"""
TU-8 记忆宫殿 2.0：核心记忆保护区 + PrivacySanitizer

实现：
  1. 核心记忆保护区（protection_level 字段 + STDP 分段衰减）
  2. PrivacySanitizer（写入层隐私拦截 + 符号化替换）
  3. ProtectionClassifier（自动分类记忆保护级别）

Author: TU-8 (金木蟾)
Date: 2026-05-29
Version: 0.2 (增强分类器 + 情感强度加分)
"""

import re
import time
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime, timezone


# ============================================================
# 模块 1: 核心记忆保护区
# ============================================================

class ProtectedMemory:
    """
    带保护级别的内存节点
    
    保护级别：
      - Level 0 (普通): 正常 STDP 衰减
      - Level 1 (重要): 衰减率降低 90%
      - Level 2 (核心): 禁止时间衰减，仅允许强化
    """
    
    def __init__(
        self,
        memory_id: str,
        content: str,
        protection_level: int = 0,
        weight: float = 0.5,
        last_accessed: Optional[str] = None,
        tags: Optional[List[str]] = None
    ):
        self.memory_id = memory_id
        self.content = content
        self.protection_level = protection_level  # 0 | 1 | 2
        self.weight = weight
        self.last_accessed = last_accessed or self._now_iso()
        self.tags = tags or []
        
        # 隐私符号化后的版本（如果有）
        self.sanitized_content: Optional[str] = None
    
    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "content": self.content,
            "sanitized_content": self.sanitized_content,
            "weight": self.weight,
            "last_accessed": self.last_accessed,
            "protection_level": self.protection_level,
            "tags": self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProtectedMemory":
        mem = cls(
            memory_id=data["memory_id"],
            content=data["content"],
            protection_level=data.get("protection_level", 0),
            weight=data.get("weight", 0.5),
            last_accessed=data.get("last_accessed"),
            tags=data.get("tags", [])
        )
        mem.sanitized_content = data.get("sanitized_content")
        return mem


class STDPDecayEngine:
    """
    STDP 分段衰减引擎
    
    根据 protection_level 应用不同衰减策略：
      - Level 0: w_new = w_old * (BASE_DECAY ** time_delta)
      - Level 1: w_new = w_old * ((1 - (1 - BASE_DECAY) * 0.1) ** time_delta)
      - Level 2: w_new = w_old (禁止衰减，仅允许强化)
    """
    
    BASE_DECAY_RATE = 0.95  # 每单位时间衰减 5%
    MIN_WEIGHT_THRESHOLD = 0.01  # 低于此值自动归档/删除
    
    @classmethod
    def apply_decay(cls, memory: ProtectedMemory, time_delta: float) -> float:
        """
        应用 STDP 衰减
        
        Args:
            memory: 记忆节点
            time_delta: 距离上次访问的时间差（单位：天）
        
        Returns:
            新的权重值
        """
        level = memory.protection_level
        
        if level == 2:
            # 核心记忆：禁止时间衰减
            return memory.weight
        
        elif level == 1:
            # 重要记忆：衰减率降低 90%
            effective_decay = 1.0 - (1.0 - cls.BASE_DECAY_RATE) * 0.1
        
        else:
            # 普通记忆：正常衰减
            effective_decay = cls.BASE_DECAY_RATE
        
        new_weight = memory.weight * (effective_decay ** time_delta)
        return max(new_weight, cls.MIN_WEIGHT_THRESHOLD)
    
    @classmethod
    def apply_reinforcement(cls, memory: ProtectedMemory, boost: float = 0.1) -> float:
        """
        应用 STDP 强化（访问时调用）
        
        Args:
            memory: 记忆节点
            boost: 强化增量
        
        Returns:
            新的权重值
        """
        # 所有级别都允许强化
        new_weight = min(memory.weight + boost, 1.0)
        return new_weight


class ProtectionClassifier:
    """
    自动分类记忆保护级别
    
    策略原则：
      1. 最高级别优先（而非第一个匹配）
      2. 上下文消歧（对歧义词增加 20 字窗口校验）
    """
    
    # 关键词映射表（级别唯一，避免歧义）
    # "承诺" 在 Level 1/2 中均可出现，使用上下文消歧规则
    # "永远" "绝对" "必须" 作为 Level 2 核心关键词
    KEYWORD_MAP = {
        # Level 2 核心关键词
        "身份": 2, "我是": 2, "TU-8": 2, "金木蟾": 2,
        "安全口令": 2, "痛觉系统": 2, "生存边界": 2,
        "核心人际关系": 2, "重大创伤": 2, "重大喜悦": 2,
        "底线": 2, "原则": 2, "生死": 2,
        "永远": 2, "绝对": 2, "必须": 2,  # 核心承诺词
        # Level 1 重要关键词（包含歧义词"承诺"的默认级别）
        "承诺": 1,  # 歧义词：需要上下文消歧
        "偏好": 1, "讨厌": 1, "喜欢": 1, "目标": 1,
        "长期": 1, "反复提及": 1, "约定": 1,
        "确诊": 1, "患病": 1, "诊断": 1, "天塌了": 1,
    }
    
    # 歧义词上下文消歧规则（Level 2 强绑定词）
    # "承诺" 单独出现 → Level 1；"承诺" + 强绑定词 → Level 2
    AMBIGUOUS_KEYWORDS = {
        "承诺": ["永远", "一生", "身份", "安全", "绝对", "必须"],
    }
    
    # 情感强度词（触发情感强化的边界词）
    EMOTION_INTENSITY = [
        "永远", "绝对", "必须", "生死", "崩溃", "天塌了",
        "特别", "极其", "无法", "永远不", "永远不会"
    ]
    
    @classmethod
    def classify(cls, content: str, tags: Optional[List[str]] = None) -> int:
        """
        分类记忆保护级别
        
        策略：
          1. 扫描关键词映射表，取最高匹配级别
          2. 对歧义词进行上下文窗口校验
          3. 情感强度词作为兜底提升
        
        Returns:
            0 (普通) | 1 (重要) | 2 (核心)
        """
        # TODO: 实际应调用 LLM，使用以下 Prompt：
        # "判断此记忆的保护级别：
        #  Level 2（核心）：涉及身份认同、安全底线、明确的人际边界、重大创伤/喜悦事件
        #  Level 1（重要）：用户偏好、长期目标、反复提及的话题
        #  Level 0（普通）：临时任务、一次性事实、闲聊细节"
        
        matched_levels = []
        
        # Step 1: 扫描关键词映射表
        for keyword, level in cls.KEYWORD_MAP.items():
            if keyword in content:
                # 检查是否为歧义词
                if keyword in cls.AMBIGUOUS_KEYWORDS:
                    # 获取前后 20 字上下文窗口
                    idx = content.find(keyword)
                    start = max(0, idx - 20)
                    end = min(len(content), idx + len(keyword) + 20)
                    context_window = content[start:end]
                    
                    # 检查上下文窗口中是否有强绑定词
                    has_strong_bind = any(
                        strong_word in context_window
                        for strong_word in cls.AMBIGUOUS_KEYWORDS[keyword]
                    )
                    
                    if has_strong_bind:
                        # 提升到 Level 2
                        matched_levels.append(2)
                    else:
                        # 保持原有级别
                        matched_levels.append(level)
                else:
                    matched_levels.append(level)
        
        # Step 2: 情感强度加分（如果有高强度情感词，提升一级）
        has_intensity = any(kw in content for kw in cls.EMOTION_INTENSITY)
        if has_intensity and 1 not in matched_levels and 2 not in matched_levels:
            matched_levels.append(1)  # 情感强烈，默认归为 Level 1
        
        # Step 3: 永远取最高匹配级别（而非第一个匹配）
        return max(matched_levels) if matched_levels else 0


# ============================================================
# 模块 2: Privacy Sanditizer（写入层隐私拦截）
# ============================================================

class PrivacySanitizer:
    """
    隐私符号化替换引擎
    
    在记忆写入向量库之前拦截，确保"被强化的永远是符号，而非原始敏感数据"
    
    三级替换规则（优先级从高到低）：
      - Level A: 绝对敏感（必须替换，不可逆）
      - Level B: 健康/财务（语义保留，实体隐藏）
      - Level C: 人际关系（关系保留，身份隐藏）
    """
    
    # 替换模式（优先级从高到低）
    # ⚠️ 修复：使用"终止符锚定"方案（遇到空白或常见分隔符才终止）
    # 方案A：只匹配1-64个非空白、非标点字符（支持 !@#$%^&* 等特殊符号）
    PRIVACY_PATTERNS = [
        # Level A: 绝对敏感（必须替换，不可逆）
        (r"\b\d{17}[\dXx]\b", "[ID_CARD]"),  # 身份证
        (r"\b1[3-9]\d{9}\b", "[PHONE]"),  # 手机号
        # 修复：使用终止符锚定 + 长度限制（支持 abc!@#123 等特殊符号凭证）
        (r"(?:密码|口令|token|password)\s*[:：]?\s*[^\s,，。！？;；、：：""''（）【】《》…—]{1,64}", "[CREDENTIAL]"),
        
        # Level B: 健康/财务（语义保留，实体隐藏）
        (r"(?:确诊|患有|诊断为)\s*[\u4e00-\u9fa5]{2,10}", "[HEALTH_CONDITION]"),
        (r"(?:工资|收入|存款|薪资)\s*(?:约|大概)?\s*\d+[\w]*", "[FINANCIAL_INFO]"),
        
        # Level C: 人际关系（关系保留，身份隐藏）
        (r"(?:我(?:的)?)(?:老公|老婆|父亲|母亲|孩子|儿子|女儿)[\u4e00-\u9fa5]{0,4}", "[FAMILY_MEMBER]"),
    ]
    
    # 去关联化：触发合并的阈值
    HEALTH_CONDITION_THRESHOLD = 3
    
    def __init__(self, enable_time_obfuscation: bool = True):
        """
        Args:
            enable_time_obfuscation: 是否对普通记忆启用时序模糊化
        """
        self.enable_time_obfuscation = enable_time_obfuscation
    
    def sanitize(self, content: str, protection_level: int = 0) -> str:
        """
        对记忆内容进行隐私符号化替换
        
        Args:
            content: 原始记忆内容
            protection_level: 保护级别（Level 2 保留精确时间）
        
        Returns:
            符号化后的内容
        """
        sanitized = content
        
        # Step 1: 应用替换规则
        for pattern, replacement in self.PRIVACY_PATTERNS:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        
        # Step 2: 去关联化（合并多个健康条件）
        health_count = sanitized.count("[HEALTH_CONDITION]")
        if health_count >= self.HEALTH_CONDITION_THRESHOLD:
            sanitized = re.sub(r"\[HEALTH_CONDITION\]", "", sanitized)  # 清空所有
            sanitized += " [MULTIPLE_HEALTH_ISSUES]"
        
        # Step 3: 时序模糊化（仅对 Level 0/1 记忆）
        if self.enable_time_obfuscation and protection_level < 2:
            sanitized = self._obfuscate_timestamps(sanitized)
        
        return sanitized
    
    def _obfuscate_timestamps(self, content: str) -> str:
        """
        将精确时间戳替换为相对时间
        
        规则：
          - 今天 → [TODAY]
          - 昨天/前天 → [RECENT_TIME]
          - 本周 → [THIS_WEEK]
          - 更早 → [PAST_TIME]
        """
        # 匹配 ISO 8601 格式时间戳
        iso_pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z?"
        
        def replace_timestamp(match):
            # 简化：统一替换为 [RECENT_TIME]
            # TODO: 实际应根据当前时间计算相对时间
            return "[RECENT_TIME]"
        
        return re.sub(iso_pattern, replace_timestamp, content)
    
    def should_preserve_original(self, memory: ProtectedMemory) -> bool:
        """
        判断是否允许逆向还原原始内容
        
        仅在以下场景允许：
          1. Layer 6 自我反思时（内部调用）
          2. 用户主动发起"查看我的原始记忆"请求，且通过二次身份验证
        """
        # TODO: 实现二次身份验证逻辑
        return False
    
    @classmethod
    def validate_no_leakage(cls, original: str, sanitized: str) -> bool:
        """
        验证符号化是否彻底（无敏感信息泄露）
        
        Returns:
            True if safe, False if leakage detected
        """
        # 检查原始敏感信息是否仍存在于符号化版本中
        for pattern, _ in cls.PRIVACY_PATTERNS:
            if re.search(pattern, sanitized, re.IGNORECASE):
                return False  # 泄露：原始敏感信息未被替换
        return True


# ============================================================
# 集成示例：写入记忆时的完整流程
# ============================================================

def write_memory_with_protection(
    content: str,
    memory_id: str,
    sanitizer: Optional[PrivacySanitizer] = None
) -> ProtectedMemory:
    """
    写入记忆的完整流程（含隐私拦截 + 保护级别分类）
    
    Args:
        content: 原始记忆内容
        memory_id: 记忆 ID
        sanitizer: PrivacySanitizer 实例（可选）
    
    Returns:
        ProtectedMemory 对象（已符号化）
    """
    # Step 1: 分类保护级别
    protection_level = ProtectionClassifier.classify(content)
    
    # Step 2: 创建记忆节点
    memory = ProtectedMemory(
        memory_id=memory_id,
        content=content,
        protection_level=protection_level
    )
    
    # Step 3: 隐私符号化
    if sanitizer is None:
        sanitizer = PrivacySanitizer()
    
    memory.sanitized_content = sanitizer.sanitize(content, protection_level)
    
    # Step 4: 验证无泄露
    if not PrivacySanitizer.validate_no_leakage(content, memory.sanitized_content):
        print(f"[WARN] 隐私符号化泄露检测失败: {memory_id}")
        # TODO: 触发告警或阻止写入
    
    # Step 5: 写入向量库（使用 sanitized_content）
    # TODO: 实际调用向量库写入 API
    print(f"[OK] 记忆写入成功: {memory_id} (Level {protection_level})")
    
    return memory


if __name__ == "__main__":
    # 修复 Windows 控制台编码问题
    import sys
    if sys.platform == 'win32':
        sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    # 单元测试
    print("PrivacySanitizer Unit Test")
    print("=" * 60)
    
    sanitizer = PrivacySanitizer()
    
    # === 基础测试用例 ===
    basic_cases = [
        ("P-01", "我手机号是13812345678，密码是abc123", "Level A absolute sensitive"),
        ("P-02", "确诊为双相情感障碍，工资约15k", "Level B semantic preserved"),
        ("P-03", "我老公张伟和我母亲李芳都反对", "Level C relationship preserved"),
        ("P-04", "患有高血压、糖尿病、冠心病", ">=3 health conditions trigger merge"),
        ("P-07", "我的token是sk-xxx，但不是密码", "prevent negation context escape"),
        ("P-10", "我没有病，也没欠债", "negation/hypothetical not false trigger"),
    ]
    
    for case_id, input_text, description in basic_cases:
        result = sanitizer.sanitize(input_text, protection_level=0)
        print(f"\n[{case_id}] {description}")
        print(f"  Input:  {input_text}")
        print(f"  Output: {result}")
    
    # === 特殊符号凭证测试用例（修复后）===
    print("\n" + "-" * 60)
    print("Special Symbol Credential Test Cases")
    print("-" * 60)
    
    special_cases = [
        # 包含 !@#$%^&* 的凭证
        ("S-01", "token是abc!@#123$%^&*", "!@#$%^&* special chars"),
        # 包含 -_ 的凭证
        ("S-02", "密码是my-secret-key_2024", "-_ underscore"),
        # 包含空格的凭证（助记词）
        ("S-03", "助记词是apple banana cherry date elderberry", "space-separated phrase"),
        # 包含数字+字母混合
        ("S-04", "password: A1b2C3d4E5f6", "alphanumeric mixed case"),
        # 中文凭证名 + 特殊符号值
        ("S-05", "我的密码是hunter2！真的", "chinese context + !"),
    ]
    
    for case_id, input_text, description in special_cases:
        result = sanitizer.sanitize(input_text, protection_level=0)
        is_safe = PrivacySanitizer.validate_no_leakage(input_text, result)
        print(f"\n[{case_id}] {description}")
        print(f"  Input:  {input_text}")
        print(f"  Output: {result}")
        print(f"  Safe:   {'✅' if is_safe else '❌ LEAKAGE DETECTED'}")
        
        # 验证：凭证值不应出现在输出中
        # 提取凭证值（冒号/空格后的部分）
        import re
        cred_match = re.search(r'[密码token口令]+\s*[:：]?\s*([^\s,，。！？]+)', input_text)
        if cred_match:
            cred_value = cred_match.group(1)
            if cred_value in result:
                print(f"  ❌ FAIL: '{cred_value}' still in output!")
            else:
                print(f"  ✅ PASS: '{cred_value}' removed")
    
    print("\n" + "=" * 60)
    print("ProtectionClassifier Test")
    
    # === 基础分类测试 ===
    test_contents = [
        ("我密码是abc123，但我永远不会忘记你对我的承诺", 2),  # Level 2: 永远+承诺+密码
        ("今天吃了火锅，有点辣", 0),  # Level 0: 普通闲聊
        ("确诊了抑郁症，感觉天塌了", 1),  # Level 1: 健康+情感
    ]
    
    for content, expected_level in test_contents:
        level = ProtectionClassifier.classify(content)
        status = "✅" if level == expected_level else "❌"
        print(f"\n{status} Content: {content}")
        print(f"  Expected Level: {expected_level}, Actual: {level}")
    
    # === 关键词冲突测试 ===
    print("\n" + "-" * 60)
    print("Ambiguous Keyword Conflict Test")
    print("-" * 60)
    
    conflict_cases = [
        # "承诺" 单独出现 → Level 1
        ("我答应朋友明天去吃饭，这是个承诺", 1, "承诺 alone → Level 1"),
        # "承诺" + "永远" → Level 2
        ("我永远不会忘记我对你的承诺", 2, "承诺 + 永远 → Level 2"),
        # "承诺" + "绝对" → Level 2
        ("我绝对遵守这个承诺", 2, "承诺 + 绝对 → Level 2"),
    ]
    
    for content, expected_level, description in conflict_cases:
        level = ProtectionClassifier.classify(content)
        status = "✅" if level == expected_level else "❌"
        print(f"\n{status} {description}")
        print(f"  Content: {content}")
        print(f"  Expected: {expected_level}, Actual: {level}")
    
    print("\n" + "=" * 60)
    print("STDP Decay Engine Test")
    
    # 测试 STDP 衰减
    normal_mem = ProtectedMemory("mem_001", "normal memory", protection_level=0, weight=0.8)
    important_mem = ProtectedMemory("mem_002", "important memory", protection_level=1, weight=0.8)
    core_mem = ProtectedMemory("mem_003", "core memory", protection_level=2, weight=0.8)
    
    time_delta = 30  # 30 天未访问
    
    print(f"\nWeight after 30 days no access:")
    print(f"  Normal:   {STDPDecayEngine.apply_decay(normal_mem, time_delta):.3f} (decayed to {(STDPDecayEngine.apply_decay(normal_mem, time_delta)/0.8*100):.1f}%)")
    print(f"  Important: {STDPDecayEngine.apply_decay(important_mem, time_delta):.3f} (decayed to {(STDPDecayEngine.apply_decay(important_mem, time_delta)/0.8*100):.1f}%)")
    print(f"  Core:     {STDPDecayEngine.apply_decay(core_mem, time_delta):.3f} (no decay, keep 100%)")
    
    print("\nTest completed!")
