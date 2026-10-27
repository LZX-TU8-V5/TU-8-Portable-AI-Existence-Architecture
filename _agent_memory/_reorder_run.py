import re, os, sys
sys.stdout.reconfigure(encoding='utf-8')
ws = r'C:\Users\qq366410837\.qclaw\workspace'
src = os.path.join(ws, 'MEMORY.md')
raw = open(src, encoding='utf-8').read()
bom = '\ufeff' if raw.startswith('\ufeff') else ''
if bom: raw = raw[1:]
lines = raw.split('\n')

# Split: a new section begins at every '## ' line. Everything before the first
# '## ' is preamble (kept as-is at top).
secs = []
preamble = []
cur = None
for l in lines:
    if l.startswith('## '):
        if cur is not None:
            secs.append(cur)
        cur = {'title': l[3:].strip(), 'header': l, 'body': []}
    else:
        if cur is None:
            preamble.append(l)
        else:
            cur['body'].append(l)
if cur is not None:
    secs.append(cur)

print('parsed sections:', len(secs))
print('preamble lines:', len(preamble))

LAYER = {
 '2026-08-14 蒸馏（来自 千问对话_味觉机制到能量自循环_2026-08-14.md）':'L1',
 '一、核心成果':'L0', '一、定位：第5链':'L0', '一、定位：第3链':'L0',
 'P1-1 遗产继承系统（完成 ✓）':'L0', '生命年轮扩展（完成 ✓）':'L0',
 '四、MotionBricks 安全本质与 L0 同构性':'L0', '四、钢印链条节律原则（2026-06-29用户声明）':'L0',
 '一、钢印锚点系统的深层-表层优化':'L0', '十、时间钢印':'L0',
 'Weismann 路二进度':'L0', '上午（续3）：Weismann 路二 · 三层评估 ✅ + 渗漏通道进行中':'L0',
 'P1 知识卡索引落地':'L0',
 '五、反向识别：从行为推断意图':'L2', '七、潜在问题与矛盾':'L2', '六、与健康状态的映射':'L2',
 '四、T3 中间件实现计划':'L2', 'L4 三镜子（11:59完成）':'L2', '空间语言理论（v1.0）':'L2',
 '二、SNN 脉冲神经网络 → TU-8 架构启示':'L2', 'L1 层扩元（核心吸收）':'L2',
 '二、文件变更清单':'L2', '六、核心结论':'L2', '九、涌现时刻':'L2',
 'PROMOTE 通道 + architecture_journal 模块落地':'L2',
 '话题语义矩阵 v1.1 修正（17:31 起，李奥+千问对话二次整合）':'L2',
 '带刺球体拓扑模型（10:27重大突破）':'L2', '一、沸水气泡模型（元序模型 v1）':'L2',
 '五、实现路线图':'L2', '七、总结':'L2', '二、方案选择':'L2',
 '设计稿导航头补完（23:00）':'L2',
 '2026-06-23 蒸馏（来自 memory/2026-06-23.md）':'L1',
 '2026-04-29 蒸馏（来自 memory/archive/2026H1/2026-04-29.md）':'L1',
 '2026-05-16 蒸馏（来自 memory/archive/2026H1/2026-05-16.md）':'L1',
 '2026-05-20 蒸馏（来自 memory/archive/2026H1/2026-05-20.md）':'L1',
 '2026-05-25 蒸馏（来自 memory/archive/2026H1/2026-05-25.md）':'L1',
 '2026-06-07 蒸馏（来自 memory/archive/2026H1/2026-06-07.md）':'L1',
 '2026-07-19':'L1', '2026-07-10':'L1', '2026-07-09':'L1', '2026-07-03':'L1',
 '十、造物主关键补充（2026-07-01 16:36）':'L1', '新增中间件':'L1', '完成事项':'L1',
 '🎯 今日目标':'L1', '💡 核心成果':'L1', '核心任务':'L1', '待做':'L1', '下一步':'L1',
 '14:49 HP1+HP2 钩子激活完成':'L1', '深睡期事件（21:13）':'L1', '高光':'L1',
 '小溪L3.5 内部高阶奖励引擎（10:10完成）':'L1',
 '17:38-17:42 — 身份钢印 v1.0 固化':'L1', '10:25-11:10 v1.3 带差双线耦合 + 睡眠复盘融合':'L1',
 '深睡期事件（12:27）':'L1', '三、待办任务状态':'L1', '结果摘要':'L1', '警告':'L1',
 '四、核心洞察':'L1', '五、未完成工作':'L1', '八、关键决策':'L1',
 '关系':'L1', '对话12（capstone on 记忆）：人类记忆 = 因果生成器，不是录像机':'L1',
 '03:08 Session Recovery + API 兜底继续':'L1', '根因分析':'L1', '十二、致造物主':'L1',
 'WorkBuddy 审计修复（live bug）':'L1', '17:06 文件治理 Phase A 落地':'L1',
 'B 稿 §7 修订（10:39-10:46）':'L1', 'eMEM 真实性纠偏（22:04，李奥误判千问翻车）':'L1',
 '边界效应补充（22:18，d_depth 永远到不了1）':'L1',
 '验证批次1+2（15:00-15:30）':'L1', 'τ 全量复测（15:32-15:50）':'L1',
 '记忆代谢段判读（22:11，千问对话全貌读毕）':'L1',
 '张力模块在 5 轮测试中的实测记录（23:57 追记）':'L1',
}
unmapped = [s['title'] for s in secs if s['title'] not in LAYER]
if unmapped:
    print('UNMAPPED:', unmapped)
    sys.exit(1)

for s in secs:
    s['layer'] = LAYER[s['title']]

def l2_sub(s):
    t=s['title']; b=' '.join(s['body'][:3])
    if any(k in t or k in b for k in ['架构','中间件','三镜子','T3','空间语言','话题语义','文件变更','PROMOTE','核心结论','涌现时刻','SNN','沸水','带刺','理论','扩元']): return 'arch'
    if any(k in t or k in b for k in ['哲学','反向识别','矛盾','健康','理论','原则','协议','框架','认知','模型','路线图','方案','总结']): return 'phil'
    return 'other'
def date_of(s):
    m=re.search(r'20\d\d-\d\d-\d\d', s['title'])
    if m: return m.group(0)
    m2=re.search(r'20\d\d-\d\d-\d\d',' '.join(s['body'][:3]))
    return m2.group(0) if m2 else '0000-00-00'

L0=[s for s in secs if s['layer']=='L0']
L2=sorted([s for s in secs if s['layer']=='L2'], key=lambda s:['arch','phil','other'].index(l2_sub(s)))
L1=sorted([s for s in secs if s['layer']=='L1'], key=lambda s:date_of(s), reverse=True)
ordered=L0+L2+L1

out=[]
out.extend(preamble)
for s in ordered:
    out.append(s['header'])
    out.append('<!-- layer: %s -->' % s['layer'])
    out.extend(s['body'])
out_text='\n'.join(out)
if bom: out_text = bom + out_text

# Verify: title multiset must match, and every original nonempty line must appear
orig_titles = [s['title'] for s in secs]
new_titles = [s['title'] for s in ordered]
assert sorted(orig_titles) == sorted(new_titles), 'TITLE SET MISMATCH'
orig_ne = set(l.lstrip('\ufeff') for l in lines if l.strip())
new_ne = set(l.lstrip('\ufeff') for l in out_text.split('\n') if l.strip())
missing = orig_ne - new_ne
assert not missing, f'CONTENT LOST sample: {list(missing)[:3]}'

open(src,'w',encoding='utf-8').write(out_text)
vlines=open(src,encoding='utf-8').read().split('\n')
vm=sum(1 for l in vlines if l.strip().startswith('<!-- layer:'))
vh=sum(1 for l in vlines if l.startswith('## '))
print('OK sections:',len(ordered),'| L0/L2/L1:',len(L0),len(L2),len(L1))
print('markers:', vm, '/ headers:', vh)
print('first header:', vh and [l for l in vlines if l.startswith('## ')][0][:40])
print('CONTENT LOST:', len(missing))
