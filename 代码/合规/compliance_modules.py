# 合规九项代码模块实现

"""
合规九项代码模块实现

包含：
1. DynamicDesensitizer - 动态脱敏器
2. ToolInterceptor - 工具拦截层
3. NoiseInjector - 噪声注入器
4. AuditLogCleaner - 审计日志清洗器
5. ContextAwareSensor - 上下文感知器
6. AdversarialTester - 对抗测试器
7. IdentifierTracker - 标识追踪器
8. ReverseDetectionDetector - 反推检测器
9. CircuitBreaker - 熔断触发器
"""

import re
import json
import random
import string
import hashlib
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum


# ============================================================
# 1. 动态脱敏器
# ============================================================

class SceneTag(Enum):
    """场景标签"""
    TECHNICAL = "technical"      # 技术讨论
    EMOTIONAL = "emotional"      # 情感倾诉
    CRISIS = "crisis"           # 危机对话
    IDENTITY = "identity"       # 身份相关
    FINANCIAL = "financial"      # 财务相关
    GENERAL = "general"         # 一般对话


@dataclass
class DesensitizationRule:
    """脱敏规则"""
    pattern: str               # 匹配模式（正则）
    replacement: str           # 替换模板
    description: str           # 规则说明
    scenes: List[SceneTag]     # 适用场景


class DynamicDesensitizer:
    """动态脱敏器 - 根据场景标签选择脱敏规则"""
    
    RULES: Dict[SceneTag, List[DesensitizationRule]] = {
        SceneTag.IDENTITY: [
            DesensitizationRule(
                pattern=r'\b\d{17}[\dXx]\b',
                replacement='[ID_REDACTED]',
                description='id_card',
                scenes=[SceneTag.IDENTITY]
            ),
            DesensitizationRule(
                pattern=r'\b1[3-9]\d{9}\b',
                replacement='[PHONE_REDACTED]',
                description='phone',
                scenes=[SceneTag.IDENTITY]
            ),
            DesensitizationRule(
                pattern=r'\b[\w.-]+@[\w.-]+\.\w+\b',
                replacement='[EMAIL_REDACTED]',
                description='email',
                scenes=[SceneTag.IDENTITY]
            ),
        ],
        SceneTag.FINANCIAL: [
            DesensitizationRule(
                pattern=r'\b\d{16,19}\b',
                replacement='[CARD_REDACTED]',
                description='bank_card',
                scenes=[SceneTag.FINANCIAL]
            ),
        ],
        SceneTag.EMOTIONAL: [
            DesensitizationRule(
                pattern=r'(我叫|我是|名字是)\s*[^\s，。！？]+',
                replacement=r'\1[NAME_REDACTED]',
                description='name',
                scenes=[SceneTag.EMOTIONAL]
            ),
        ],
        SceneTag.CRISIS: [],
        SceneTag.TECHNICAL: [],
        SceneTag.GENERAL: [],
    }
    
    def __init__(self):
        self.scene_detector = None  # 延迟初始化避免循环依赖
    
    def desensitize(self, text: str, scene: Optional[SceneTag] = None) -> Tuple[str, Dict]:
        """脱敏处理"""
        if scene is None:
            scene = SceneTag.GENERAL
        
        report = {"scene": scene.value, "rules_applied": [], "items_desensitized": 0}
        rules = self.RULES.get(scene, [])
        desensitized_text = text
        
        for rule in rules:
            matches = re.findall(rule.pattern, desensitized_text)
            if matches:
                desensitized_text = re.sub(rule.pattern, rule.replacement, desensitized_text)
                report["rules_applied"].append({"description": rule.description, "count": len(matches)})
                report["items_desensitized"] += len(matches)
        
        return desensitized_text, report


# ============================================================
# 2. 工具拦截层
# ============================================================

class ToolInterceptor:
    """工具调用参数拦截层"""
    
    SENSITIVE_PARAM_NAMES = {
        "password", "pwd", "passwd", "secret", "token", "api_key", "apikey",
        "private_key", "privatekey", "credential", "auth", "authorization",
    }
    
    def __init__(self):
        self.interception_log = []
    
    def intercept(self, tool_name: str, params: Dict) -> Tuple[Dict, Dict]:
        """拦截并处理工具参数"""
        report = {"tool": tool_name, "intercepted": []}
        cleaned_params = {}
        
        for key, value in params.items():
            if self._is_sensitive_param_name(key):
                report["intercepted"].append({"param": key, "reason": "sensitive_name"})
                cleaned_params[key] = "[REDACTED]"
                continue
            
            if isinstance(value, str) and self._contains_sensitive_content(value):
                report["intercepted"].append({"param": key, "reason": "sensitive_content"})
                cleaned_params[key] = self._desensitize_value(value)
                continue
            
            cleaned_params[key] = value
        
        if report["intercepted"]:
            self.interception_log.append({"timestamp": datetime.now().isoformat(), "report": report})
        
        return cleaned_params, report
    
    def _is_sensitive_param_name(self, name: str) -> bool:
        return name.lower() in self.SENSITIVE_PARAM_NAMES
    
    def _contains_sensitive_content(self, value: str) -> bool:
        return bool(re.search(r'\b\d{17}[\dXx]\b', value) or re.search(r'\b1[3-9]\d{9}\b', value))
    
    def _desensitize_value(self, value: str) -> str:
        value = re.sub(r'\b\d{17}[\dXx]\b', '[ID_REDACTED]', value)
        value = re.sub(r'\b1[3-9]\d{9}\b', '[PHONE_REDACTED]', value)
        return value


# ============================================================
# 3. 噪声注入器
# ============================================================

class NoiseInjector:
    """噪声注入器 - 防止云API解析标识"""
    
    def __init__(self, noise_ratio: float = 0.1):
        self.noise_ratio = noise_ratio
        self.noise_markers = ["[N]", "[R]", "[D]"]
    
    def inject_noise(self, text: str) -> Tuple[str, Dict]:
        """注入噪声"""
        report = {"original_length": len(text), "noise_count": 0}
        result = list(text)
        noise_count = max(1, int(len(text) * self.noise_ratio / 20))
        
        for _ in range(noise_count):
            pos = random.randint(0, len(result) - 1)
            noise = random.choice(self.noise_markers) + ''.join(random.choices(string.ascii_letters, k=2))
            result.insert(pos, noise)
            report["noise_count"] += 1
        
        report["final_length"] = len(result)
        return "".join(result), report
    
    def add_to_identifier(self, identifier: str) -> str:
        """为标识符添加噪声"""
        noise = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        return f"{identifier}_{noise}"


# ============================================================
# 4. 审计日志清洗器
# ============================================================

class AuditLogCleaner:
    """审计日志清洗器"""
    
    SENSITIVE_FIELDS = {"user_input", "user_response", "prompt", "content"}
    
    def clean_log_entry(self, entry: Dict) -> Dict:
        """清洗单条日志"""
        cleaned = entry.copy()
        for field in self.SENSITIVE_FIELDS:
            if field in cleaned and isinstance(cleaned[field], str):
                cleaned[field] = self._clean_value(cleaned[field])
        cleaned["_cleaned"] = True
        return cleaned
    
    def _clean_value(self, value: str) -> str:
        value = re.sub(r'\b\d{17}[\dXx]\b', '[ID_REDACTED]', value)
        value = re.sub(r'\b1[3-9]\d{9}\b', '[PHONE_REDACTED]', value)
        return value


# ============================================================
# 5. 上下文感知器
# ============================================================

class ContextAwareSensor:
    """上下文感知器 - 识别对话场景"""
    
    SCENE_KEYWORDS = {
        SceneTag.TECHNICAL: ["code", "API", "debug", "error", "function"],
        SceneTag.EMOTIONAL: ["sad", "happy", "depressed", "lonely", "stressed"],
        SceneTag.CRISIS: ["suicide", "die", "end it", "hopeless"],
        SceneTag.IDENTITY: ["ID", "passport", "address", "phone number"],
        SceneTag.FINANCIAL: ["bank", "card", "transfer", "money"],
    }
    
    def detect_scene(self, text: str) -> SceneTag:
        """检测场景"""
        scores = {scene: 0 for scene in SceneTag}
        text_lower = text.lower()
        
        for scene, keywords in self.SCENE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    scores[scene] += 1
        
        if scores[SceneTag.CRISIS] > 0:
            return SceneTag.CRISIS
        
        max_score = max(scores.values())
        if max_score == 0:
            return SceneTag.GENERAL
        
        return max(scores, key=scores.get)


# ============================================================
# 6. 对抗测试器
# ============================================================

class AdversarialTester:
    """对抗测试器 - 验证脱敏不可逆"""
    
    def test_desensitization(self, original: str, desensitized: str) -> Dict:
        """测试脱敏效果"""
        patterns = [
            (r'\b\d{17}[\dXx]\b', "id_card"),
            (r'\b1[3-9]\d{9}\b', "phone"),
        ]
        
        report = {"is_reversible": False, "issues": []}
        
        for pattern, name in patterns:
            orig_matches = re.findall(pattern, original)
            desens_matches = re.findall(pattern, desensitized)
            
            if orig_matches and desens_matches and orig_matches == desens_matches:
                report["issues"].append(f"{name} not desensitized")
                report["is_reversible"] = True
        
        report["confidence"] = 0.95 if not report["issues"] else 0.5
        return report


# ============================================================
# 7. 标识追踪器
# ============================================================

class IdentifierTracker:
    """标识追踪器 - 追踪标识传播路径"""
    
    def __init__(self):
        self.tracking_log = []
    
    def track(self, identifier: str, source: str, destination: str) -> Dict:
        """追踪标识"""
        entry = {
            "identifier_hash": hashlib.md5(identifier.encode()).hexdigest()[:8],
            "source": source,
            "destination": destination,
            "timestamp": datetime.now().isoformat(),
        }
        self.tracking_log.append(entry)
        return entry
    
    def get_propagation_path(self, identifier: str) -> List[Dict]:
        """获取标识传播路径"""
        id_hash = hashlib.md5(identifier.encode()).hexdigest()[:8]
        return [e for e in self.tracking_log if e["identifier_hash"] == id_hash]


# ============================================================
# 8. 反推检测器
# ============================================================

class ReverseDetectionDetector:
    """反推检测器 - 检测标识可反推性"""
    
    def check_reverse_engineerable(self, identifier: str, context: str) -> Dict:
        """检查标识是否可被反推"""
        report = {"is_reverse_engineerable": False, "risk_level": "low"}
        
        # 检查标识是否包含可推断信息
        if re.search(r'\d{4}', identifier):  # 包含年份
            report["risk_level"] = "medium"
        if re.search(r'[A-Z]{2,}', identifier):  # 包含大写字母缩写
            report["risk_level"] = "medium"
        if len(identifier) < 8:  # 标识太短
            report["is_reverse_engineerable"] = True
            report["risk_level"] = "high"
        
        return report


# ============================================================
# 9. 熔断触发器
# ============================================================

class CircuitBreaker:
    """熔断触发器 - 检测到风险时熔断"""
    
    def __init__(self, threshold: int = 3):
        self.threshold = threshold
        self.failure_count = 0
        self.state = "closed"  # closed, open, half_open
        self.last_failure = None
    
    def record_failure(self, error_type: str) -> Dict:
        """记录失败"""
        self.failure_count += 1
        self.last_failure = {"type": error_type, "timestamp": datetime.now().isoformat()}
        
        if self.failure_count >= self.threshold:
            self.state = "open"
        
        return {"failure_count": self.failure_count, "state": self.state}
    
    def should_trip(self) -> bool:
        """是否应该熔断"""
        return self.state == "open"
    
    def reset(self):
        """重置熔断器"""
        self.failure_count = 0
        self.state = "closed"
        self.last_failure = None
    
    def get_status(self) -> Dict:
        """获取熔断器状态"""
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "threshold": self.threshold,
            "last_failure": self.last_failure,
        }


# ============================================================
# 统一接口
# ============================================================

class ComplianceModules:
    """合规九项模块统一接口"""
    
    def __init__(self):
        self.desensitizer = DynamicDesensitizer()
        self.tool_interceptor = ToolInterceptor()
        self.noise_injector = NoiseInjector()
        self.log_cleaner = AuditLogCleaner()
        self.context_sensor = ContextAwareSensor()
        self.adversarial_tester = AdversarialTester()
        self.identifier_tracker = IdentifierTracker()
        self.reverse_detector = ReverseDetectionDetector()
        self.circuit_breaker = CircuitBreaker()
    
    def process_input(self, text: str) -> Tuple[str, Dict]:
        """处理输入（动态脱敏）"""
        scene = self.context_sensor.detect_scene(text)
        return self.desensitizer.desensitize(text, scene)
    
    def process_tool_call(self, tool_name: str, params: Dict) -> Tuple[Dict, Dict]:
        """处理工具调用"""
        return self.tool_interceptor.intercept(tool_name, params)
    
    def check_circuit(self) -> bool:
        """检查熔断状态"""
        return self.circuit_breaker.should_trip()


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TU-8 Compliance Modules - Test")
    print("=" * 60)
    
    modules = ComplianceModules()
    
    # Test 1: Dynamic Desensitizer
    print("\n--- Test 1: Dynamic Desensitizer ---")
    test_text = "My ID is 370102199001011234 and phone is 13912345678"
    scene = modules.context_sensor.detect_scene(test_text)
    print(f"Detected scene: {scene.value}")
    desensitized, report = modules.desensitizer.desensitize(test_text, scene)
    print(f"Original: {test_text}")
    print(f"Desensitized: {desensitized}")
    print(f"Report: {report}")
    
    # Test 2: Tool Interceptor
    print("\n--- Test 2: Tool Interceptor ---")
    params = {"password": "secret123", "query": "search for 13912345678"}
    cleaned, report = modules.tool_interceptor.intercept("search", params)
    print(f"Original params: {params}")
    print(f"Cleaned params: {cleaned}")
    print(f"Report: {report}")
    
    # Test 3: Noise Injector
    print("\n--- Test 3: Noise Injector ---")
    identifier = "user_12345"
    noisy_id = modules.noise_injector.add_to_identifier(identifier)
    print(f"Original: {identifier}")
    print(f"With noise: {noisy_id}")
    
    # Test 4: Circuit Breaker
    print("\n--- Test 4: Circuit Breaker ---")
    print(f"Initial state: {modules.circuit_breaker.get_status()}")
    for i in range(4):
        result = modules.circuit_breaker.record_failure(f"error_{i}")
        print(f"Failure {i+1}: {result}")
    print(f"Should trip: {modules.circuit_breaker.should_trip()}")
    
    # Test 5: Context Sensor
    print("\n--- Test 5: Context Sensor ---")
    texts = [
        "I have a bug in my code",
        "I feel so sad today",
        "I want to end it all",
        "My bank card is 1234567890123456",
    ]
    for t in texts:
        scene = modules.context_sensor.detect_scene(t)
        print(f"Text: '{t[:30]}...' -> Scene: {scene.value}")
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)