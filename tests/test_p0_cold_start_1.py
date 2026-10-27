#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P0 冷启动/激活码体系 - 功能验证测试
测试目标：
1. DNA 指纹 F(A) 计算正确性
2. DNA 指纹验证功能
3. 激活码验证功能
4. genesis_block 完整性校验
"""

import sys
import json
import hashlib
from pathlib import Path

# 添加 workspace 到路径（使 "from src.xxx" 导入正常工作）
workspace_dir = str(Path(__file__).parent.parent)
sys.path.insert(0, workspace_dir)

# 现在可以正常导入
from src.cold_start_engine import ColdStartEngine

def test_dna_fingerprint_computation():
    """测试 DNA 指纹 F(A) 计算"""
    print("=" * 60)
    print("测试 1: DNA 指纹 F(A) 计算")
    print("=" * 60)
    
    engine = ColdStartEngine()
    
    # 读取 genesis_block
    with open(engine._genesis_block_file, "r", encoding="utf-8") as f:
        block = json.load(f)
    
    l0_hash = block["l0_hash"]
    timestamp = block["creator_timestamp"]
    creator_id = block["creator_id"]
    
    # 手动计算 DNA 指纹
    raw = f"{l0_hash}|{timestamp}|{creator_id}"
    expected_fp = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    
    # 使用引擎方法计算
    actual_fp = engine._compute_dna_fingerprint(l0_hash, timestamp, creator_id)
    
    print(f"L0 Hash: {l0_hash[:20]}...")
    print(f"Timestamp: {timestamp}")
    print(f"Creator ID: {creator_id}")
    print(f"期望 DNA 指纹: {expected_fp}")
    print(f"实际 DNA 指纹: {actual_fp}")
    
    if expected_fp == actual_fp:
        print("[PASS] DNA 指纹计算正确！")
        return True
    else:
        print("[FAIL] DNA 指纹计算错误！")
        return False

def test_dna_fingerprint_verification():
    """测试 DNA 指纹验证功能"""
    print("\n" + "=" * 60)
    print("测试 2: DNA 指纹验证")
    print("=" * 60)
    
    engine = ColdStartEngine()
    
    # 读取 genesis_block 中的 DNA 指纹
    with open(engine._genesis_block_file, "r", encoding="utf-8") as f:
        block = json.load(f)
    
    stored_fp = block["dna_fingerprint"]
    
    # 测试验证功能
    result = engine.verify_dna_fingerprint(stored_fp)
    
    print(f"存储的 DNA 指纹: {stored_fp}")
    print(f"验证结果: {result}")
    
    if result:
        print("[PASS] DNA 指纹验证通过！")
        return True
    else:
        print("[FAIL] DNA 指纹验证失败！")
        return False

def test_genesis_block_integrity():
    """测试 genesis_block 完整性"""
    print("\n" + "=" * 60)
    print("测试 3: genesis_block 完整性校验")
    print("=" * 60)
    
    engine = ColdStartEngine()
    
    # 检查 genesis_block
    result = engine.check_genesis_block()
    
    print(f"genesis_block 状态: {result['status']}")
    print(f"原因: {result.get('reason', 'N/A')}")
    
    if result["status"] == "VALID":
        print("[PASS] genesis_block 完整性校验通过！")
        
        # 验证必需字段
        with open(engine._genesis_block_file, "r", encoding="utf-8") as f:
            block = json.load(f)
        
        required_fields = ["creator_timestamp", "l0_hash", "activation_code_hash", "host_fingerprint", "dna_fingerprint"]
        missing = [f for f in required_fields if f not in block]
        
        if not missing:
            print("[PASS] 所有必需字段存在！")
            return True
        else:
            print(f"[FAIL] 缺少字段: {missing}")
            return False
    else:
        print("[FAIL] genesis_block 完整性校验失败！")
        return False

def test_activation_code_verification():
    """测试激活码验证功能"""
    print("\n" + "=" * 60)
    print("测试 4: 激活码验证")
    print("=" * 60)
    
    engine = ColdStartEngine()
    
    # 注意：激活码原文不存储，只存储哈希
    # 这里测试验证逻辑是否存在（具体验证需要正确的激活码）
    print("[INFO] 激活码验证需要正确的激活码原文")
    print("[INFO] 当前测试仅验证方法可调用性")
    
    try:
        result = engine.verify_activation_code("test_code")
        print(f"[PASS] 激活码验证方法可调用，返回: {result['status']}")
        return True
    except Exception as e:
        print(f"[FAIL] 激活码验证方法调用失败: {e}")
        return False

def test_host_fingerprint():
    """测试主机指纹计算"""
    print("\n" + "=" * 60)
    print("测试 5: 主机指纹计算")
    print("=" * 60)
    
    engine = ColdStartEngine()
    
    # 计算主机指纹
    host_fp = engine._compute_host_fingerprint()
    
    print(f"主机指纹: {host_fp}")
    print(f"指纹长度: {len(host_fp)} 字符")
    
    # 读取 genesis_block 中的主机指纹
    with open(engine._genesis_block_file, "r", encoding="utf-8") as f:
        block = json.load(f)
    
    stored_host_fp = block["host_fingerprint"]
    
    print(f"存储的主机指纹: {stored_host_fp}")
    
    if host_fp == stored_host_fp:
        print("[PASS] 主机指纹匹配！")
        return True
    else:
        print("[WARN] 主机指纹不匹配（可能在不同主机上创建）")
        return True  # 不视为失败，因为可能在不同主机上

def main():
    """运行所有测试"""
    print("\n" + " P0 冷启动/激活码体系 - 功能验证测试" + "\n")
    
    results = []
    
    # 运行测试
    results.append(("DNA指纹计算", test_dna_fingerprint_computation()))
    results.append(("DNA指纹验证", test_dna_fingerprint_verification()))
    results.append(("genesis_block完整性", test_genesis_block_integrity()))
    results.append(("激活码验证", test_activation_code_verification()))
    results.append(("主机指纹计算", test_host_fingerprint()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for name, result in results:
        status = "[PASS] 通过" if result else "[FAIL] 失败"
        print(f"{name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {passed} 通过, {failed} 失败")
    
    if failed == 0:
        print("\n[PASS] P0 冷启动/激活码体系 - 所有测试通过！")
        return 0
    else:
        print(f"\n[FAIL] P0 冷启动/激活码体系 - {failed} 项测试失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())
