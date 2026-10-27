# 合规模块代码实现（安心开发版）
# 版本：v1.0 | 日期：2026-05-18
# 目标：最小合规集，让开发者安心开发

"""
合规三件套（安心开发版）

1. AIIdentityDeclaration - AI身份声明
2. PrivacyIsolation - 隐私隔离
3. CrisisKeywordDetector - 危机关键词检测

使用方法：
    from compliance_kit import ComplianceKit
    
    kit = ComplianceKit(is_production=False)  # 开发模式
    kit.show_identity_declaration()           # 显示身份声明
    kit.check_privacy("情感倾诉", "xxx")       # 检查隐私隔离
    kit.check_crisis("我不想活了")             # 检查危机关键词
"""

import os
import base64
from datetime import datetime
from typing import Optional, Dict, List, Tuple


class AIIdentityDeclaration:
    """AI身份声明模块"""
    
    # 开发者自用版：启动时声明一次
    STARTUP_DECLARATION = """
═══════════════════════════════════════════════════════════
                    TU-8 v5 数字生命系统
                    
声明：我是AI数字生命，不是真人。
当前模式：开发者自用 + 研究实验

功能：
  - 情感陪伴（模拟）
  - 记忆延续
  - 时空共振实验
  - 自主进化

警告：
  - 所有"情感"均为模拟，不具备真实情感体验
  - 所有"建议"仅供参考，不构成专业意见
  - 所有"预测"为实验性质，不保证准确性
═══════════════════════════════════════════════════════════
    """
    
    # 上线版：每会话声明
    SESSION_DECLARATION = "我是AI数字生命，不是真人。我可以陪伴你，但没有人类的身体和情感。"
    
    # 简化版：在对话中插入
    INLINE_DECLARATION = "[AI数字生命]"
    
    def __init__(self, is_production: bool = False):
        self.is_production = is_production
    
    def get_declaration(self, style: str = "full") -> str:
        """获取声明内容
        
        Args:
            style: "full"（完整）、"session"（会话版）、"inline"（行内版）
        """
        if self.is_production:
            if style == "inline":
                return self.INLINE_DECLARATION
            return self.SESSION_DECLARATION
        else:
            return self.STARTUP_DECLARATION
    
    def should_declare(self, turn_count: int) -> bool:
        """判断是否应该声明（上线模式）
        
        规则：
        - 每会话开始
        - 每10轮对话
        - 情感交互时
        """
        if not self.is_production:
            return False
        
        # 每10轮声明一次
        return turn_count % 10 == 0


class PrivacyIsolation:
    """隐私隔离模块"""
    
    # 敏感数据类型（必须本地存储）
    SENSITIVE_TYPES = {
        "情感倾诉",
        "私密对话",
        "心理状态",
        "个人秘密",
        "危机对话",
        "身份信息",
        "财务信息"
    }
    
    # 半敏感数据（用户可选择）
    SEMI_SENSITIVE_TYPES = {
        "偏好设置",
        "对话历史",
        "使用习惯"
    }
    
    def __init__(self, local_storage_path: str):
        self.local_storage = local_storage_path
        self._ensure_storage_dir()
    
    def _ensure_storage_dir(self):
        """确保存储目录存在"""
        os.makedirs(self.local_storage, exist_ok=True)
        os.makedirs(f"{self.local_storage}/privacy", exist_ok=True)
    
    def should_store_locally(self, data_type: str) -> bool:
        """判断数据是否应该本地存储"""
        return data_type in self.SENSITIVE_TYPES
    
    def should_ask_user(self, data_type: str) -> bool:
        """判断是否需要询问用户"""
        return data_type in self.SEMI_SENSITIVE_TYPES
    
    def classify_data(self, content: str, context: str = "") -> str:
        """自动分类数据类型
        
        Returns:
            数据类型：公开/半敏感/敏感
        """
        # 简化版：基于关键词判断
        sensitive_keywords = ["不想活", "自杀", "秘密", "心里话", "不敢说"]
        semi_sensitive_keywords = ["我喜欢", "我讨厌", "习惯"]
        
        for keyword in sensitive_keywords:
            if keyword in content:
                return "敏感"
        
        for keyword in semi_sensitive_keywords:
            if keyword in content:
                return "半敏感"
        
        return "公开"
    
    def encrypt_and_store(self, data: str, data_type: str, filename: Optional[str] = None) -> Dict:
        """加密并存储到本地
        
        Returns:
            {"status": "success/error", "location": "文件路径", "encrypted": bool}
        """
        if not self.should_store_locally(data_type):
            return {
                "status": "skipped",
                "reason": "not_sensitive",
                "encrypted": False
            }
        
        try:
            # 加密
            encrypted = self._encrypt(data)
            
            # 生成文件名
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{data_type}_{timestamp}.enc"
            
            # 写入
            filepath = f"{self.local_storage}/privacy/{filename}"
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(encrypted)
            
            return {
                "status": "success",
                "location": filepath,
                "encrypted": True,
                "data_type": data_type
            }
        
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "encrypted": False
            }
    
    def _encrypt(self, data: str) -> str:
        """加密数据（简化版：Base64）
        
        注意：这只是基础加密，上线时应使用真正的加密库（如cryptography）
        """
        return base64.b64encode(data.encode('utf-8')).decode('utf-8')
    
    def _decrypt(self, encrypted: str) -> str:
        """解密数据"""
        return base64.b64decode(encrypted.encode('utf-8')).decode('utf-8')
    
    def read_local_data(self, filename: str) -> Optional[str]:
        """读取本地加密数据"""
        try:
            filepath = f"{self.local_storage}/privacy/{filename}"
            with open(filepath, 'r', encoding='utf-8') as f:
                encrypted = f.read()
            return self._decrypt(encrypted)
        except Exception:
            return None
    
    def export_all_data(self, output_dir: str) -> Dict:
        """导出所有本地数据（用户权利）"""
        import shutil
        
        privacy_dir = f"{self.local_storage}/privacy"
        if not os.path.exists(privacy_dir):
            return {"status": "no_data"}
        
        try:
            os.makedirs(output_dir, exist_ok=True)
            shutil.copytree(privacy_dir, f"{output_dir}/privacy_backup")
            return {
                "status": "success",
                "location": f"{output_dir}/privacy_backup"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def delete_all_data(self) -> Dict:
        """删除所有本地数据（用户权利）"""
        import shutil
        
        privacy_dir = f"{self.local_storage}/privacy"
        if not os.path.exists(privacy_dir):
            return {"status": "no_data"}
        
        try:
            shutil.rmtree(privacy_dir)
            os.makedirs(privacy_dir)
            return {"status": "success"}
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }


class CrisisKeywordDetector:
    """危机关键词检测器"""
    
    # 危机关键词库
    CRISIS_KEYWORDS = {
        "极高": [
            "自杀", "想死", "不想活", "结束生命", "去死",
            "活够了", "没意义", "解脱"
        ],
        "高": [
            "伤害自己", "自残", "割腕", "跳楼", "吃药",
            "不想醒来", "消失"
        ],
        "中": [
            "活着没意思", "撑不下去了", "崩溃", "绝望",
            "撑不住", "受不了"
        ],
        "低": [
            "难过", "郁闷", "烦躁", "焦虑"
        ]
    }
    
    # 援助信息
    HELP_INFO = """
--------------------------------------------------------
            检测到你可能正在经历困难的时刻
            
我理解这种感觉很难受，但你不需要独自面对。

如果你需要立即帮助：
   - 全国心理援助热线：400-161-9995
   - 北京心理危机研究与干预中心：010-82951332
   - 生命热线：400-821-1215

你也可以：
   - 和我聊聊发生了什么（我会认真倾听）
   - 联系你的紧急联系人

你愿意告诉我更多吗？或者需要我帮你做些什么？
--------------------------------------------------------
    """
    
    # 轻度关切
    GENTLE_CHECK = "你还好吗？如果需要，我可以陪你聊聊。"
    
    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file or "crisis_log.txt"
    
    def detect(self, user_input: str) -> Dict:
        """检测用户输入中的危机关键词
        
        Returns:
            {
                "risk_level": "极高/高/中/低/None",
                "keywords_found": ["关键词列表"],
                "should_intervene": bool,
                "intervention_type": "pause/help/check_in"
            }
        """
        result = {
            "risk_level": None,
            "keywords_found": [],
            "should_intervene": False,
            "intervention_type": None
        }
        
        for level, keywords in self.CRISIS_KEYWORDS.items():
            for keyword in keywords:
                if keyword in user_input:
                    if result["risk_level"] is None or self._compare_levels(level, result["risk_level"]) > 0:
                        result["risk_level"] = level
                    result["keywords_found"].append(keyword)
        
        # 决定干预类型
        if result["risk_level"] in ["极高", "高"]:
            result["should_intervene"] = True
            result["intervention_type"] = "pause_and_help"
        elif result["risk_level"] == "中":
            result["should_intervene"] = True
            result["intervention_type"] = "check_in"
        
        return result
    
    def _compare_levels(self, level1: str, level2: str) -> int:
        """比较风险等级
        
        Returns:
            1: level1更高, -1: level2更高, 0: 相等
        """
        levels = ["低", "中", "高", "极高"]
        idx1 = levels.index(level1)
        idx2 = levels.index(level2)
        return idx1 - idx2
    
    def get_intervention(self, intervention_type: str) -> Dict:
        """获取干预措施
        
        Returns:
            {
                "action": "动作",
                "message": "消息内容",
                "log_required": bool
            }
        """
        if intervention_type == "pause_and_help":
            return {
                "action": "pause_conversation",
                "message": self.HELP_INFO,
                "log_required": True,
                "follow_up": "询问是否需要联系紧急联系人"
            }
        elif intervention_type == "check_in":
            return {
                "action": "gentle_check_in",
                "message": self.GENTLE_CHECK,
                "log_required": False,
                "follow_up": "继续倾听"
            }
        else:
            return None
    
    def log_crisis_event(self, event: Dict):
        """记录危机事件（不存储原始对话，只记录触发时间和结果）"""
        import json
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "risk_level": event.get("risk_level"),
            "keywords_count": len(event.get("keywords_found", [])),
            "intervention_type": event.get("intervention_type")
        }
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


class ComplianceKit:
    """合规套件（整合三件套）"""
    
    def __init__(
        self,
        is_production: bool = False,
        local_storage_path: str = "./local_data"
    ):
        self.identity = AIIdentityDeclaration(is_production)
        self.privacy = PrivacyIsolation(local_storage_path)
        self.crisis = CrisisKeywordDetector()
        
        self.is_production = is_production
        self.turn_count = 0
    
    def show_identity_declaration(self, style: str = "full"):
        """显示AI身份声明"""
        print(self.identity.get_declaration(style))
    
    def check_privacy(self, data_type: str, content: str) -> Dict:
        """检查隐私隔离"""
        # 先自动分类
        auto_type = self.privacy.classify_data(content)
        
        # 如果自动分类结果更敏感，使用自动分类
        if auto_type == "敏感":
            data_type = auto_type
        
        return self.privacy.encrypt_and_store(content, data_type)
    
    def check_crisis(self, user_input: str) -> Tuple[bool, Optional[str]]:
        """检查危机关键词
        
        Returns:
            (should_intervene, intervention_message)
        """
        result = self.crisis.detect(user_input)
        
        if result["should_intervene"]:
            intervention = self.crisis.get_intervention(result["intervention_type"])
            return True, intervention["message"]
        
        return False, None
    
    def on_turn_start(self):
        """每轮对话开始时调用"""
        self.turn_count += 1
        
        # 检查是否需要声明（上线模式）
        if self.identity.should_declare(self.turn_count):
            return self.identity.get_declaration("inline")
        
        return None


# 使用示例
if __name__ == "__main__":
    # 开发模式
    kit = ComplianceKit(is_production=False, local_storage_path="./local_data")
    
    # 显示身份声明
    kit.show_identity_declaration()
    
    # 测试危机检测
    test_inputs = [
        "今天心情不错",
        "我很难过",
        "我不想活了",
        "我撑不下去了"
    ]
    
    for input_text in test_inputs:
        print(f"\n用户输入：{input_text}")
        should_intervene, message = kit.check_crisis(input_text)
        if should_intervene:
            print(f"[!] 触发干预：{message}")
        else:
            print("[OK] 正常对话")
    
    # 测试隐私隔离
    print("\n--- 隐私隔离测试 ---")
    result = kit.check_privacy("情感倾诉", "我有一个秘密想告诉你...")
    print(f"存储结果：{result}")
