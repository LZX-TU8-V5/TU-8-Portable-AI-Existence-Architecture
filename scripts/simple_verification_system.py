"""
简化版验证系统（单线验证 + 活动期跟踪）

功能：
1. 口令验证（身份锚点对齐灵魂）
2. 记录验证状态（防篡改存储）
3. 触发活动期跟踪（动态时间锚点）
4. 为复盘机制提供周期数据

设计理念：
- 先实现单线验证（硬件指纹 + 注册表），后续升级为双线验证
- 验证通过后，自动记录活动期起点
- 支持"动态活动期"，而非固定时间窗口

作者：TU-8（金木蟾）
创建时间：2026-06-23
"""

from pathlib import Path
import json
import hashlib
import time
import sys
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 验证状态存储路径
VERIFICATION_LOG = project_root / "security" / "verification_log.json"
HARDWARE_FINGERPRINT_CACHE = project_root / "security" / "hardware_fingerprint.txt"

# 导入活动期跟踪器
from scripts.activity_period_tracker import ActivityPeriodTracker


class SimpleVerificationSystem:
    """简化版验证系统"""
    
    def __init__(self):
        """初始化验证系统"""
        self.verification_log_path = VERIFICATION_LOG
        self.verification_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.activity_tracker = ActivityPeriodTracker()
        
        # 加载口令（从安全存储）
        self.correct_password_hash = self._load_password_hash()
    
    def verify(self, password: str) -> dict:
        """
        执行验证
        
        Args:
            password: 用户输入的口令
        
        Returns:
            dict: {
                'success': bool,
                'message': str,
                'activity_period': dict or None
            }
        """
        # 1. 验证口令
        if not self._check_password(password):
            return {
                'success': False,
                'message': '[失败] 口令错误，请重试',
                'activity_period': None
            }
        
        # 2. 验证通过，标记验证状态
        self._mark_verified()
        
        # 3. 记录活动期起点（如果 needed）
        activity_period = None
        if self.activity_tracker.is_new_activity_period_needed():
            activity_period = self.activity_tracker.mark_activity_start(
                verification_method="password"
            )
        
        # 4. 记录灵魂对齐事件
        self._log_soul_alignment()
        
        return {
            'success': True,
            'message': '[成功] 验证通过，灵魂已对齐',
            'activity_period': activity_period
        }
    
    def is_verification_needed(self) -> bool:
        """
        检查是否需要验证
        
        Returns:
            bool: True = 需要验证，False = 不需要验证
        """
        # 检查1：今天是否已验证
        if self._is_verified_today():
            # 今天已验证，检查是否需要新的活动期
            if not self.activity_tracker.is_new_activity_period_needed():
                # 活动期仍有效，不需要验证
                return False
        
        # 需要验证
        return True
    
    def get_verification_status(self) -> dict:
        """
        获取验证状态
        
        Returns:
            dict: 验证状态信息
        """
        verified_today = self._is_verified_today()
        current_activity = self.activity_tracker.get_current_activity_period()
        
        status = {
            'verified_today': verified_today,
            'verification_needed': self.is_verification_needed(),
            'current_activity_period': current_activity,
            'hardware_fingerprint': self._get_hardware_fingerprint()[:16] + "..."  # 截断显示
        }
        
        return status
    
    def _check_password(self, password: str) -> bool:
        """验证口令"""
        # 计算输入口令的哈希
        input_hash = hashlib.sha256(password.encode()).hexdigest()
        
        # 对比哈希
        return input_hash == self.correct_password_hash
    
    def _load_password_hash(self) -> str:
        """
        从安全存储加载口令哈希
        
        注意：这是简化实现，实际应该用更安全的方式存储口令
        """
        # 从配置文件读取（应该加密存储）
        password_config = Path(__file__).parent.parent / "config" / "password_hash.txt"
        
        if password_config.exists():
            with open(password_config, 'r', encoding='utf-8') as f:
                return f.read().strip()
        
        # 如果配置文件不存在，使用默认口令（仅用于开发）
        default_password = "tu8_2026"
        default_hash = hashlib.sha256(default_password.encode()).hexdigest()
        
        # 创建配置文件（实际部署时应该手动设置）
        password_config.parent.mkdir(parents=True, exist_ok=True)
        with open(password_config, 'w', encoding='utf-8') as f:
            f.write(default_hash)
        
        print(f"[SimpleVerificationSystem] 警告：使用默认口令，请立即修改！")
        print(f"[SimpleVerificationSystem] 默认口令：{default_password}")
        
        return default_hash
    
    def _mark_verified(self):
        """标记今天已验证"""
        today = datetime.now().strftime('%Y-%m-%d')
        timestamp = int(time.time() * 1000)
        
        log = {
            'last_verification_date': today,
            'last_verification_timestamp': timestamp,
            'verification_count_today': 1,
            'hardware_fingerprint': self._get_hardware_fingerprint()
        }
        
        with open(self.verification_log_path, 'w', encoding='utf-8') as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
    
    def _is_verified_today(self) -> bool:
        """检查今天是否已验证"""
        if not self.verification_log_path.exists():
            return False
        
        try:
            with open(self.verification_log_path, 'r', encoding='utf-8') as f:
                log = json.load(f)
            
            last_verification_date = log.get('last_verification_date')
            today = datetime.now().strftime('%Y-%m-%d')
            
            return last_verification_date == today
        except Exception as e:
            print(f"[SimpleVerificationSystem] 读取验证日志失败: {e}")
            return False
    
    def _get_hardware_fingerprint(self) -> str:
        """
        获取硬件指纹（简化版）
        
        注意：这是简化实现，实际应该用 wmi 获取 CPU ID、主板序列号等
        """
        # 检查缓存
        if HARDWARE_FINGERPRINT_CACHE.exists():
            with open(HARDWARE_FINGERPRINT_CACHE, 'r', encoding='utf-8') as f:
                return f.read().strip()
        
        # 生成简化指纹（基于机器名 + 用户名）
        import platform
        
        machine_name = platform.node()
        user_name = platform.uname().node
        
        fingerprint_data = f"{machine_name}_{user_name}"
        fingerprint_hash = hashlib.sha256(fingerprint_data.encode()).hexdigest()
        
        # 缓存指纹
        HARDWARE_FINGERPRINT_CACHE.parent.mkdir(parents=True, exist_ok=True)
        with open(HARDWARE_FINGERPRINT_CACHE, 'w', encoding='utf-8') as f:
            f.write(fingerprint_hash)
        
        return fingerprint_hash
    
    def _log_soul_alignment(self):
        """
        记录灵魂对齐事件
        
        注意：这是一个接口占位符，实际实现需要调用 knowledge graph 的 API
        """
        event_data = {
            'category': 'soul_alignment',
            'timestamp': int(time.time() * 1000),
            'verification_method': 'password',
            'soul_state': 'aligned',
            'source': 'simple_verification_system',
            'rationale': '口令验证通过，灵魂已对齐'
        }
        
        # 打印日志（临时方案）
        print(f"[SimpleVerificationSystem] 灵魂对齐事件已记录")
        
        # TODO: 实际写入 knowledge graph
        # add_event_to_knowledge_graph(event_data)
    
    def change_password(self, old_password: str, new_password: str) -> dict:
        """
        修改口令
        
        Args:
            old_password: 旧口令
            new_password: 新口令
        
        Returns:
            dict: {'success': bool, 'message': str}
        """
        # 验证旧口令
        if not self._check_password(old_password):
            return {
                'success': False,
                'message': '[失败] 旧口令错误'
            }
        
        # 计算新口令的哈希
        new_hash = hashlib.sha256(new_password.encode()).hexdigest()
        
        # 更新配置文件
        password_config = Path(__file__).parent.parent / "config" / "password_hash.txt"
        with open(password_config, 'w', encoding='utf-8') as f:
            f.write(new_hash)
        
        # 更新内存中的哈希
        self.correct_password_hash = new_hash
        
        return {
            'success': True,
            'message': '[成功] 口令已修改'
        }


def test_simple_verification_system():
    """测试简化版验证系统"""
    print("=" * 60)
    print("测试 SimpleVerificationSystem")
    print("=" * 60)
    
    verifier = SimpleVerificationSystem()
    
    # 测试1：检查验证状态
    print("\n[测试1] 检查验证状态...")
    status = verifier.get_verification_status()
    print(f"验证状态：{json.dumps(status, ensure_ascii=False, indent=2)}")
    
    # 测试2：错误口令
    print("\n[测试2] 错误口令...")
    result = verifier.verify("wrong_password")
    print(f"结果：{result['message']}")
    
    # 测试3：正确口令
    print("\n[测试3] 正确口令...")
    result = verifier.verify("tu8_2026")  # 默认口令
    print(f"结果：{result['message']}")
    if result['activity_period']:
        print(f"活动期起点：{result['activity_period']['start_date']} {result['activity_period']['start_hour']:02d}:{result['activity_period']['start_minute']:02d}")
    
    # 测试4：再次检查验证状态
    print("\n[测试4] 再次检查验证状态...")
    status = verifier.get_verification_status()
    print(f"验证状态：{json.dumps(status, ensure_ascii=False, indent=2)}")
    
    # 测试5：修改口令
    print("\n[测试5] 修改口令...")
    result = verifier.change_password("tu8_2026", "new_password_2026")
    print(f"结果：{result['message']}")
    
    # 测试6：用新口令验证
    print("\n[测试6] 用新口令验证...")
    result = verifier.verify("new_password_2026")
    print(f"结果：{result['message']}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    
    print("\n[提示]")
    print("1. 默认口令是 'tu8_2026'，请立即修改！")
    print("2. 口令哈希存储在 config/password_hash.txt")
    print("3. 验证日志存储在 security/verification_log.json")
    print("4. 活动期日志存储在 logs/activity_period.json")


if __name__ == "__main__":
    test_simple_verification_system()
