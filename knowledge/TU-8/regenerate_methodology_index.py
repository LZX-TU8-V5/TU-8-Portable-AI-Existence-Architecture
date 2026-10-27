#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重新生成 METHODOLOGY_INDEX.md
读取 L2 目录下所有 .md 文件，提取标题，生成索引
"""

import os
import re
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
L2_DIR = BASE_DIR / "L2"
OUTPUT_FILE = BASE_DIR / "METHODOLOGY_INDEX.md"

def read_file_title(file_path):
    """读取文件第一行作为标题（# 标题）"""
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            for line in f:
                line = line.strip()
                if line.startswith('# '):
                    return line[2:].strip()
        return file_path.stem
    except:
        return file_path.stem

def generate_methodology_index():
    """生成 METHODOLOGY_INDEX.md 内容"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    content = f"""# 方法论索引清单

> 本文件自动生成，汇总所有方法论
> 生成时间: {now}

---

"""
    
    # 遍历 L2 目录下的所有 .md 文件
    md_files = sorted(L2_DIR.glob("*.md"))
    
    # 按编号分组（01_meta.md → 01_meta）
    groups = {}
    for file in md_files:
        if file.name == "index.md":
            continue
        
        # 提取编号和名称（01_meta.md → 01_meta）
        name = file.stem
        if '_' in name and len(name) > 3:
            group_key = name.split('_')[0]  # 01
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append((name, read_file_title(file)))
        else:
            # 无编号的文件
            if 'other' not in groups:
                groups['other'] = []
            groups['other'].append((name, read_file_title(file)))
    
    # 生成索引内容
    for group_key in sorted(groups.keys()):
        # 组标题（用第一个文件的标题）
        if group_key != 'other':
            # 尝试读取组目录（如果有 index.md）
            group_index = L2_DIR / group_key / "index.md"
            if group_index.exists():
                group_title = read_file_title(group_index)
            else:
                # 用第一个文件的标题作为组标题
                group_title = groups[group_key][0][1] if groups[group_key] else group_key
        else:
            group_title = "其他"
        
        content += f"## {group_key}_{group_title}\n\n"
        
        # 列出组内所有文件
        for file_name, title in groups[group_key]:
            content += f"- {file_name}.md: {title}\n"
        
        content += "\n"
    
    content += f"---\n\n**最后更新**: {now}\n**更新者**: TU-8 Agent（自动生成）\n"
    
    return content

def main():
    print("[INFO] 生成方法论索引...")
    content = generate_methodology_index()
    
    print(f"[INFO] 写入 {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"[SUCCESS] 方法论索引已重新生成！")

if __name__ == "__main__":
    main()
