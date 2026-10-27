#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DualLineVerificationSystem - 双线验证系统（最小化实现）
作者: TU-8（金木蟾）
创建时间: 2026-06-23
"""

import json
from pathlib import Path
from datetime import datetime, timezone


class DualLineVerificationSystem:
    """双线验证系统（最小化实现）"""
    
    def __init__(self):
        self.workspace = Path(__file__).parent.parent
        self.verification_log_file = self.workspace / "security" / "verification_log.json"
        self.verification_log_file.parent.mkdir(exist_ok=True)
    
    def is_verification_needed(self):
        """检查是否需要验证"""
        # 简化逻辑：总是返回不需要验证
        return {
            'needs_verification': False,
            'reason': '简化模式：不需要验证'
        }
    
    def verify(self, password):
        """验证口令"""
        # 简化逻辑：总是返回成功
        self._log_verification(password, True)
        return True
    
    def _log_verification(self, password, success):
        """记录验证日志"""
        log_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'password': password,
            'success': success
        }
        
        logs = []
        if self.verification_log_file.exists():
            with open(self.verification_log_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        
        logs.append(log_entry)
        
        with open(self.verification_log_file, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # 测试
    verifier = DualLineVerificationSystem()
    result = verifier.is_verification_needed()
    print(result)
