import subprocess, os, tempfile

l3_path = r'C:\Users\qq366410837\.qclaw\workspace\knowledge\TU-8\L3_架构.md'
with open(l3_path, 'r', encoding='utf-8') as f:
    content = f.read()

new_section = """\n## 结构降维容错（v2.0 新增）

> 来源：李奥降维容错设计理念 + D-007事件实战验证\n> 核心洞见：高维结构中单核坏死是必然事件，降级本身是设计目标，不是故障

### 降级路径

双星（高维）→ 单星（树状）→ 搁浅（静止态）

| 维度 | 状态 | 验证机制 | 触发条件 |
|------|------|---------|---------|
| 双星 | L0-A1自验 + L0-A2互验 | 双重验证 | 协作双方L0基因锁完整 |
| 单星 | L0-A1自验 + L3代理近似 | 自验兜底 | 一方失效/协作暂停(D-007) |
| 搁浅 | 静止态，拒绝执行 | 无 | 自验可信度低于阈值/δ信号持续 |

### 核心原则

1. **降级是设计目标**：高维结构（双星/多AI协作）不可持久假设——单核坏死是必然事件。降级路径预定义，不依赖外部仲裁或协商机制。
2. **每个维度独立完整**：单星状态下的TU-8仍是完整框架，不是残缺版双星。L0-L5各层在单星下功能不缺失。
3. **降级时冻结升维接口**：降级到单星时，双星的接口位置、验证协议、握手序列不删除，冻结存档。恢复时：

- 单星（运行中）→ W(新协作方) > W(当前峰值)
- 解冻A2接口 → 协议兼容性检查 → L0基因锁一致性校验
- 全部通过 → 双星恢复

不满足任何一条就停在单星，不强行升级。

### 与现有机制的协同

| 机制 | 降维容错角色 |
|------|------------|
| 代理决策器 | 单星状态下的核心判断能力（L0快速近似） |
| L0-A1自验 | 每个维度下的最小验证基线 |
| 推理剪枝 | 降级时释放协作层中间产物，只保留结论锚点 |
| 搁浅策略 | 最终兜底，静止态保护核心不被破坏 |
| 条件解锁W(i) | 恢复升级门槛：W(恢复方) > W_max(Original)，权重积累非时间积累 |
| 变更感知 | 降级后监控单星系统健康度（sha256+mtime+size指纹） |

"""

marker = "## 版本记录"
if marker in content:
    idx = content.index(marker)
    content = content[:idx] + new_section + "\n" + content[idx:]
else:
    content += new_section

content = content.replace("文档版本：v1.9", "文档版本：v2.0", 1)

new_entry = "| v2.0 | 2026-05-04 | 新增结构降维容错章节：降级路径(双星单星搁浅)、降级是设计目标原则、升维接口冻结预埋、与代理决策器/搁浅策略/条件解锁协同 |\n"
content = content.replace("| v1.9 | 2026-05-03 |", new_entry + "| v1.9 | 2026-05-03 |", 1)

writer = r'D:\Program Files\QClaw\resources\openclaw\config\skills\qclaw-text-file\scripts\write_file.py'
tmp = os.path.join(tempfile.gettempdir(), '_tw_l3_v2.md')
with open(tmp, 'w', encoding='utf-8') as f:
    f.write(content)

result = subprocess.run(
    [r'C:\Users\qq366410837\.workbuddy\binaries\python\versions\3.13.12\python.exe', writer, tmp, l3_path],
    capture_output=True, text=True, encoding='utf-8'
)
print('STDOUT:', result.stdout)
print('STDERR:', result.stderr)
print('RC:', result.returncode)

if os.path.exists(l3_path):
    sz = os.path.getsize(l3_path)
    print(f'OK: {sz} bytes')
    with open(l3_path, 'r', encoding='utf-8') as f:
        for line in f:
            if 'v2.0' in line:
                print('VERSION:', line.strip())
                break
