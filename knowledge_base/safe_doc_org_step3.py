#!/usr/bin/env python3
"""
安全文档整理 - 步骤3：测试引用
验证更新后的引用是否指向有效文件
"""
import os
import json

workspace = r'D:\qq366410837\.qclaw\workspace'
kb_root = os.path.join(workspace, 'knowledge_base')

print('=== 步骤3：测试引用 ===\n')

# 加载更新日志
log_path = os.path.join(kb_root, 'step2_update_log.json')
with open(log_path, encoding='utf-8') as f:
    log = json.load(f)

updated_files = log.get('updated', [])
print(f'需要测试 {len(updated_files)} 个已更新的文件\n')

# 测试每个文件的引用
test_results = {
    'valid': [],  # 引用有效
    'broken': [],  # 引用损坏
    'file_missing': [],  # 文件不存在
}

for relpath in updated_files:
    fpath = os.path.join(workspace, relpath)
    
    if not os.path.exists(fpath):
        test_results['file_missing'].append(relpath)
        continue
    
    try:
        with open(fpath, encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # 查找所有看起来像引用路径的模式
        # 匹配 ../knowledge_base/ 或 knowledge_base/ 开头的路径
        import re
        ref_pattern = r'(?:\.\.\/knowledge_base\/|knowledge_base\/)[^\s\)\]\}]+'
        found_refs = re.findall(ref_pattern, content)
        
        broken_in_file = []
        for ref in found_refs:
            # 转换为绝对路径
            ref_abs = os.path.normpath(os.path.join(os.path.dirname(fpath), ref))
            if not os.path.exists(ref_abs):
                broken_in_file.append((ref, ref_abs))
        
        if broken_in_file:
            test_results['broken'].append({
                'file': relpath,
                'broken_refs': broken_in_file,
            })
        else:
            test_results['valid'].append(relpath)
    
    except Exception as e:
        test_results['broken'].append({
            'file': relpath,
            'error': str(e),
        })

# 输出测试结果
print('=== 测试结果 ===\n')
print(f'[OK] 引用有效: {len(test_results["valid"])} 个文件')
if test_results['valid']:
    for f in test_results['valid'][:5]:
        print(f'  - {f}')
    if len(test_results['valid']) > 5:
        print(f'  ... 还有 {len(test_results["valid"])-5} 个')

print(f'\n[FAIL] 引用损坏: {len(test_results["broken"])} 个文件')
if test_results['broken']:
    for item in test_results['broken'][:5]:
        print(f'  - {item["file"]}')
        if 'broken_refs' in item:
            for ref, abs_path in item['broken_refs'][:3]:
                print(f'      {ref} (文件不存在: {abs_path})')
        if 'error' in item:
            print(f'      错误: {item["error"]}')
    if len(test_results['broken']) > 5:
        print(f'  ... 还有 {len(test_results["broken"])-5} 个')

print(f'\n[MISSING] 文件不存在: {len(test_results["file_missing"])} 个')
if test_results['file_missing']:
    for f in test_results['file_missing']:
        print(f'  - {f}')

# 保存测试结果
result_path = os.path.join(kb_root, 'step3_test_result.json')
with open(result_path, 'w', encoding='utf-8') as f:
    json.dump(test_results, f, ensure_ascii=False, indent=2)

print(f'\n测试结果已保存: {result_path}')

# 判断是否可以进入步骤4
if test_results['broken'] or test_results['file_missing']:
    print('\n[警告] 存在损坏的引用或缺失的文件！')
    print('建议：修复引用后再继续')
    print('\n下一步：修复引用（执行 fix_broken_refs.py）')
else:
    print('\n[OK] 所有引用测试通过！')
    print('\n下一步：执行步骤4（删除源文件）')
    print('注意：源文件仍在 docs/ 目录中，确认测试无误后可删除。')
