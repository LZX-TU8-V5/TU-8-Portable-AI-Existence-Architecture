#!/usr/bin/env python3
"""
文件知识提取器 - 逐个文件分析并贴标签
"""
import os
import re
import json
from datetime import datetime

workspace = r'D:\qq366410837\.qclaw\workspace'
kb_root = os.path.join(workspace, 'knowledge_base')
index_path = os.path.join(kb_root, 'INDEX.json')

# 标签体系
TAGS = {
    # 功能标签
    'CORE': '核心组件',
    'CHAIN_METABOLISM': '代谢链',
    'CHAIN_MEMORY': '记忆链', 
    'CHAIN_SEAL': '钢印链',
    'CHAIN_CONSCIOUSNESS': '意识循环链',
    'LAYER_L0': 'L0层',
    'LAYER_L1': 'L1层',
    'LAYER_L2': 'L2层',
    'LAYER_L4': 'L4层',
    'LAYER_L5': 'L5层',
    'COGNITION': '认知组件',
    'COLD_START': '冷启动',
    'EMOTION': '情感引擎',
    'SEAL': '钢印协议',
    'MEMORY': '记忆管理',
    'TEST': '测试文件',
    'TEMP': '临时文件',
    'PATCH': '补丁',
    'ARCHITECTURE': '架构文档',
    'LOG': '日志',
    'CONFIG': '配置',
    'SCRIPT': '脚本',
    'UNUSED': '未使用',
    'DEPRECATED': '已弃用',
}

def analyze_file(filepath):
    """分析单个文件，返回标签列表和摘要"""
    tags = []
    summary = ''
    
    fname = os.path.basename(filepath)
    ext = os.path.splitext(fname)[1].lower()
    
    # 1. 根据文件名判断
    if 'test_' in fname:
        tags.append('TEST')
    if 'patch_' in fname or 'fix_' in fname:
        tags.append('PATCH')
    if fname.startswith('_'):
        tags.append('TEMP')
    if 'backup' in fname or '.bak' in fname:
        tags.append('TEMP')
    
    # 2. 读取内容分析
    if ext in ['.py', '.ps1', '.md', '.json', '.txt']:
        try:
            with open(filepath, encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 检查关键词
            keywords = {
                'metabolism': 'CHAIN_METABOLISM',
                'memory': 'CHAIN_MEMORY',
                'seal': 'CHAIN_SEAL',
                'consciousness': 'CHAIN_CONSCIOUSNESS',
                'cold_start': 'COLD_START',
                'emotion': 'EMOTION',
                'cognitive': 'COGNITION',
                'L0': 'LAYER_L0',
                'L1': 'LAYER_L1',
                'L2': 'LAYER_L2',
                'L4': 'LAYER_L4',
                'L5': 'LAYER_L5',
            }
            for kw, tag in keywords.items():
                if kw.lower() in content.lower():
                    if tag not in tags:
                        tags.append(tag)
            
            # 提取前几行作为摘要
            lines = content.split('\n')[:10]
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('//'):
                    summary = line[:100]
                    break
            
        except Exception as e:
            summary = f'Read error: {e}'
    
    # 3. 判断核心组件
    core_files = [
        'tu8_memory.py', 'consciousness_cycle.py', 'user_metabolism.py',
        'life_ring_tracker.py', 'seal_protocol.py', 'emotion_engine.py',
        'cold_start_engine.py', 'cognitive_evaluator.py',
    ]
    if fname in core_files:
        tags.append('CORE')
    
    return tags, summary


def process_file(filepath):
    """处理单个文件：分析、贴标签、决定去处"""
    fname = os.path.basename(filepath)
    tags, summary = analyze_file(filepath)
    
    # 决定去处
    if 'CORE' in tags or 'ARCHITECTURE' in tags:
        category = '00_CORE'
    elif 'TEST' in tags:
        category = '03_TEST'
    elif 'TEMP' in tags or 'PATCH' in tags:
        category = '04_TEMP'
    elif 'LOG' in tags or 'DEPRECATED' in tags:
        category = '05_ARCHIVE'
    else:
        category = '01_DESIGN'
    
    result = {
        'file': filepath,
        'relative_path': os.path.relpath(filepath, workspace),
        'tags': tags,
        'summary': summary,
        'category': category,
        'size': os.path.getsize(filepath) if os.path.exists(filepath) else 0,
    }
    
    return result


def main():
    # 扫描工作区文件
    all_files = []
    for root, dirs, files in os.walk(workspace):
        # 跳过知识库目录本身
        if 'knowledge_base' in root:
            continue
        for f in files:
            filepath = os.path.join(root, f)
            all_files.append(filepath)
    
    print(f'Found {len(all_files)} files to analyze')
    
    # 逐个分析
    results = []
    for i, filepath in enumerate(all_files):
        result = process_file(filepath)
        results.append(result)
        
        if (i+1) % 10 == 0:
            print(f'  Analyzed {i+1}/{len(all_files)}: {os.path.basename(filepath)}')
    
    # 保存分析结果
    analysis_path = os.path.join(kb_root, 'file_analysis.json')
    with open(analysis_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f'\nAnalysis complete. Results saved to: {analysis_path}')
    print(f'Total files analyzed: {len(results)}')
    
    # 统计标签分布
    tag_count = {}
    for r in results:
        for tag in r['tags']:
            tag_count[tag] = tag_count.get(tag, 0) + 1
    
    print('\nTag distribution:')
    for tag, count in sorted(tag_count.items(), key=lambda x: x[1], reverse=True):
        print(f'  {tag}: {count}')


if __name__ == '__main__':
    main()
