#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Memory Node 自动生成工具
功能：将普通 Markdown 文件转换为 Memory Node 格式（五栏结构 + 八组YAML接口）
作者：TU-8 Agent
日期：2026-06-20
版本：v1.0
"""

import os
import sys
import json
import hashlib
from datetime import datetime
from pathlib import Path
import re

# ================= 配置区 =================
WORKSPACE = Path("D:/qq366410837/.qclaw/workspace")
TEMPLATE_PATH = WORKSPACE / "knowledge/TU-8/memory_node_template_v1.0.md"

# ================= 核心类 =================
class MemoryNodeGenerator:
    """Memory Node 生成器"""
    
    def __init__(self, input_path: str, output_path: str = None):
        self.input_path = Path(input_path)
        self.output_path = Path(output_path) if output_path else self._default_output_path()
        self.content = ""
        self.metadata = {}
        
    def _default_output_path(self) -> Path:
        """默认输出路径：同一目录，扩展名改为 .node.md"""
        return self.input_path.parent / f"{self.input_path.stem}.node.md"
        
    def read_input(self):
        """读取输入文件"""
        if not self.input_path.exists():
            raise FileNotFoundError(f"文件不存在: {self.input_path}")
        
        with open(self.input_path, 'r', encoding='utf-8') as f:
            self.content = f.read()
        
        print(f"✅ 已读取文件: {self.input_path}")
        return self
        
    def extract_metadata(self):
        """从原文提取元数据（标题、标签等）"""
        # 提取第一个标题
        title_match = re.search(r'^#\s+(.+)$', self.content, re.MULTILINE)
        title = title_match.group(1) if title_match else self.input_path.stem
        
        # 提取现有标签（#tag 格式）
        tags = re.findall(r'#(\w+)', self.content)
        
        # 生成 node_id
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        node_id = f"mem_{timestamp}_{self.input_path.stem}"
        
        self.metadata = {
            'title': title,
            'tags': tags,
            'node_id': node_id,
            'timestamp': datetime.now().isoformat(),
        }
        
        print(f"✅ 已提取元数据: title='{title}', tags={tags}")
        return self
        
    def generate_yaml(self) -> str:
        """生成八组YAML接口"""
        ts = self.metadata['timestamp']
        node_id = self.metadata['node_id']
        
        # 自动生成钢印哈希（简化版）
        seal_hash = hashlib.sha256(f"{node_id}{ts}".encode()).hexdigest()[:16]
        
        yaml = f"""---
# ================= Memory Node v1.0: {self.metadata['title']} =================
# 作用：自动生成（工具：generate_memory_node.py）
# 版本: 1.0 | 日期: {datetime.now().strftime('%Y-%m-%d')} | 作者: TU-8 Agent

# ---- 接口1：节点身份 ----
node_id: "{node_id}"
node_type: "auto_generated"
node_status: "active"

# ---- 接口2：钢印链条 ----
seal_chain:
  parent_seal: null
  child_seals: []
  current_seal: "seal_{datetime.now().strftime('%Y%m%d_%H%M%S')}_create"
  seal_count: 1
  session_id: "sess_{datetime.now().strftime('%Y%m%d_%H%M%S')}_TU8_AutoGen"
  seal_hash: "{seal_hash}"

# ---- 接口3：空间坐标 ----
spatial:
  zone: "AUTO"
  coordinates: [0, 0, 0]
  neighbors: []

# ---- 接口4：状态向量 ----
state_vector:
  timestamp: "{ts}"
  vector: [0.5, 0.5, 0.5]
  narrative_compression: "自动生成Memory Node，待人工完善"
  causal_coherence: 0.5

# ---- 接口5：知识网络 ----
knowledge_links:
  supports_core: []
  referenced_by: []
  related_to: []
  similarity_links: []

# ---- 接口6：防丢失 ----
fallback:
  tags: {json.dumps([f"#{tag}" for tag in self.metadata['tags'][:5]])}
  semantic_hooks: ["自动生成", "{self.metadata['title']}"]
  aliases: ["{self.input_path.name}"]

# ---- 接口7：检索优化 ----
retrieval:
  dimension_digest:
    - what: "{self.metadata['title']}"
    - who: "待补充"
    - how: "待补充"
    - why: "待补充"
    - risk: "自动生成，需人工完善"
  weight: 0.5
  last_accessed: "{ts}"
  access_count: 1

# ---- 接口8：链接完整性 ----
link_check:
  last_verified: null
  broken_links: []
  auto_repair: true
---

"""
        
        print(f"✅ 已生成 YAML 头部（{len(yaml.splitlines())} 行）")
        return yaml
        
    def generate_four_columns(self) -> str:
        """生成四栏结构（第二到第五栏）"""
        columns = f"""
# ================= 第二栏：钢印链条时间线 =================
## Seal Chain Timeline
- **[{datetime.now().isoformat()}] [CREATE]** 自动生成 Memory Node。
  - 状态向量：`[0.5, 0.5, 0.5]`
  - 因果连贯度：`0.5`（混沌期，待人工完善）
  - Session ID：`sess_{datetime.now().strftime('%Y%m%d_%H%M%S')}_TU8_AutoGen`

# ================= 第三栏：标签和钩子 =================
## Tags & Hooks
- **核心标签**：{', '.join([f'#{tag}' for tag in self.metadata['tags'][:5]]) if self.metadata['tags'] else '（待补充）'}
- **语义钩子**：`{self.metadata['title']}` `自动生成` `待完善`

# ================= 第四栏：浓缩五维 =================
## 5-Dimensional Digest
1. **核心目标**：{self.metadata['title']}
2. **适用对象**：待补充
3. **运作机制**：待补充
4. **防御边界**：自动生成，需人工完善
5. **风险/限制**：信息不完整，仅作参考

# ================= 第五栏：正文 =================
# {self.metadata['title']}

"""
        
        print(f"✅ 已生成四栏结构")
        return columns
        
    def generate(self):
        """生成完整的 Memory Node 文件"""
        self.read_input()
        self.extract_metadata()
        
        yaml_header = self.generate_yaml()
        four_columns = self.generate_four_columns()
        
        # 组合：YAML + 四栏 + 原文
        output_content = yaml_header + four_columns + self.content
        
        # 写入输出文件
        with open(self.output_path, 'w', encoding='utf-8') as f:
            f.write(output_content)
        
        print(f"\n🎉 生成成功！输出文件: {self.output_path}")
        print(f"📊 文件大小: {len(output_content)} 字节")
        return self.output_path
        
    def backup_original(self):
        """备份原文件"""
        backup_dir = WORKSPACE / f"backup/generated_{datetime.now().strftime('%Y%m%d')}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        backup_path = backup_dir / self.input_path.name
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(self.content)
        
        print(f"✅ 已备份原文件到: {backup_path}")
        return backup_path


# ================= 命令行接口 =================
def main():
    if len(sys.argv) < 2:
        print("用法: python generate_memory_node.py <input_file> [output_file]")
        print("示例: python generate_memory_node.py MEMORY.md MEMORY.node.md")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        generator = MemoryNodeGenerator(input_path, output_path)
        generator.backup_original()  # 先备份
        output = generator.generate()
        
        print(f"\n✅ 完成！请审阅生成的文件: {output}")
        print(f"⚠️  注意：自动生成的内容需人工完善（特别是第四栏和第五栏）")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
