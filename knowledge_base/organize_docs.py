#!/usr/bin/env python3
"""
文档和知识库整理器
1. 分析 docs/ 和 knowledge/ 的内容
2. 建立清晰的知识库分类
3. 移动/归档文档到正确位置
"""
import os
import re

workspace = r'D:\qq366410837\.qclaw\workspace'
kb_root = os.path.join(workspace, 'knowledge_base')

print('=== 文档和知识库整理 ===\n')

# 1. 分析 docs/ 目录的文件内容
docs_dir = os.path.join(workspace, 'docs')
print('1. 分析 docs/ 目录...')

doc_categories = {
    'ARCHITECTURE': [],  # 架构设计
    'IMPLEMENTATION': [],  # 实现记录
    'REVIEW': [],  # 审查/评审
    'GUIDE': [],  # 指南/教程
    'TEMP': [],  # 临时/过期
}

for fname in os.listdir(docs_dir):
    if not fname.endswith('.md'):
        continue
    
    fpath = os.path.join(docs_dir, fname)
    if not os.path.isfile(fpath):
        continue
    
    # 读取文件内容判断类别
    try:
        with open(fpath, encoding='utf-8', errors='ignore') as f:
            content = f.read(2000)  # 只读前2000字符
        
        # 根据文件名和内容判断
        if 'ARCHITECTURE' in fname or 'architecture' in fname.lower():
            doc_categories['ARCHITECTURE'].append(fname)
        elif 'REVIEW' in fname or 'review' in fname.lower():
            doc_categories['REVIEW'].append(fname)
        elif 'GUIDE' in fname or 'guide' in fname.lower():
            doc_categories['GUIDE'].append(fname)
        elif 'OPEN_SOURCE' in fname:
            doc_categories['GUIDE'].append(fname)
        elif 'four_chain' in fname.lower():
            doc_categories['ARCHITECTURE'].append(fname)
        elif 'workspace_file_audit' in fname.lower():
            doc_categories['TEMP'].append(fname)  # 审计报表，可归档
        else:
            doc_categories['IMPLEMENTATION'].append(fname)
    except:
        doc_categories['TEMP'].append(fname)

print(f'  找到 {len([f for cat in doc_categories.values() for f in cat])} 个文档文件')
for cat, files in doc_categories.items():
    print(f'    {cat}: {len(files)} 个')
    for f in files[:3]:
        print(f'      - {f}')
    if len(files) > 3:
        print(f'      ... 还有 {len(files)-3} 个')

print('\n2. 分析 knowledge/TU-8/ 目录...')
# 2. 分析 knowledge/TU-8/ 目录
knowledge_dir = os.path.join(workspace, 'knowledge', 'TU-8')

knowledge_structure = {}
if os.path.exists(knowledge_dir):
    for root, dirs, files in os.walk(knowledge_dir):
        relpath = os.path.relpath(root, knowledge_dir)
        if files:
            knowledge_structure[relpath] = files
    
    print(f'  共 {len(knowledge_structure)} 个子目录')
    print('\n  关键目录:')
    
    key_dirs = [
        '',  # 根目录
        '00_Kernel',
        'L2',
        '_agent_memory',
        '_shield_experience',
        'scripts',
    ]
    
    for d in key_dirs:
        if d in knowledge_structure:
            files = knowledge_structure[d]
            print(f'    {d or "./"}: {len(files)} 个文件')
else:
    print('  knowledge/TU-8/ 目录不存在')

print('\n3. 建立知识库分类结构...')
# 3. 建立新的知识库分类
new_kb_structure = {
    '01_DESIGN': '设计文档（架构、层定义、协议）',
    '02_IMPLEMENTATION': '实现记录（开发日志、补丁说明）',
    '03_REVIEW': '审查评审（代码审查、外部建议）',
    '04_GUIDE': '指南文档（使用指南、开源指导）',
    '05_ARCHIVE': '归档文档（过时、已完成）',
    '06_AGENT_MEMORY': 'Agent 记忆（TU-8 记忆库）',
}

# 创建新的知识库目录
new_kb_root = os.path.join(kb_root, 'knowledge')
for cat in new_kb_structure:
    cat_dir = os.path.join(new_kb_root, cat)
    os.makedirs(cat_dir, exist_ok=True)

print('  创建了新的知识库目录结构:')
for cat, desc in new_kb_structure.items():
    print(f'    {cat}: {desc}')

# 4. 生成整理计划
print('\n4. 生成整理计划...')

plan = {
    'docs_to_move': [],
    'knowledge_to_reorganize': [],
    'duplicates_to_check': [],
}

# docs/ 文件分类
for cat, files in doc_categories.items():
    target_cat = {
        'ARCHITECTURE': '01_DESIGN',
        'IMPLEMENTATION': '02_IMPLEMENTATION',
        'REVIEW': '03_REVIEW',
        'GUIDE': '04_GUIDE',
        'TEMP': '05_ARCHIVE',
    }[cat]
    
    for f in files:
        plan['docs_to_move'].append({
            'file': f,
            'from': 'docs/',
            'to': f'knowledge/{target_cat}/',
            'reason': f'归类到 {cat}',
        })

print(f'  docs/ -> knowledge/: {len(plan["docs_to_move"])} 个文件')

# 保存计划
plan_path = os.path.join(kb_root, 'doc_organization_plan.json')
with open(plan_path, 'w', encoding='utf-8') as f:
    import json
    json.dump(plan, f, ensure_ascii=False, indent=2)

print(f'\n整理计划已保存: {plan_path}')
print('\n下一步：审查计划并执行移动')
