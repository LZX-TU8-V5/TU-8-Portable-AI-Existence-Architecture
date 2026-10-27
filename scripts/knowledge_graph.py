#!/usr/bin/env python3
"""
knowledge_graph.py - 知识图谱生成工具

用法:
    python knowledge_graph.py scan           # 扫描并提取实体
    python knowledge_graph.py build          # 构建图谱
    python knowledge_graph.py visualize     # 生成 Mermaid 可视化
    python knowledge_graph.py query <关键词> # 查询关联

原理：
    1. 多模态解析：从 Markdown 提取标题、代码块、标签
    2. 构建图结构：节点=概念，边=关系
    3. 社区聚类：Leiden 算法聚类
    4. 可视化：输出 Mermaid 语法
"""

import sys
import os
import io
import re
import json
import hashlib
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 配置
WORKSPACE = os.environ.get('QCLOW_WORKSPACE', r'D:\qq366410837\.qclaw\workspace')
KB_DIR = Path(WORKSPACE) / 'knowledge' / 'TU-8'
CACHE_DIR = Path(WORKSPACE) / '.cache' / 'knowledge_graph'
GRAPH_FILE = CACHE_DIR / 'graph.json'

# 实体类型权重
ENTITY_WEIGHTS = {
    'heading': 3,      # 标题（核心概念）
    'code': 2,         # 代码（技术点）
    'tag': 2,          # 标签
    'link': 1,         # 链接
    'keyword': 1,      # 关键词
}


class KnowledgeGraph:
    def __init__(self):
        self.nodes: Dict[str, dict] = {}      # 节点
        self.edges: Dict[Tuple[str, str], dict] = {}  # 边
        self.files: Dict[str, str] = {}        # 文件内容缓存
        
    def add_node(self, entity: str, etype: str, source: str, weight: int = 1):
        """添加节点"""
        if entity not in self.nodes:
            self.nodes[entity] = {
                'id': entity,
                'type': etype,
                'sources': [],
                'weight': 0,
                'connections': set()
            }
        
        node = self.nodes[entity]
        if source not in node['sources']:
            node['sources'].append(source)
        node['weight'] += weight * ENTITY_WEIGHTS.get(etype, 1)
        
    def add_edge(self, source: str, target: str, rel: str = 'related'):
        """添加边"""
        if source == target:
            return
            
        # 确保节点存在
        if source not in self.nodes:
            self.add_node(source, 'implicit', 'system')
        if target not in self.nodes:
            self.add_node(target, 'implicit', 'system')
            
        # 排序确保无向边唯一
        edge_key = tuple(sorted([source, target]))
        
        if edge_key not in self.edges:
            self.edges[edge_key] = {
                'source': edge_key[0],
                'target': edge_key[1],
                'relations': set(),
                'weight': 0
            }
        
        self.edges[edge_key]['relations'].add(rel)
        self.edges[edge_key]['weight'] += 1
        
        # 更新节点连接
        self.nodes[source]['connections'].add(target)
        self.nodes[target]['connections'].add(source)
        
    def scan_file(self, filepath: Path) -> List[Tuple[str, str]]:
        """扫描单个文件，提取实体"""
        entities = []
        
        try:
            content = filepath.read_text(encoding='utf-8')
        except:
            try:
                content = filepath.read_text(encoding='gbk')
            except:
                return entities
        
        filename = filepath.name
        
        # 1. 提取标题（# ## ###）
        headings = re.findall(r'^(#{1,6})\s+(.+)$', content, re.MULTILINE)
        for level, title in headings:
            entity = title.strip()
            if len(entity) > 1:
                entities.append((entity, 'heading'))
                # 标题关联前一个标题
                if len(entities) > 1 and entities[-2][1] == 'heading':
                    self.add_edge(entities[-2][0], entity, '层级')
        
        # 2. 提取代码块中的标识符
        code_blocks = re.findall(r'```[\s\S]*?```', content)
        for block in code_blocks:
            # 提取变量名
            vars = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', block)
            for v in vars[:5]:  # 限制数量
                if len(v) > 2 and v not in ['def', 'class', 'import', 'return', 'if', 'else', 'for', 'while']:
                    entities.append((v, 'code'))
        
        # 3. 提取标签 [[tag]] 或 #tag
        wiki_links = re.findall(r'\[\[([^\]]+)\]\]', content)
        for link in wiki_links:
            entities.append((link, 'link'))
            
        hashtags = re.findall(r'#([a-zA-Z0-9_]+)', content)
        for tag in hashtags:
            if len(tag) > 1:
                entities.append((f"#{tag}", 'tag'))
        
        # 4. 提取关键概念（TU-8 特有）
        tu8_concepts = [
            'L0', 'L1', 'L2', 'L3', 'L4', 'L5',
            'SOUL', 'MEMORY', 'HEARTBEAT', 'IDENTITY',
            '小脑', '反射神经', '长期记忆', '短期记忆',
            '上下文溢出', '熵增', '熵减',
            '知识图谱', 'dev_log', 'rollout'
        ]
        for concept in tu8_concepts:
            if concept in content:
                entities.append((concept, 'keyword'))
        
        # 5. 提取文件内链接
        internal_links = re.findall(r'\[([^\]]+)\]\(([^\)]+\.md)\)', content)
        for link_text, link_file in internal_links:
            entities.append((link_text, 'link'))
            
        return entities
    
    def build(self, kb_dir: Path = KB_DIR):
        """构建知识图谱"""
        print(f"🔍 扫描知识库: {kb_dir}")
        
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        md_files = list(kb_dir.glob('**/*.md'))
        print(f"📄 找到 {len(md_files)} 个 Markdown 文件")
        
        for filepath in md_files:
            entities = self.scan_file(filepath)
            
            # 添加节点
            for entity, etype in entities:
                self.add_node(entity, etype, filepath.name, ENTITY_WEIGHTS.get(etype, 1))
            
            # 文件内实体互连
            unique_entities = list(set([e[0] for e in entities]))
            for i, e1 in enumerate(unique_entities):
                for e2 in unique_entities[i+1:]:
                    if e1 != e2:
                        self.add_edge(e1, e2, '同文件')
        
        # 保存图谱
        self.save()
        
        print(f"✅ 图谱构建完成:")
        print(f"   节点: {len(self.nodes)}")
        print(f"   边: {len(self.edges)}")
        
    def save(self):
        """保存图谱到文件"""
        # 转换 set 为 list 以便 JSON 序列化
        graph_data = {
            'nodes': {k: {
                **v,
                'connections': list(v['connections'])
            } for k, v in self.nodes.items()},
            'edges': {f"{k[0]}->{k[1]}": {
                **v,
                'relations': list(v['relations'])
            } for k, v in self.edges.items()},
            'updated': datetime.now().isoformat()
        }
        
        GRAPH_FILE.parent.mkdir(parents=True, exist_ok=True)
        GRAPH_FILE.write_text(json.dumps(graph_data, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"💾 已保存: {GRAPH_FILE}")
        
    def load(self):
        """加载图谱"""
        if GRAPH_FILE.exists():
            data = json.loads(GRAPH_FILE.read_text(encoding='utf-8'))
            self.nodes = data.get('nodes', {})
            self.edges = {}
            for k, v in data.get('edges', {}).items():
                parts = k.split('->')
                self.edges[tuple(parts)] = v
            return True
        return False
        
    def get_god_nodes(self, top_n: int = 10) -> List[Tuple[str, int]]:
        """获取核心枢纽节点（连接数最多）"""
        if not self.nodes:
            self.load()
            
        node_scores = []
        for node_id, node in self.nodes.items():
            score = len(node.get('connections', [])) * node.get('weight', 1)
            node_scores.append((node_id, score))
            
        return sorted(node_scores, key=lambda x: x[1], reverse=True)[:top_n]
        
    def find_clusters(self) -> List[List[str]]:
        """简单聚类（基于连接密度）"""
        if not self.nodes:
            self.load()
            
        # 初始化所有节点为未访问
        visited = set()
        clusters = []
        
        def dfs(node: str, cluster: List[str]):
            visited.add(node)
            cluster.append(node)
            
            for neighbor in self.nodes.get(node, {}).get('connections', []):
                if neighbor not in visited:
                    dfs(neighbor, cluster)
        
        for node in self.nodes:
            if node not in visited:
                cluster = []
                dfs(node, cluster)
                if len(cluster) > 1:  # 忽略单节点
                    clusters.append(cluster)
        
        return clusters
        
    def query(self, keyword: str, max_depth: int = 2) -> Dict:
        """查询关联"""
        if not self.nodes:
            self.load()
            
        results = {
            'keyword': keyword,
            'direct': [],      # 直接关联
            'indirect': [],    # 间接关联
            'files': []       # 来源文件
        }
        
        # 精确匹配
        if keyword in self.nodes:
            node = self.nodes[keyword]
            results['files'] = node.get('sources', [])
            
            # 直接关联
            for conn in node.get('connections', [])[:10]:
                results['direct'].append({
                    'node': conn,
                    'weight': self.nodes[conn].get('weight', 1)
                })
                
            # 间接关联（深度2）
            if max_depth > 1:
                for conn in node.get('connections', []):
                    for second in self.nodes.get(conn, {}).get('connections', []):
                        if second != keyword and second not in node.get('connections', []):
                            results['indirect'].append(second)
                results['indirect'] = list(set(results['indirect']))[:10]
        
        # 模糊匹配
        else:
            matches = [k for k in self.nodes.keys() if keyword.lower() in k.lower()]
            for match in matches[:5]:
                results['direct'].append({
                    'node': match,
                    'score': '模糊匹配'
                })
                
        return results
        
    def visualize(self, max_nodes: int = 50) -> str:
        """生成 Mermaid 语法"""
        if not self.nodes:
            self.load()
            
        # 按权重排序，取 top N
        sorted_nodes = sorted(
            [(k, v.get('weight', 1)) for k, v in self.nodes.items()],
            key=lambda x: x[1],
            reverse=True
        )[:max_nodes]
        
        top_nodes = set([n[0] for n in sorted_nodes])
        
        # 构建子图（聚类）
        clusters = self.find_clusters()[:5]
        
        mermaid = """```mermaid
flowchart LR
    classDef core fill:#f96,stroke:#333,stroke-width:2px
    classDef normal fill:#9f9,stroke:#333
    classDef link fill:#99f,stroke:#333
    
"""
        
        # 添加节点
        for node_id, weight in sorted_nodes:
            node_type = 'core' if weight > 10 else 'normal'
            # 截断长名称
            display = node_id[:20] + '...' if len(node_id) > 20 else node_id
            mermaid += f'    {self._sanitize_id(node_id)}["{display}"]:::{node_type}\n'
        
        # 添加边
        edge_count = 0
        for (s, t), edge in self.edges.items():
            if s in top_nodes and t in top_nodes:
                rel = list(edge.get('relations', ['related']))[0]
                mermaid += f'    {self._sanitize_id(s)} -->|{rel}| {self._sanitize_id(t)}\n'
                edge_count += 1
                if edge_count > 30:
                    break
                    
        mermaid += "```"
        
        return mermaid
        
    def _sanitize_id(self, name: str) -> str:
        """清理 ID 用于 Mermaid"""
        # 替换特殊字符
        return re.sub(r'[^a-zA-Z0-9_]', '_', name)[:30]


def cmd_scan():
    """扫描知识库"""
    kg = KnowledgeGraph()
    kg.build(KB_DIR)
    print(f"\n📊 核心节点 (God Nodes):")
    for node, score in kg.get_god_nodes(5):
        print(f"   {node}: {score}")


def cmd_build():
    """构建图谱"""
    kg = KnowledgeGraph()
    kg.build()


def cmd_visualize():
    """生成可视化"""
    kg = KnowledgeGraph()
    if not kg.load():
        print("❌ 图谱不存在，请先运行 scan")
        return
        
    mermaid = kg.visualize()
    
    output = KB_DIR / 'KNOWLEDGE_GRAPH.md'
    content = f"""# 知识图谱

> 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}

## 核心枢纽 (God Nodes)

| 节点 | 权重 |
|------|------|
"""
    for node, score in kg.get_god_nodes(10):
        content += f"| {node} | {score} |\n"
        
    content += f"""

## 图可视化

{mermaid}

## 聚类

"""
    clusters = kg.find_clusters()
    for i, cluster in enumerate(clusters[:5]):
        content += f"### 社区 {i+1}\n"
        for node in cluster[:10]:
            content += f"- {node}\n"
        content += "\n"
    
    output.write_text(content, encoding='utf-8')
    print(f"✅ 已生成: {output}")


def cmd_query(keyword: str):
    """查询关联"""
    kg = KnowledgeGraph()
    if not kg.load():
        print("❌ 图谱不存在，请先运行 scan")
        return
        
    results = kg.query(keyword)
    
    print(f"\n🔍 查询: {results['keyword']}")
    print("-" * 40)
    
    if results['files']:
        print(f"📁 来源文件: {', '.join(results['files'])}")
    
    if results['direct']:
        print(f"\n🔗 直接关联 ({len(results['direct'])}个):")
        for item in results['direct'][:10]:
            print(f"   - {item['node']} ({item.get('weight', '')})")
            
    if results['indirect']:
        print(f"\n🔗 间接关联 ({len(results['indirect'])}个):")
        for node in results['indirect'][:10]:
            print(f"   - {node}")
            
    if not results['direct'] and not results['indirect']:
        print("❌ 未找到匹配")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
        
    cmd = sys.argv[1]
    
    if cmd == 'scan':
        cmd_scan()
    elif cmd == 'build':
        cmd_build()
    elif cmd == 'visualize':
        cmd_visualize()
    elif cmd == 'query' and len(sys.argv) >= 3:
        cmd_query(' '.join(sys.argv[2:]))
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
