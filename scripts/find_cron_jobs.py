"""
搜索并列出所有TU-8相关的cron定时器
"""

import os
import pathlib
import json

# 搜索路径
search_paths = [
    pathlib.Path('C:/Users/qq366410837/.qclaw'),
    pathlib.Path('D:/qq366410837/.qclaw/workspace')
]

found_jobs = []

for search_path in search_paths:
    if not search_path.exists():
        continue
    
    for json_file in search_path.rglob('*.json'):
        try:
            # 跳过太大的文件
            if json_file.stat().st_size > 50000:
                continue
            
            # 读取JSON文件
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 检查是否包含定时器配置
            if isinstance(data, dict):
                # 检查常见的定时器配置字段
                if 'name' in data or 'jobName' in data or 'task' in data:
                    name = data.get('name', data.get('jobName', ''))
                    
                    # 检查是否与TU-8相关
                    if 'TU-8' in name or '五级' in name or '复盘' in name or 'retrospective' in name.lower():
                        found_jobs.append({
                            'file': str(json_file),
                            'name': name,
                            'schedule': data.get('schedule', data.get('cron', '')),
                            'data': data
                        })
        
        except Exception as e:
            # 跳过无法读取的文件
            pass

# 输出结果
if found_jobs:
    print(f"找到 {len(found_jobs)} 个TU-8相关的定时器配置：\n")
    for i, job in enumerate(found_jobs, 1):
        print(f"{i}. 文件: {job['file']}")
        print(f"   名称: {job['name']}")
        print(f"   调度: {job['schedule']}")
        print()
else:
    print("未找到TU-8相关的定时器配置文件")
    print("\n可能定时器配置存储在其他位置，或者只包含执行记录而不包含配置。")
