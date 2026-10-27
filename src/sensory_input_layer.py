# -*- coding: utf-8 -*-
"""
sensory_input_layer.py — TU-8 感知输入层 v1.0
日期: 2026-07-09
功能: 从 tu8_dispatch.py 抽取感知输入处理逻辑，统一管理输入预处理

设计理念:
  - 输入预处理：文本清洗、敏感词检测、意图预判
  - 信号增强：提取关键实体、情感标记、上下文锚点
  - 噪声过滤：去除无关信息、压缩冗余

架构位置:
  用户输入 → SensoryInputLayer → tu8_dispatch → tu8_agent
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path
import json

logger = logging.getLogger("TU8.SENSORY")


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class SensorySignal:
    """感知信号"""
    raw_input: str                    # 原始输入
    cleaned_input: str                # 清洗后输入
    language: str = "zh-CN"           # 语言
    intent_hint: str = "unknown"      # 意图预判
    entities: List[str] = field(default_factory=list)  # 提取的实体
    sentiment: str = "neutral"        # 情感标记
    context_anchors: List[str] = field(default_factory=list)  # 上下文锚点
    noise_ratio: float = 0.0          # 噪声比例
    signal_strength: float = 1.0      # 信号强度 (0-1)
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# 感知输入层
# =============================================================================

class SensoryInputLayer:
    """
    感知输入层
    
    职责：
    1. 文本清洗：去除控制字符、统一格式
    2. 敏感词检测：标记潜在风险
    3. 意图预判：快速分类（提问/指令/闲聊/其他）
    4. 实体提取：人名、地点、时间、关键词
    5. 情感标记：正面/负面/中性
    """
    
    # 意图关键词
    INTENT_KEYWORDS = {
        "question": ["?", "？", "怎么", "什么", "如何", "为什么", "哪", "吗", "呢"],
        "command": ["执行", "运行", "创建", "删除", "修改", "帮我", "请", "做"],
        "chat": ["哈哈", "呵呵", "好的", "嗯", "ok", "谢谢", "你好", "hi", "hello"],
    }
    
    # 敏感词模式（简化版）
    SENSITIVE_PATTERNS = [
        r"密码",
        r"口令",
        r"token",
        r"secret",
        r"api[_-]?key",
    ]
    
    # 噪声模式
    NOISE_PATTERNS = [
        r"\s+",           # 多余空白
        r"[\x00-\x08]",   # 控制字符
        r"[\x0b-\x0c]",
        r"[\x0e-\x1f]",
    ]
    
    def __init__(self, workspace_dir: str = ""):
        self.workspace = Path(workspace_dir) if workspace_dir else Path.cwd()
        self._sensitive_detected = []
    
    # -------------------------------------------------------------------------
    # 主处理流程
    # -------------------------------------------------------------------------
    
    def process(self, user_input: str) -> SensorySignal:
        """
        处理用户输入
        
        Args:
            user_input: 原始用户输入
            
        Returns:
            SensorySignal: 感知信号
        """
        # Step 1: 文本清洗
        cleaned = self._clean_text(user_input)
        
        # Step 2: 敏感词检测
        sensitive = self._detect_sensitive(cleaned)
        
        # Step 3: 意图预判
        intent = self._predict_intent(cleaned)
        
        # Step 4: 实体提取
        entities = self._extract_entities(cleaned)
        
        # Step 5: 情感标记
        sentiment = self._detect_sentiment(cleaned)
        
        # Step 6: 上下文锚点
        anchors = self._extract_anchors(cleaned)
        
        # Step 7: 噪声评估
        noise_ratio = self._estimate_noise(user_input, cleaned)
        
        # Step 8: 信号强度
        signal_strength = 1.0 - noise_ratio
        
        return SensorySignal(
            raw_input=user_input,
            cleaned_input=cleaned,
            intent_hint=intent,
            entities=entities,
            sentiment=sentiment,
            context_anchors=anchors,
            noise_ratio=noise_ratio,
            signal_strength=signal_strength,
            metadata={
                "sensitive_detected": sensitive,
                "language": self._detect_language(cleaned),
            }
        )
    
    # -------------------------------------------------------------------------
    # 子处理函数
    # -------------------------------------------------------------------------
    
    def _clean_text(self, text: str) -> str:
        """文本清洗"""
        # 去除控制字符
        for pattern in self.NOISE_PATTERNS:
            text = re.sub(pattern, " ", text)
        
        # 统一空白
        text = re.sub(r"\s+", " ", text)
        
        # 去除首尾空白
        text = text.strip()
        
        return text
    
    def _detect_sensitive(self, text: str) -> List[str]:
        """敏感词检测"""
        detected = []
        text_lower = text.lower()
        
        for pattern in self.SENSITIVE_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                detected.append(pattern)
        
        if detected:
            self._sensitive_detected.extend(detected)
            logger.warning(f"[Sensory] 敏感词检测: {detected}")
        
        return detected
    
    def _predict_intent(self, text: str) -> str:
        """意图预判"""
        text_lower = text.lower()
        
        for intent, keywords in self.INTENT_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    return intent
        
        return "other"
    
    def _extract_entities(self, text: str) -> List[str]:
        """实体提取（简化版）"""
        entities = []
        
        # 提取日期
        date_pattern = r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?"
        entities.extend(re.findall(date_pattern, text))
        
        # 提取时间
        time_pattern = r"\d{1,2}[:时]\d{1,2}[分]?"
        entities.extend(re.findall(time_pattern, text))
        
        # 提取邮箱
        email_pattern = r"[\w.-]+@[\w.-]+\.\w+"
        entities.extend(re.findall(email_pattern, text))
        
        # 提取URL
        url_pattern = r"https?://[^\s]+"
        entities.extend(re.findall(url_pattern, text))
        
        return list(set(entities))
    
    def _detect_sentiment(self, text: str) -> str:
        """情感标记（简化版）"""
        positive_words = ["好", "棒", "谢谢", "喜欢", "开心", "满意", "ok", "good"]
        negative_words = ["差", "烂", "讨厌", "生气", "不满", "不好", "错", "问题"]
        
        text_lower = text.lower()
        
        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)
        
        if pos_count > neg_count:
            return "positive"
        elif neg_count > pos_count:
            return "negative"
        return "neutral"
    
    def _extract_anchors(self, text: str) -> List[str]:
        """提取上下文锚点"""
        anchors = []
        
        # 提取引号内容
        quoted = re.findall(r"[""「」『』](.+?)[""「」『』]", text)
        anchors.extend(quoted)
        
        # 提取代码块标识
        code_blocks = re.findall(r"`(.+?)`", text)
        anchors.extend(code_blocks)
        
        return anchors
    
    def _estimate_noise(self, raw: str, cleaned: str) -> float:
        """估计噪声比例"""
        if len(raw) == 0:
            return 0.0
        
        noise_chars = len(raw) - len(cleaned)
        return noise_chars / len(raw)
    
    def _detect_language(self, text: str) -> str:
        """语言检测（简化版）"""
        # 统计中文字符比例
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        total_chars = len(text.replace(" ", ""))
        
        if total_chars == 0:
            return "unknown"
        
        if chinese_chars / total_chars > 0.3:
            return "zh-CN"
        return "en-US"
    
    # -------------------------------------------------------------------------
    # 统计接口
    # -------------------------------------------------------------------------
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "sensitive_detected_total": len(self._sensitive_detected),
            "recent_sensitive": self._sensitive_detected[-10:],
        }


# =============================================================================
# 便捷接口
# =============================================================================

_layer: Optional[SensoryInputLayer] = None


def get_sensory_layer(workspace_dir: str = "") -> SensoryInputLayer:
    """获取全局感知层"""
    global _layer
    if _layer is None:
        _layer = SensoryInputLayer(workspace_dir)
    return _layer


def process_input(user_input: str) -> SensorySignal:
    """处理输入（便捷接口）"""
    layer = get_sensory_layer()
    return layer.process(user_input)


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("感知输入层 v1.0 测试")
    print("=" * 60)
    
    layer = SensoryInputLayer()
    
    test_cases = [
        "2026-07-09 你好，请问如何使用这个功能？",
        "帮我创建一个文件 test.txt",
        "我的密码是 secret123",
        "哈哈，好的谢谢！",
        "https://example.com 这个链接怎么样？",
    ]
    
    for test in test_cases:
        print(f"\n[输入] {test}")
        signal = layer.process(test)
        print(f"  清洗: {signal.cleaned_input}")
        print(f"  意图: {signal.intent_hint}")
        print(f"  情感: {signal.sentiment}")
        print(f"  实体: {signal.entities}")
        print(f"  锚点: {signal.context_anchors}")
        print(f"  噪声: {signal.noise_ratio:.2%}")
        print(f"  信号强度: {signal.signal_strength:.2f}")
        
        if signal.metadata.get("sensitive_detected"):
            print(f"  ⚠️ 敏感词: {signal.metadata['sensitive_detected']}")
    
    print("\n" + "=" * 60)
    print("测试完成")
