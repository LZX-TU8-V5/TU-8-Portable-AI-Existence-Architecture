# Fix L2/index.md - correct file names to match actual files

path = r'C:\Users\qq366410837\.qclaw\workspace\knowledge\TU-8\L2\index.md'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace Chinese file names with actual English file names
replacements = {
    '`01_元协议.md`': '`01_meta.md`',
    '`02_经验沉淀.md`': '`02_experience.md`',
    '`03_技能文档.md`': '`03_skill_doc.md`',
    '`04_问题解决.md`': '`04_protocols.md`',
    '`05_决策框架.md`': '`05_execution.md`',
    '`06_学习机制.md`': '`06_principles.md`',
    '`07_工具管理.md`': '`07_resources.md`',
    '`08_智能基元.md`': '`08_primitives.md`',
    '`09_信息生态.md`': '`09_infoeco.md`',
    '`10_创造性方法论.md`': '`10_creativity.md`',
    '`11_因果归因.md`': '`11_causality.md`',
    '`12_优化器方法.md`': '`12_benders.md`',
    '`13_双引擎架构.md`': '`13_dual_engine.md`',
    '`14_跨层接口.md`': '`14_cross_layer.md`',
    '_共享定义.md': '_shared.md',
}

for old, new in replacements.items():
    content = content.replace(old, new)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Done. Fixed file names in index.md")
