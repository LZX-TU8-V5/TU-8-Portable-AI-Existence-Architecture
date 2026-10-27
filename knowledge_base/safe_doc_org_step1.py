#!/usr/bin/env python3
"""
安全文档整理 - 四步法
1. 复制文件到新位置（不删除源文件）
2. 扫描并更新引用
3. 测试引用是否正确
4. 确认后删除源文件
"""
import os
import shutil
import json
import re

workspace = r'D:\qq366410837\.qclaw\workspace'
kb_root = os.path.join(workspace, 'knowledge_base')
plan_path = os.path.join(kb_root, 'doc_organization_plan.json')

# 加载计划
with open(plan_path, encoding='utf-8') as f:
    plan = json.load(f)

print('=== 安全文档整理（四步法）===\n')

# 步骤 1: 复制文件到新位置
print('【步骤 1/4】复制文件到新位置...\n')

new_kb_root = os.path.join(kb_root, 'knowledge')
copied = []
failed_copy = []

for item in plan['docs_to_move']:
    fname = item['file']
    src = os.path.join(workspace, 'docs', fname)
    dst_dir = os.path.join(new_kb_root, item['to'].replace('knowledge/', ''))
    dst = os.path.join(dst_dir, fname)
    
    if not os.path.exists(src):
        print(f'  [SKIP] 源文件不存在: {fname}')
        continue
    
    try:
        os.makedirs(dst_dir, exist_ok=True)
        shutil.copy2(src, dst)  # copy2 保留元数据
        copied.append({
            'file': fname,
            'from': src,
            'to': dst,
            'relative_to': item['to'],
        })
        print(f'  [COPIED] {fname} -> {item["to"]}')
    except Exception as e:
        failed_copy.append((fname, str(e)))
        print(f'  [FAILED] {fname}: {e}')

print(f'\n复制完成: {len(copied)} 个文件')
if failed_copy:
    print(f'失败: {len(failed_copy)} 个')

# 步骤 2: 扫描引用
print(f'\n【步骤 2/4】扫描引用（哪些文件引用了这些文档）...\n')

# 收集所有需要检查的引用
# 文档可能被 .md 文件通过相对路径引用
files_to_scan = []
for root, dirs, files in os.walk(workspace):
    # 跳过知识库新目录
    if 'knowledge_base' in root:
        continue
    for f in files:
        if f.endswith('.md') or f.endswith('.py'):
            files_to_scan.append(os.path.join(root, f))

print(f'将扫描 {len(files_to_scan)} 个文件以查找引用...')

# 查找引用
references_found = {}
for item in copied:
    fname = item['file']
    references_found[fname] = []
    
    for scan_file in files_to_scan:
        try:
            with open(scan_file, encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 检查是否引用了该文件
            if fname in content:
                relpath = os.path.relpath(scan_file, workspace)
                references_found[fname].append(relpath)
        except:
            pass

# 显示引用情况
print('\n引用扫描结果:')
for fname, refs in references_found.items():
    if refs:
        print(f'  {fname}: 被 {len(refs)} 个文件引用')
        for ref in refs[:3]:
            print(f'    - {ref}')
        if len(refs) > 3:
            print(f'    ... 还有 {len(refs)-3} 个')
    else:
        print(f'  {fname}: 未被引用（可安全删除）')

# 保存引用信息
ref_path = os.path.join(kb_root, 'references_found.json')
with open(ref_path, 'w', encoding='utf-8') as f:
    json.dump(references_found, f, ensure_ascii=False, indent=2)

print(f'\n引用信息已保存: {ref_path}')

# 步骤 3: 生成更新引用的脚本
print(f'\n【步骤 3/4】生成更新引用的脚本...\n')

# 对于每个有引用的文件，生成更新脚本
update_plan = []
for fname, refs in references_found.items():
    if not refs:
        continue
    
    # 找到该文件的新位置
    item = next((i for i in copied if i['file'] == fname), None)
    if not item:
        continue
    
    new_relpath = os.path.relpath(item['to'], workspace)
    
    for ref_file in refs:
        update_plan.append({
            'file': ref_file,
            'old_ref': fname,
            'new_ref': os.path.relpath(item['to'], os.path.dirname(os.path.join(workspace, ref_file))),
        })

print(f'需要更新 {len(update_plan)} 处引用')

if update_plan:
    print('\n示例更新:')
    for item in update_plan[:5]:
        print(f'  文件: {item["file"]}')
        print(f'    旧引用: {item["old_ref"]}')
        print(f'    新引用: {item["new_ref"]}')
        print()

# 保存更新计划
update_plan_path = os.path.join(kb_root, 'update_references_plan.json')
with open(update_plan_path, 'w', encoding='utf-8') as f:
    json.dump(update_plan, f, ensure_ascii=False, indent=2)

print(f'更新计划已保存: {update_plan_path}')

print(f'\n【步骤 4/4】等待确认...\n')
print('当前状态：')
print(f'  1. ✓ 已复制 {len(copied)} 个文件到新位置')
print(f'  2. ✓ 已扫描引用，找到 {len(update_plan)} 处需要更新')
print(f'  3. ? 需要更新引用（执行 update_references.py）')
print(f'  4. ? 需要测试')
print(f'  5. ? 最后才删除源文件')
print('\n下一步：执行引用更新脚本')
