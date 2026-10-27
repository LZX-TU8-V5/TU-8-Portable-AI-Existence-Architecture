#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证 index.md 是否包含所有文件
如果有缺失，将它们添加到索引中
"""

import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent
INDEX_FILE = BASE_DIR / "index.md"

# 要排除的目录/文件
EXCLUDE_DIRS = {'__pycache__', '.git', 'node_modules'}
EXCLUDE_FILES = {'index.md', 'verify_index.py'}

def get_actual_files():
    """获取实际所有文件（相对路径）"""
    files = set()
    for root, dirs, filenames in os.walk(BASE_DIR):
        # 排除目录
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for filename in filenames:
            if filename in EXCLUDE_FILES:
                continue
            
            file_path = Path(root) / filename
            rel_path = file_path.relative_to(BASE_DIR)
            files.add(str(rel_path))
    
    return files

def get_indexed_files():
    """从 index.md 中提取已索引的文件"""
    if not INDEX_FILE.exists():
        return set()
    
    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 提取反引号中的文件路径
    files = set(re.findall(r'`([^`]+\.[a-zA-Z0-9]+)`', content))
    return files

def main():
    print("[INFO] 获取实际所有文件...")
    actual_files = get_actual_files()
    print(f"[INFO] 实际文件数: {len(actual_files)}")
    
    print("[INFO] 获取已索引文件...")
    indexed_files = get_indexed_files()
    print(f"[INFO] 已索引文件数: {len(indexed_files)}")
    
    # 找出缺失的文件
    missing = actual_files - indexed_files
    print(f"\n=== 验证结果 ===")
    print(f"缺失文件数: {len(missing)}")
    
    if not missing:
        print("[SUCCESS] 所有文件都已索引！")
        return
    
    print(f"\n缺失文件列表（前20个）:")
    for f in sorted(missing)[:20]:
        print(f"  - {f}")
    
    # 将缺失文件添加到 index.md
    print(f"\n[INFO] 将缺失文件添加到 index.md...")
    
    # 读取现有内容
    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 在 "所有文件列表" 章节后添加缺失文件
    # 简单处理：在文件末尾添加
    append_content = "\n\n### 补充文件（自动添加）\n"
    for f in sorted(missing):
        append_content += f"- `{f}`\n"
    
    with open(INDEX_FILE, 'a', encoding='utf-8') as f:
        f.write(append_content)
    
    print(f"[SUCCESS] 已添加 {len(missing)} 个缺失文件到 index.md！")

if __name__ == "__main__":
    main()
