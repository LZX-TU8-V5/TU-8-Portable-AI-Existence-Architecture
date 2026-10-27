#!/usr/bin/env python3
"""批量文件整理器 - 根据分析结果整理文件到知识库"""
import os
import json
import shutil
from datetime import datetime

workspace = r'D:\qq366410837\.qclaw\workspace'
kb_root = os.path.join(workspace, 'knowledge_base')
analysis_path = os.path.join(kb_root, 'file_analysis.json')
index_path = os.path.join(kb_root, 'INDEX.json')

# 加载分析结果
with open(analysis_path, encoding='utf-8') as f:
    results = json.load(f)

# 加载索引
with open(index_path, encoding='utf-8') as f:
    index = json.load(f)

print(f'加载 {len(results)} 个文件的分析结果')

# 按类别分组
categories = {}
for r in results:
    cat = r['category']
    if cat not in categories:
        categories[cat] = []
    categories[cat].append(r)

# 处理每类文件
for cat, files in categories.items():
    print(f'\n=== 处理 {cat} ({len(files)} 个文件) ===')
    
    # 创建类别目录
    cat_dir = os.path.join(kb_root, cat)
    os.makedirs(cat_dir, exist_ok=True)
    
    # 处理前 5 个文件作为示例
    for i, r in enumerate(files[:5]):
        fpath = r['file']
        relpath = r['relative_path']
        tags = r['tags']
        size_kb = r['size'] / 1024
        
        print(f'\n  [{i+1}] {relpath}')
        print(f'      标签: {tags}')
        print(f'      大小: {size_kb:.1f}KB')
        
        # 判断处理方式
        if cat == '04_TEMP':
            action = 'ARCHIVE'
        elif cat == '00_CORE':
            action = 'KEEP'
        elif cat == '03_TEST':
            action = 'MOVE_TO_TESTS'
        else:
            action = 'INDEX_ONLY'
        
        print(f'      建议操作: {action}')
        
        # 记录到索引
        index['files'][relpath] = {
            'category': cat,
            'tags': tags,
            'size_kb': size_kb,
            'action': action,
            'analyzed_at': datetime.now().isoformat(),
        }

# 保存更新后的索引
with open(index_path, 'w', encoding='utf-8') as f:
    json.dump(index, f, ensure_ascii=False, indent=2)

print(f'\n索引已更新: {index_path}')
print('示例处理完成。确认后继续批量处理...')
