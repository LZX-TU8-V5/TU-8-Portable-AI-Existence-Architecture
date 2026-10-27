#!/usr/bin/env python3
"""执行文档整理计划"""
import os
import shutil
import json

workspace = r'D:\qq366410837\.qclaw\workspace'
kb_root = os.path.join(workspace, 'knowledge_base')
plan_path = os.path.join(kb_root, 'doc_organization_plan.json')

# 加载计划
with open(plan_path, encoding='utf-8') as f:
    plan = json.load(f)

print('=== 执行文档整理 ===\n')

# 创建目标目录结构
new_kb_root = os.path.join(kb_root, 'knowledge')
categories = {
    '01_DESIGN': '设计文档',
    '02_IMPLEMENTATION': '实现记录',
    '03_REVIEW': '审查评审',
    '04_GUIDE': '指南文档',
    '05_ARCHIVE': '归档文档',
    '06_AGENT_MEMORY': 'Agent 记忆',
}

for cat in categories:
    cat_dir = os.path.join(new_kb_root, cat)
    os.makedirs(cat_dir, exist_ok=True)
    print(f'  ✓ {cat}: {categories[cat]}')

print(f'\n1. 移动 docs/ 文件到新知识库...\n')

moved = []
failed = []

for item in plan['docs_to_move']:
    fname = item['file']
    src = os.path.join(workspace, 'docs', fname)
    dst_dir = os.path.join(new_kb_root, item['to'].replace('knowledge/', ''))
    dst = os.path.join(dst_dir, fname)
    
    if not os.path.exists(src):
        print(f'  [SKIP] 源文件不存在: {fname}')
        continue
    
    try:
        shutil.move(src, dst)
        moved.append((fname, item['to']))
        print(f'  [MOVED] {fname} -> {item["to"]}')
    except Exception as e:
        failed.append((fname, str(e)))
        print(f'  [FAILED] {fname}: {e}')

print(f'\n成功移动: {len(moved)} 个')
if failed:
    print(f'失败: {len(failed)} 个')

print(f'\n2. 整理 knowledge/TU-8/ 目录...\n')

# 整理 knowledge/TU-8/ 到 06_AGENT_MEMORY/
tu8_knowledge = os.path.join(workspace, 'knowledge', 'TU-8')
agent_memory_dst = os.path.join(new_kb_root, '06_AGENT_MEMORY')

if os.path.exists(tu8_knowledge):
    # 移动关键子目录
    key_dirs = [
        '_agent_memory',
        '_shield_experience',
        '00_Kernel',
        'L2',
    ]
    
    for d in key_dirs:
        src_dir = os.path.join(tu8_knowledge, d)
        if os.path.exists(src_dir):
            dst_dir = os.path.join(agent_memory_dst, d)
            try:
                if os.path.exists(dst_dir):
                    print(f'  [SKIP] 目标已存在: {d}')
                else:
                    shutil.move(src_dir, dst_dir)
                    print(f'  [MOVED] {d}/ -> 06_AGENT_MEMORY/{d}/')
            except Exception as e:
                print(f'  [FAILED] {d}: {e}')
    
    print(f'\n3. 处理 scripts/ 目录...\n')
    
    # scripts/ 目录可能有临时脚本，检查后决定
    scripts_dir = os.path.join(tu8_knowledge, 'scripts')
    if os.path.exists(scripts_dir):
        script_files = os.listdir(scripts_dir)
        print(f'  找到 {len(script_files)} 个脚本文件')
        print(f'  建议：这些脚本可能是临时工具，移到 05_ARCHIVE/')
        
        archive_scripts = os.path.join(new_kb_root, '05_ARCHIVE', 'scripts')
        os.makedirs(archive_scripts, exist_ok=True)
        
        for f in script_files:
            src = os.path.join(scripts_dir, f)
            dst = os.path.join(archive_scripts, f)
            try:
                shutil.move(src, dst)
                print(f'    [ARCHIVED] {f}')
            except Exception as e:
                print(f'    [FAILED] {f}: {e}')

print(f'\n=== 整理完成 ===')
print(f'移动文档: {len(moved)} 个')
print(f'Agent 记忆: 已整理到 06_AGENT_MEMORY/')
print(f'脚本文件: 已归档到 05_ARCHIVE/scripts/')

# 保存操作日志
log = {
    'action': 'organize_docs_and_knowledge',
    'moved_docs': moved,
    'failed': failed,
    'timestamp': '__TIMESTAMP__',
}
log_path = os.path.join(kb_root, 'doc_organization_log.json')
with open(log_path, 'w', encoding='utf-8') as f:
    json.dump(log, f, ensure_ascii=False, indent=2)

print(f'\n日志已保存: {log_path}')
print('\n下一步：创建知识库索引，生成知识地图')
