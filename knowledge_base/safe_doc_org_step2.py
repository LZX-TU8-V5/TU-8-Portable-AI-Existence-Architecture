#!/usr/bin/env python3
"""
安全文档整理 - 步骤2：更新引用
只更新活动文件，跳过备份目录
"""
import os
import json
import re

workspace = r'D:\qq366410837\.qclaw\workspace'
kb_root = os.path.join(workspace, 'knowledge_base')

# 加载引用信息
ref_path = os.path.join(kb_root, 'references_found.json')
with open(ref_path, encoding='utf-8') as f:
    references_found = json.load(f)

print('=== 步骤2：更新引用 ===\n')
print('过滤规则：跳过 backup/ 和 knowledge_base/ 目录\n')

# 筛选需要更新的引用（排除备份）
active_updates = []
skipped = 0

for fname, refs in references_found.items():
    for ref_file in refs:
        # 跳过备份目录
        if 'backup' in ref_file or 'knowledge_base' in ref_file:
            skipped += 1
            continue
        
        # 找到该文件的新位置
        copied_list_path = os.path.join(kb_root, 'doc_organization_plan.json')
        with open(copied_list_path, encoding='utf-8') as f:
            plan = json.load(f)
        
        item = next((i for i in plan['docs_to_move'] if i['file'] == fname), None)
        if not item:
            continue
        
        # 计算新引用路径
        new_location = os.path.join(workspace, 'knowledge_base', 'knowledge', 
                                  item['to'].replace('knowledge/', ''), fname)
        ref_file_full = os.path.join(workspace, ref_file)
        
        if os.path.exists(ref_file_full):
            new_relpath = os.path.relpath(new_location, os.path.dirname(ref_file_full))
            
            active_updates.append({
                'ref_file': ref_file,
                'old_ref': fname,
                'new_ref': new_relpath.replace('\\', '/'),  # 统一用正斜杠
            })

print(f'需要更新的引用: {len(active_updates)} 处')
print(f'跳过的引用（备份）: {skipped} 处\n')

if not active_updates:
    print('[OK] 没有活动文件需要更新引用！')
    print('这意味着所有引用都在备份目录中，文档可以安全移动。')
else:
    print('需要更新的文件:')
    for item in active_updates:
        print(f'  {item["ref_file"]}')
        print(f'    {item["old_ref"]} -> {item["new_ref"]}\n')
    
    # 执行更新
    print('开始更新引用...\n')
    
    updated = []
    failed = []
    
    for item in active_updates:
        ref_file = item['ref_file']
        ref_file_full = os.path.join(workspace, ref_file)
        
        try:
            with open(ref_file_full, encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 替换引用
            old_ref = item['old_ref']
            new_ref = item['new_ref']
            
            if old_ref in content:
                new_content = content.replace(old_ref, new_ref)
                
                # 写回文件
                with open(ref_file_full, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                updated.append(ref_file)
                print(f'  [UPDATED] {ref_file}')
            else:
                print(f'  [SKIP] 未找到引用: {ref_file} (可能已更新)')
        
        except Exception as e:
            failed.append((ref_file, str(e)))
            print(f'  [FAILED] {ref_file}: {e}')
    
    print(f'\n更新完成: {len(updated)} 个文件')
    if failed:
        print(f'失败: {len(failed)} 个')

# 保存更新日志
log = {
    'action': 'update_references',
    'updated': updated if active_updates else [],
    'failed': failed if active_updates else [],
    'skipped_backup_refs': skipped,
}
log_path = os.path.join(kb_root, 'step2_update_log.json')
with open(log_path, 'w', encoding='utf-8') as f:
    json.dump(log, f, ensure_ascii=False, indent=2)

print(f'\n日志已保存: {log_path}')

if not active_updates:
    print('\n[OK] 无需更新引用，可以进行步骤3（测试）')
else:
    print('\n下一步：执行步骤3（测试引用是否正确）')
