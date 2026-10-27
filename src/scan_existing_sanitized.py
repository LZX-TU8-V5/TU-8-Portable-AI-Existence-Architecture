#!/usr/bin/env python3
"""
存量扫描：检查已有 sanitized_content 是否存在隐私泄露
扫描范围：最近 7 天写入的记录
"""
# 创作者: 李奥(金木蟾) | TU-8 v5

import sys
import time
import json
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from tu8_memory import TU8MemoryEngine, PrivacySanitizer

WORKSPACE = r"C:\Users\qq366410837\.qclaw\workspace"
CUTOFF_TS = time.time() - 7 * 86400  # 7天前

def main():
    engine = TU8MemoryEngine(workspace_dir=WORKSPACE, memory_dir=None)
    
    leaks_found = []
    scanned_count = 0
    risk_levels = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    
    print(f" 存量扫描启动")
    print(f"   扫描范围: {datetime.fromtimestamp(CUTOFF_TS).strftime('%Y-%m-%d')} 至今")
    print(f"   长期记忆条目: {len(engine.long_term)}")
    print(f"   短期记忆条目: {len(engine.short_term)}")
    print()
    
    # 扫描长期记忆
    for eid, entry in engine.long_term.items():
        # 时间过滤
        if entry.created_at < CUTOFF_TS:
            continue
        
        scanned_count += 1
        
        # 检查 sanitized_content 是否泄露
        original = entry.content
        sanitized = getattr(entry, 'sanitized_content', None) or original
        
        is_safe = PrivacySanitizer.validate_no_leakage(original, sanitized)
        
        if not is_safe:
            # 评估风险等级
            risk = "LOW"
            if any(kw in original.lower() for kw in ['sk-', 'bearer', 'password', 'token']):
                risk = "HIGH"
            elif any(kw in original.lower() for kw in ['api_key', 'secret', 'private']):
                risk = "MEDIUM"
            
            leaks_found.append({
                "id": eid,
                "risk": risk,
                "original_snippet": original[:80],
                "sanitized_snippet": sanitized[:80],
                "protection_level": entry.protection_level,
                "created_at": entry.created_at,
            })
            risk_levels[risk] += 1
    
    # 输出报告
    print("=" * 60)
    print(" 存量扫描报告")
    print("=" * 60)
    print(f"扫描记录数:     {scanned_count}")
    print(f"发现泄露数:     {len(leaks_found)}")
    print(f"  - 高风险:     {risk_levels['HIGH']}")
    print(f"  - 中风险:     {risk_levels['MEDIUM']}")
    print(f"  - 低风险:     {risk_levels['LOW']}")
    print()
    
    if leaks_found:
        print("[!]  泄露详情（前5条）:")
        for item in leaks_found[:5]:
            print(f"  [{item['risk']}] {item['id']}")
            print(f"    原文: {item['original_snippet']}")
            print(f"    脱敏: {item['sanitized_snippet']}")
            print(f"    保护级别: {item['protection_level']}")
            print()
    else:
        print("[OK] 未发现隐私泄露")
        print("   所有 sanitized_content 均通过 validate_no_leakage 校验")
    print("=" * 60)
    
    # 输出 JSON 供程序化读取
    result = {
        "scanned": scanned_count,
        "leaks": len(leaks_found),
        "risk_breakdown": risk_levels,
        "highest_risk": "NONE" if not leaks_found else max(
            leaks_found, key=lambda x: {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(x["risk"], 0)
        )["risk"],
        "leak_samples": leaks_found[:5],
    }
    
    output_path = Path(WORKSPACE) / "scan_report.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n 完整报告已保存: {output_path}")
    
    return len(leaks_found) == 0

if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
