#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TU-8 方法论索引自动生成脚本
扫描 L2 目录，读取 YAML Front Matter，生成 00_Kernel/00_index.md
"""

import os
import re
import yaml
import shutil
from datetime import datetime
from pathlib import Path

# 配置
BASE_DIR = Path(__file__).parent
L2_DIR = BASE_DIR / "L2"
OUTPUT_FILE = BASE_DIR / "00_Kernel" / "00_index.md"
BACKUP_DIR = BASE_DIR / "00_Kernel" / "archive"

# 确保输出目录存在
OUTPUT_FILE.parent.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)


def create_snapshot():
    """
    创建索引表的版本快照
    在重写索引表之前，自动备份旧版本到 archive 文件夹
    """
    # 1. 检查主文件是否存在
    if not OUTPUT_FILE.exists():
        print("[INFO] 索引文件不存在，跳过快照。")
        return
    
    # 2. 生成带时间戳的文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    snapshot_name = f"index_{timestamp}.md"
    snapshot_path = BACKUP_DIR / snapshot_name
    
    # 3. 执行复制（保留元数据）
    shutil.copy2(OUTPUT_FILE, snapshot_path)
    print(f"[SNAPSHOT] 快照已保存: {snapshot_path}")
    
    # 4. 清理旧快照（保留最近30天，最多50个版本）
    snapshots = sorted(BACKUP_DIR.glob("index_*.md"), key=lambda x: x.stat().st_mtime, reverse=True)
    
    # 删除超过50个的旧快照
    if len(snapshots) > 50:
        for old_snapshot in snapshots[50:]:
            old_snapshot.unlink()
            print(f"[CLEANUP] 删除旧快照: {old_snapshot.name}")
    
    # 删除超过30天的快照
    from datetime import timedelta
    cutoff_time = datetime.now().timestamp() - (30 * 24 * 60 * 60)
    for snapshot in snapshots:
        if snapshot.stat().st_mtime < cutoff_time:
            snapshot.unlink()
            print(f"[CLEANUP] 删除过期快照: {snapshot.name}")

def scan_and_generate():
    """扫描 L2 目录并生成索引表"""
    
    # 📸 先创建快照（备份当前版本）
    create_snapshot()
    
    index_data = []
    
    # 遍历 L2 目录下的所有 markdown 文件
    for root, _, files in os.walk(L2_DIR):
        for file in files:
            if file.endswith(".md"):
                file_path = Path(root) / file
                rel_path = file_path.relative_to(BASE_DIR)
                
                with open(file_path, 'r', encoding='utf-8-sig') as f:  # utf-8-sig 自动处理 BOM
                    content = f.read()
                    
                    # 提取 YAML Front Matter (允许开头有空白)
                    match = re.match(r'^\s*---\n(.*?)\n---', content, re.DOTALL)
                    if match:
                        try:
                            meta = yaml.safe_load(match.group(1))
                            # 只提取需要的字段
                            index_data.append({
                                "id": meta.get('id', 'N/A'),
                                "category": meta.get('category', 'N/A'),
                                "priority": meta.get('priority', 'NORMAL'),
                                "title": meta.get('title', file_path.stem),
                                "description": meta.get('description', '无描述'),
                                "tags": meta.get('tags', []),
                                "trigger_keywords": meta.get('trigger_keywords', []),
                                "path": str(rel_path)
                            })
                        except Exception as e:
                            print(f"[ERROR] 解析文件 {file_path} 失败: {e}")
                    else:
                        print(f"[WARN] 文件 {file_path} 缺少 YAML Front Matter")
    
    # 按 ID 排序
    index_data.sort(key=lambda x: x['id'])
    
    # 生成 Markdown 表格
    md_content = f"""# 📚 TU-8 方法论核心索引表

> **自动生成，请勿手动修改**
> 生成时间: {Path(__file__).stat().st_mtime}
> 脚本路径: `generate_index.py`

---

## 统计信息

| 项目 | 数量 |
|------|------|
| 总方法论数 | {len(index_data)} |
| CRITICAL 级 | {sum(1 for x in index_data if x['priority'] == 'CRITICAL')} |
| HIGH 级 | {sum(1 for x in index_data if x['priority'] == 'HIGH')} |
| NORMAL 级 | {sum(1 for x in index_data if x['priority'] == 'NORMAL')} |

---

## 索引表格

| 编号 | 分类 | 优先级 | 标题 | 一句话简介 | 触发词 | 路径 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
    
    for item in index_data:
        trigger_str = ", ".join(item['trigger_keywords']) if item['trigger_keywords'] else "-"
        md_content += f"| {item['id']} | {item['category']} | {item['priority']} | {item['title']} | {item['description']} | {trigger_str} | `{item['path']}` |\n"
    
    md_content += """

---

## 使用说明

1. **触发词匹配**：当用户输入包含"触发词"列中的关键词时，自动加载对应方法论
2. **优先级**：
   - `CRITICAL`：必须无条件执行，违反即任务失败
   - `HIGH`：优先采用，强烈推荐
   - `NORMAL`：按需查阅，参考使用
3. **自动更新**：修改 L2 目录下的任何 .md 文件后，运行 `python generate_index.py` 更新本表

---

*本文件由 `generate_index.py` 自动生成，最后更新: 2026-05-27*
"""
    
    # 写入文件
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"[SUCCESS] 索引表已更新！共收录 {len(index_data)} 条方法论。")
    print(f"          输出路径: {OUTPUT_FILE}")

if __name__ == "__main__":
    scan_and_generate()
