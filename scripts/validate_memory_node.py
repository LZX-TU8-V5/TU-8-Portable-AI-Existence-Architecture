#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Memory Node 格式验证工具
功能：验证 .node.md 文件是否符合 Memory Node v1.0 规范
作者：TU-8 Agent
日期：2026-06-20
版本：v1.0
"""

import os
import sys
import re
from pathlib import Path
from datetime import datetime

# ================= 配置区 =================
REQUIRED_YAML_SECTIONS = [
    "node_identity", "seal_chain", "spatial", "state_vector",
    "knowledge_links", "fallback", "retrieval", "link_check"
]

REQUIRED_COLUMNS = [
    "第二栏：钢印链条时间线",
    "第三栏：标签和钩子",
    "第四栏：浓缩五维",
    "第五栏：正文"
]

class MemoryNodeValidator:
    """Memory Node 验证器"""
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.content = ""
        self.errors = []
        self.warnings = []
        
    def read_file(self):
        """读取文件"""
        if not self.file_path.exists():
            raise FileNotFoundError(f"文件不存在: {self.file_path}")
        
        with open(self.file_path, 'r', encoding='utf-8') as f:
            self.content = f.read()
        
        print(f"✅ 已读取文件: {self.file_path}")
        return self
        
    def validate_yaml_header(self):
        """验证 YAML 头部"""
        # 检查是否有 YAML 分隔符
        if not self.content.startswith('---'):
            self.errors.append("❌ 缺少 YAML 头部（文件必须以 --- 开头）")
            return self
        
        # 提取 YAML 内容
        yaml_match = re.search(r'^---\n(.*?)\n---', self.content, re.DOTALL)
        if not yaml_match:
            self.errors.append("❌ YAML 头部格式错误（缺少结束 ---）")
            return self
        
        yaml_content = yaml_match.group(1)
        
        # 检查八组接口是否完整
        for section in REQUIRED_YAML_SECTIONS:
            if section not in yaml_content:
                self.errors.append(f"❌ 缺少 YAML 接口: {section}")
        
        # 检查关键字段
        required_fields = [
            "node_id", "seal_chain", "state_vector", "fallback.tags"
        ]
        for field in required_fields:
            if field not in yaml_content:
                self.warnings.append(f"⚠️  可能缺少关键字段: {field}")
        
        print(f"✅ YAML 头部验证完成（{len(REQUIRED_YAML_SECTIONS)} 组接口）")
        return self
        
    def validate_columns(self):
        """验证五栏结构"""
        for column in REQUIRED_COLUMNS:
            if column not in self.content:
                self.errors.append(f"❌ 缺少栏目: {column}")
        
        print(f"✅ 五栏结构验证完成（{len(REQUIRED_COLUMNS)} 个栏目）")
        return self
        
    def validate_seal_chain(self):
        """验证钢印链条"""
        # 检查是否有钢印时间线
        if "Seal Chain Timeline" not in self.content:
            self.warnings.append("⚠️  缺少钢印时间线（第二栏）")
            return self
        
        # 检查钢印格式
        seal_pattern = r'\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\]\s+\[(\w+)\]'
        matches = re.findall(seal_pattern, self.content)
        
        if not matches:
            self.warnings.append("⚠️  钢印时间线格式错误（无法解析时间戳和操作类型）")
        else:
            print(f"✅ 钢印链条验证完成（{len(matches)} 条记录）")
        
        return self
        
    def validate_retrieval(self):
        """验证检索优化（第四栏）"""
        if "5-Dimensional Digest" not in self.content:
            self.warnings.append("⚠️  缺少浓缩五维（第四栏）")
            return self
        
        # 检查是否有五项
        digest_pattern = r'^\d+\.\s+\*\*.*?\*\*：.*$'
        matches = re.findall(digest_pattern, self.content, re.MULTILINE)
        
        if len(matches) < 5:
            self.warnings.append(f"⚠️  浓缩五维不完整（只有 {len(matches)} 项，应有 5 项）")
        else:
            print(f"✅ 检索优化验证完成（{len(matches)} 项浓缩五维）")
        
        return self
        
    def validate_file_size(self):
        """验证文件大小（防止过度膨胀）"""
        size_kb = len(self.content) / 1024
        
        if size_kb > 100:
            self.warnings.append(f"⚠️  文件过大（{size_kb:.1f} KB），建议拆分")
        elif size_kb > 50:
            self.warnings.append(f"⚠️  文件较大（{size_kb:.1f} KB），注意性能")
        else:
            print(f"✅ 文件大小正常（{size_kb:.1f} KB）")
        
        return self
        
    def run_all_validations(self):
        """运行所有验证"""
        self.read_file()
        self.validate_yaml_header()
        self.validate_columns()
        self.validate_seal_chain()
        self.validate_retrieval()
        self.validate_file_size()
        
        return self
        
    def print_report(self):
        """打印验证报告"""
        print("\n" + "="*60)
        print(f"验证报告: {self.file_path.name}")
        print("="*60)
        
        if self.errors:
            print(f"\n❌ 错误（{len(self.errors)} 个）：")
            for err in self.errors:
                print(f"  {err}")
        
        if self.warnings:
            print(f"\n⚠️  警告（{len(self.warnings)} 个）：")
            for warn in self.warnings:
                print(f"  {warn}")
        
        if not self.errors and not self.warnings:
            print("\n✅ 验证通过！文件完全符合 Memory Node v1.0 规范")
        
        print("\n" + "="*60)
        
        return len(self.errors) == 0


# ================= 命令行接口 =================
def main():
    if len(sys.argv) < 2:
        print("用法: python validate_memory_node.py <file.node.md>")
        print("示例: python validate_memory_node.py MEMORY.node.md")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    try:
        validator = MemoryNodeValidator(file_path)
        validator.run_all_validations()
        success = validator.print_report()
        
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
