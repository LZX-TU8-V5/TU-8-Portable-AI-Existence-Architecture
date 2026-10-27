#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量自动生成 trigger_keywords 脚本 (v2 - 修复编码问题)
基于文件标题、描述、内容自动提取关键词
"""

import os
import re
import yaml
import sys
import io
from pathlib import Path

# Windows 控制台编码修复
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE_DIR = Path(__file__).parent
L2_DIR = BASE_DIR / "L2"

def extract_keywords_from_content(file_path):
    """从文件内容中提取关键词"""
    keywords = []
    
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    
    # 1. 从 YAML front matter 提取 title 和 description
    match = re.match(r'^\s*---\n(.*?)\n---', content, re.DOTALL)
    if match:
        try:
            meta = yaml.safe_load(match.group(1))
            title = meta.get('title', '')
            description = meta.get('description', '')
            
            # 从标题提取关键词（去掉编号和标点）
            if title:
                # 去掉 "1.1 " 这样的前缀
                clean_title = re.sub(r'^\d+(\.\d+)*\s*', '', title)
                keywords.append(clean_title)
                
                # 拆分标题中的中文词组
                words = re.findall(r'[\u4e00-\u9fa5]{2,}', clean_title)
                keywords.extend(words)
            
            # 从描述中提取关键词
            if description and len(description) > 10:
                words = re.findall(r'[\u4e00-\u9fa5]{2,}', description)
                keywords.extend(words[:3])  # 只取前3个
                
        except Exception as e:
            print(f"[WARN] 解析 {file_path.name} 的 YAML 失败: {e}")
    
    # 2. 从正文提取章节标题（## 开头的）
    headers = re.findall(r'^##\s+(.+)$', content, re.MULTILINE)
    for header in headers[:3]:  # 只取前3个章节标题
        clean_header = re.sub(r'^\d+(\.\d+)*\s*', '', header)
        keywords.append(clean_header)
    
    # 3. 去重并过滤太短的词（<2个字符）
    keywords = list(set([k.strip() for k in keywords if len(k.strip()) >= 2]))
    
    # 4. 限制最多8个关键词
    return keywords[:8]

def update_trigger_keywords():
    """更新所有 L2 文件的 trigger_keywords"""
    updated_count = 0
    
    for root, _, files in os.walk(L2_DIR):
        for file in files:
            if file.endswith('.md'):
                file_path = Path(root) / file
                
                # 读取文件
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    content = f.read()
                
                # 提取关键词
                keywords = extract_keywords_from_content(file_path)
                
                if not keywords:
                    print(f"[WARN] {file_path.name} 无法提取关键词，跳过")
                    continue
                
                # 更新 YAML front matter
                def replace_keywords(match):
                    # 保留其他字段，只替换 trigger_keywords
                    yaml_str = match.group(1)
                    try:
                        meta = yaml.safe_load(yaml_str)
                        meta['trigger_keywords'] = keywords
                        
                        # 重新生成 YAML 字符串
                        new_yaml = yaml.dump(meta, allow_unicode=True, default_flow_style=False)
                        return '---\n' + new_yaml + '---'
                    except Exception as e:
                        print(f"[ERROR] 更新 {file_path.name} 失败: {e}")
                        return match.group(0)  # 返回原内容
                
                new_content = re.sub(r'^\s*---\n(.*?)\n---', replace_keywords, content, flags=re.DOTALL)
                
                # 写回文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                updated_count += 1
                print(f"[SUCCESS] {file_path.name} 触发词已更新: {keywords}")
    
    print(f"\n[COMPLETE] 共更新 {updated_count} 个文件的 trigger_keywords")

if __name__ == "__main__":
    print("[START] 开始批量生成 trigger_keywords...\n")
    update_trigger_keywords()
    print("\n[NEXT] 下一步：运行 python generate_index.py 重新生成索引表")
