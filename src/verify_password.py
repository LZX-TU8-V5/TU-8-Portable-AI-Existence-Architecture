# -*- coding: utf-8 -*-
"""
verify_password.py — 口令验证脚本
验证用户提供的口令，如果正确则更新 session_mode.json
"""
# 创作者: 李奥(金木蟾) | TU-8 v5

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

_WORKSPACE = Path(r"C:\Users\qq366410837\.qclaw\workspace")
_SECURITY_DIR = _WORKSPACE / "security"
_SESSION_MODE_FILE = _SECURITY_DIR / "session_mode.json"
_KEYS_FILE = _WORKSPACE / "secure_vault" / "keys.txt"


def load_stored_password():
    """从 keys.txt 读取存储的口令"""
    try:
        if _KEYS_FILE.exists():
            with open(_KEYS_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
    except Exception as e:
        print(f"读取口令文件失败: {e}", file=sys.stderr)
    return None


def verify_password(user_password: str) -> bool:
    """验证用户提供的口令"""
    stored = load_stored_password()
    if stored is None:
        print("错误: 未找到存储的口令", file=sys.stderr)
        return False
    
    if user_password.strip() == stored:
        return True
    else:
        print(f"口令验证失败", file=sys.stderr)
        return False


def update_session_mode_after_verification():
    """验证成功后更新 session_mode.json"""
    try:
        if _SESSION_MODE_FILE.exists():
            with open(_SESSION_MODE_FILE, 'r', encoding='utf-8') as f:
                mode_data = json.load(f)
        else:
            mode_data = {}
        
        # 更新验证状态
        mode_data["needs_verification"] = False
        mode_data["verification_passed"] = True
        mode_data["verification_time"] = datetime.now(timezone.utc).isoformat()
        mode_data["mode"] = "FULL"  # 验证成功后提升为 FULL 模式
        mode_data["result"] = "AUTO_PASS"
        mode_data["reason"] = "password_verified"
        
        with open(_SESSION_MODE_FILE, 'w', encoding='utf-8') as f:
            json.dump(mode_data, f, ensure_ascii=False, indent=2)
        
        print("[SUCCESS] 验证成功！会话模式已更新为 FULL")
        return True
    except Exception as e:
        print(f"更新会话模式失败: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    # 设置标准输出为 UTF-8
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    if len(sys.argv) < 2:
        print("Usage: python verify_password.py <password>")
        sys.exit(1)
    
    user_password = sys.argv[1]
    
    if verify_password(user_password):
        if update_session_mode_after_verification():
            sys.exit(0)
        else:
            sys.exit(1)
    else:
        print("[FAIL] Password verification failed")
        sys.exit(1)
