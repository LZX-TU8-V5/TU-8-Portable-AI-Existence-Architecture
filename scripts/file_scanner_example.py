#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件扫描工具（集成系统心跳）
功能：展示如何在执行工具中"触发"系统心跳
作者：TU-8 Agent
日期：2026-06-20
版本：v0.1 (集成示例)
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime

# 导入系统心跳模块
from system_heartbeat import status_callback, get_heartbeat

# ================= 配置区 =================
WORKSPACE = Path("D:/qq366410837/.qclaw/workspace")

# ================= 核心类 =================
class FileScanner:
    """文件扫描器（集成系统心跳版本）"""
    
    def __init__(self, target_dir: str):
        self.target_dir = Path(target_dir)
        self.results = []
        self.errors = []
        
    def scan(self, max_files: int = 100):
        """
        扫描目标目录（集成状态回调）
        
        在关键节点触发 status_callback：
        - 扫描开始时：SCANNING_START
        - 遇到编码错误时：ENCODING_ERROR
        - 扫描超时时：SCAN_TIMEOUT
        - 扫描完成时：SCANNING_DONE
        """
        # 【触发点1】扫描开始时
        status_callback("SCANNING_START", operation="文件扫描", target=str(self.target_dir))
        
        start_time = time.time()
        timeout = 30  # 30秒超时
        
        try:
            # 检查目标目录是否存在
            if not self.target_dir.exists():
                raise FileNotFoundError(f"目录不存在: {self.target_dir}")
            
            # 递归扫描文件
            file_count = 0
            for file_path in self.target_dir.rglob("*"):
                # 【触发点2】检查超时
                if time.time() - start_time > timeout:
                    status_callback("SCAN_TIMEOUT", timeout=timeout)
                    print(f"[文件扫描] 扫描超时（{timeout}秒），终止扫描")
                    break
                
                if file_path.is_file():
                    try:
                        # 尝试读取文件（可能触发编码错误）
                        self.process_file(file_path)
                        file_count += 1
                        
                        if file_count >= max_files:
                            print(f"[文件扫描] 已达到最大文件数 {max_files}，停止扫描")
                            break
                            
                    except UnicodeDecodeError as e:
                        # 【触发点3】编码错误
                        status_callback(
                            "ENCODING_ERROR",
                            error_msg=str(e),
                            file_path=str(file_path)
                        )
                        self.errors.append({
                            "file": str(file_path),
                            "error": str(e)
                        })
                        # 继续处理其他文件（不中断）
                        continue
                        
                    except Exception as e:
                        # 【触发点4】其他错误
                        status_callback(
                            "FILE_READ_ERROR",
                            file_path=str(file_path),
                            error_type=type(e).__name__
                        )
                        self.errors.append({
                            "file": str(file_path),
                            "error": str(e)
                        })
                        continue
            
            # 【触发点5】扫描完成时
            status_callback("SCANNING_DONE", operation="文件扫描", count=file_count)
            
            print(f"[文件扫描] 扫描完成：处理了 {file_count} 个文件，遇到 {len(self.errors)} 个错误")
            
        except Exception as e:
            # 【触发点6】严重错误（如目录不存在）
            status_callback(
                "FILE_READ_ERROR",
                file_path=str(self.target_dir),
                error_type=type(e).__name__
            )
            print(f"[文件扫描] 扫描失败: {e}")
            
    def process_file(self, file_path: Path):
        """处理单个文件（可能触发编码错误）"""
        # 尝试用 UTF-8 读取（可能失败）
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.results.append({
                "file": str(file_path),
                "size": len(content),
                "status": "success"
            })
        except UnicodeDecodeError:
            # 尝试用 GBK 读取（中文系统常见）
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    content = f.read()
                self.results.append({
                    "file": str(file_path),
                    "size": len(content),
                    "status": "success_gbk"
                })
            except:
                # 重新抛出 UnicodeDecodeError（让调用者处理）
                raise


# ================= 测试用例 =================
if __name__ == "__main__":
    print("=== 文件扫描工具集成测试 ===\n")
    
    # 创建扫描器实例
    scanner = FileScanner(WORKSPACE)
    
    # 执行扫描（会触发多个 status_callback）
    print("[测试] 开始扫描 workspace...")
    scanner.scan(max_files=50)
    
    # 查看扫描结果
    print(f"\n扫描结果：")
    print(f"  成功：{len(scanner.results)} 个文件")
    print(f"  失败：{len(scanner.errors)} 个文件")
    
    # 查看系统事件（如果有的话）
    heartbeat = get_heartbeat()
    pending = heartbeat.get_pending_events()
    if pending:
        print(f"\n待处理系统事件：{len(pending)} 个")
        for event in pending:
            print(f"  - {event['event_type']}: {event['payload']}")
    else:
        print("\n✅ 所有系统事件已被消费（注入到 Prompt 中）")
    
    print("\n=== 测试完成 ===")
