#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TU-8 架构文件回收脚本
每天定时运行，将过期的待删文件移入回收站

流程：
  1. 读取 .pending_deletion.jsonl
  2. 检查过期文件（3天缓冲）
  3. 移入回收站（自定义目录）
  4. 清理队列文件
  5. 清理回收站（7天缓冲）
"""

import json
import os
import shutil
import logging
from datetime import datetime, timedelta

# 配置日志（UTF-8编码）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)

# 配置路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.dirname(SCRIPT_DIR)

PENDING_QUEUE = os.path.join(WORKSPACE_DIR, ".pending_deletion.jsonl")
RECYCLE_BIN = os.path.join(WORKSPACE_DIR, ".arch_recycle_bin")
RECYCLE_RETENTION_DAYS = 7  # 回收站保留7天

def log(msg):
    """日志输出"""
    logger.info(msg)

def load_pending_queue():
    """读取待删队列"""
    if not os.path.exists(PENDING_QUEUE):
        return []
    
    records = []
    with open(PENDING_QUEUE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    log(f"警告：跳过无效JSON: {line}")
    
    return records

def save_pending_queue(records):
    """保存待删队列（只保留未过期记录）"""
    with open(PENDING_QUEUE, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

def move_to_recycle_bin(file_path, record):
    """移入回收站（带时间戳防冲突）"""
    if not os.path.exists(RECYCLE_BIN):
        os.makedirs(RECYCLE_BIN, exist_ok=True)
    
    # 生成唯一文件名（原文件名 + 标记时间）
    base_name = os.path.basename(file_path)
    marked_at = record.get("marked_at", datetime.now().isoformat())
    timestamp = marked_at.replace(":", "-").replace(".", "-")  # 文件名安全
    recycle_name = f"{base_name}__{timestamp}"
    
    recycle_path = os.path.join(RECYCLE_BIN, recycle_name)
    
    # 如果已存在，添加序号
    counter = 1
    while os.path.exists(recycle_path):
        recycle_name = f"{base_name}__{timestamp}__{counter}"
        recycle_path = os.path.join(RECYCLE_BIN, recycle_name)
        counter += 1
    
    # 移动文件
    shutil.move(file_path, recycle_path)
    
    # 写入元数据（记录原始路径、删除时间等）
    meta_path = recycle_path + ".meta.json"
    meta = {
        "original_path": file_path,
        "marked_at": record.get("marked_at"),
        "recycled_at": datetime.now().isoformat(),
        "delete_after": (datetime.now() + timedelta(days=RECYCLE_RETENTION_DAYS)).isoformat()
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    
    return recycle_path

def clean_recycle_bin():
    """清理回收站（超过7天的文件永久删除）"""
    if not os.path.exists(RECYCLE_BIN):
        return
    
    now = datetime.now()
    cleaned_count = 0
    cleaned_size = 0
    
    for item in os.listdir(RECYCLE_BIN):
        item_path = os.path.join(RECYCLE_BIN, item)
        
        # 跳过元数据文件
        if item.endswith(".meta.json"):
            continue
        
        # 读取元数据
        meta_path = item_path + ".meta.json"
        if not os.path.exists(meta_path):
            continue
        
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            
            delete_after = datetime.fromisoformat(meta.get("delete_after", "2099-01-01T00:00:00"))
            
            if now >= delete_after:
                # 过期，永久删除
                if os.path.isfile(item_path):
                    size = os.path.getsize(item_path)
                    os.remove(item_path)
                    cleaned_size += size
                elif os.path.isdir(item_path):
                    size = sum(f.stat().st_size for f in os.scandir(item_path) if f.is_file())
                    shutil.rmtree(item_path)
                    cleaned_size += size
                
                # 删除元数据
                os.remove(meta_path)
                cleaned_count += 1
        
        except Exception as e:
            log(f"警告：清理回收站项目失败 {item}: {e}")
    
    if cleaned_count > 0:
        cleaned_size_mb = cleaned_size / (1024 * 1024)
        log(f"清理回收站：{cleaned_count} 个项目，释放 {cleaned_size_mb:.2f} MB")

def run_recycle():
    """主回收流程"""
    log("========== 架构文件回收开始 ==========")
    
    # 1. 加载待删队列
    records = load_pending_queue()
    if not records:
        log("无待删文件")
        # 即使没有待删文件，也要清理回收站
        clean_recycle_bin()
        log("========== 架构文件回收完成 ==========")
        return
    
    log(f"待删队列：{len(records)} 个文件")
    
    # 2. 分离过期和未过期记录
    now = datetime.now()
    expired_records = []
    remaining_records = []
    
    for record in records:
        delete_after = datetime.fromisoformat(record.get("delete_after", "2099-01-01T00:00:00"))
        
        if now >= delete_after:
            expired_records.append(record)
        else:
            remaining_records.append(record)
    
    log(f"过期文件：{len(expired_records)} 个")
    log(f"未过期文件：{len(remaining_records)} 个")
    
    # 3. 处理过期文件
    recycled_count = 0
    recycled_size = 0
    
    for record in expired_records:
        file_path = record.get("path")
        
        if not file_path or not os.path.exists(file_path):
            log(f"跳过不存在的文件：{file_path}")
            continue
        
        try:
            # 移入回收站
            recycle_path = move_to_recycle_bin(file_path, record)
            size = os.path.getsize(recycle_path)
            recycled_count += 1
            recycled_size += size
            log(f"移入回收站：{file_path} → {recycle_path}")
        
        except Exception as e:
            log(f"错误：处理文件失败 {file_path}: {e}")
    
    # 4. 更新待删队列（只保留未过期记录）
    save_pending_queue(remaining_records)
    
    # 5. 清理回收站（7天缓冲）
    clean_recycle_bin()
    
    # 6. 汇总报告
    recycled_size_mb = recycled_size / (1024 * 1024)
    log(f"========== 架构文件回收完成 ==========")
    log(f"回收文件：{recycled_count} 个，{recycled_size_mb:.2f} MB")
    log(f"剩余待删：{len(remaining_records)} 个")

if __name__ == "__main__":
    run_recycle()
