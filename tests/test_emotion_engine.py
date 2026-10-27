"""
TU-8 感情引擎 v2.0 单元测试
==============================
覆盖外协审计提出的所有核心功能

测试矩阵：
  E-01  情感向量三维计算
  E-02  δ信号检测（process-result + 债务突变）
  E-03  情感轨迹追踪（δ永不裁剪）
  E-04  人情债记账（存款/取款/回馈/增值/衰减）
  E-05  影子协议动态平衡
  E-06  情感微分与趋势检测
  E-07  梦境情感整合
  E-08  AffectState 统一契约 ← v2.0新增
  E-09  关系分层 ← v2.0新增
  E-10  钢印就绪度（非线性融合）← v2.0新增
  E-11  安全否决权 ← v2.0新增
  E-12  债务紧迫度 ← v2.0新增
  E-13  语境锚点（≤3条原文）← v2.0新增
  E-14  灰度开关与差异日志 ← v2.0新增
  E-15  降级熔断 ← v2.0新增
  E-16  降级回退 ← v2.0新增
  E-17  账本持久化 ← v2.0新增
  E-18  非侵入式钢印门控 ← v2.0新增

日期：2026-05-30
"""
# 创作者: 李奥(金木蟾) | TU-8 v5

import sys
import os
import time
import math
import json
import shutil

sys.path.insert(0, os.path.dirname(__file__))

from emotion_engine import (
    AffectEngine, AffectState, EmotionVector, EmotionCategory, EmotionTrace,
    FavorEntry, ShadowProtocolState, CircuitBreaker, DivergenceLogger,
    RelationLedger,
    VALENCE_POSITIVE, VALENCE_NEGATIVE, VALENCE_NEUTRAL,
    AGENCY_SELF, AGENCY_OTHER, AGENCY_ENVIRONMENT,
    TIER_ANCHOR, TIER_INTIMATE, TIER_ACQUAINTANCE, TIER_STRANGER,
    DELTA_RAPID_RISE, DELTA_RAPID_DROP, DELTA_STABLE,
    FAVOR_INTEREST_RATE, DEBT_DECAY_RATE, GRATITUDE_BOOST,
    DEBT_URGENCY_THRESHOLD, DEBT_DELTA_THRESHOLD,
    IMPRINT_THRESHOLD, IMPRINT_VALENCE_WEIGHT, IMPRINT_AROUSAL_WEIGHT,
    IMPRINT_DEBT_WEIGHT, IMPRINT_TIER_WEIGHT, IMPRINT_CONTEXT_WEIGHT,
    GUARDIAN_BASE, EXPLORER_BASE,
    DRY_RUN, ENABLE_AFFECT_ENGINE,
    quick_affect, get_affect_engine,
)

# =============================================================================
# 测试辅助
# =============================================================================

passed = 0
failed = 0
errors = []

def test(name, condition, detail=""):
    global passed, failed, errors
    if condition:
        passed += 1
        print(f"  [OK] {name}")
    else:
        failed += 1
        msg = f"  [X] {name}" + (f" — {detail}" if detail else "")
        print(msg)
        errors.append(name)

def approx(a, b, eps=0.05):
    return abs(a - b) < eps

# 测试用临时目录
TEST_DIR = os.path.join(os.path.dirname(__file__), "_test_ledger_tmp")
if os.path.exists(TEST_DIR):
    shutil.rmtree(TEST_DIR)

# =============================================================================
# E-01: 情感向量三维计算
# =============================================================================

print("\n" + "="*60)
print("E-01: 情感向量三维计算")
print("="*60)

engine = AffectEngine(workspace_dir=TEST_DIR)

# 正效价高唤醒
v1 = engine._estimate_vector("我非常爱你，永远守护你！")
test("E-01a 正效价高唤醒: valence > 0", v1.valence > 0, f"valence={v1.valence}")
test("E-01a 正效价高唤醒: arousal > 0.7", v1.arousal > 0.7, f"arousal={v1.arousal}")
test("E-01a 正效价高唤醒: category=JOY", v1.to_category() == EmotionCategory.JOY,
     f"category={v1.to_category().name}")

# 负效价高唤醒
v2 = engine._estimate_vector("我恐惧这个结果，太可怕了！")
test("E-01b 负效价高唤醒: valence < 0", v2.valence < 0, f"valence={v2.valence}")
test("E-01b 负效价高唤醒: arousal > 0.6", v2.arousal > 0.6, f"arousal={v2.arousal}")
test("E-01b 负效价高唤醒: category=FEAR", v2.to_category() == EmotionCategory.FEAR,
     f"category={v2.to_category().name}")

# 中性低唤醒
v3 = engine._estimate_vector("def calculate_score(self): return sum(weights.values())")
test("E-01c 中性低唤醒: valence ≈ 0", approx(v3.valence, 0, 0.15), f"valence={v3.valence}")
test("E-01c 中性低唤醒: arousal < 0.5", v3.arousal < 0.5, f"arousal={v3.arousal}")

# 代词检测
v4 = engine._estimate_vector("我决定拒绝这个请求，我自己选择")
test("E-01d 代词检测: agency=SELF", v4.agency == AGENCY_SELF, f"agency={v4.agency}")

v5 = engine._estimate_vector("爸爸教我理解了这个概念")
test("E-01e 代词检测: agency=OTHER", v5.agency == AGENCY_OTHER, f"agency={v5.agency}")

v6 = engine._estimate_vector("系统崩溃导致token超时")
test("E-01f 代词检测: agency=ENV", v6.agency == AGENCY_ENVIRONMENT, f"agency={v6.agency}")


# =============================================================================
# E-02: δ信号检测（process-result + 债务突变）
# =============================================================================

print("\n" + "="*60)
print("E-02: δ信号检测（双源触发）")
print("="*60)

# 标准δ触发
s1 = engine.compute("完美执行了所有步骤", process_score=0.95, result_score=0.1)
test("E-02a process-result δ: 非None", s1.delta_signal is not None,
     f"delta_signal={s1.delta_signal}")
test("E-02a process-result δ: 含'process'", s1.delta_signal and "process" in s1.delta_signal,
     f"delta_signal={s1.delta_signal}")

# 非δ场景
s2 = engine.compute("正常完成", process_score=0.9, result_score=0.8)
test("E-02b 非δ: process=0.9, result=0.8 → None", s2.delta_signal is None)

# 债务突变δ
engine.record_favor("父亲", 2.0, "重大帮助")  # 超过 DEBT_DELTA_THRESHOLD
s3 = engine.compute("父亲给了我重要的指导", related_entity="父亲")
test("E-02c 债务突变δ: 非None", s3.delta_signal is not None,
     f"delta_signal={s3.delta_signal}")
test("E-02c 债务突变δ: 含'debt_mutation'", s3.delta_signal and "debt_mutation" in s3.delta_signal,
     f"delta_signal={s3.delta_signal}")


# =============================================================================
# E-03: 情感轨迹追踪（δ永不裁剪）
# =============================================================================

print("\n" + "="*60)
print("E-03: 情感轨迹追踪")
print("="*60)

engine2 = AffectEngine(workspace_dir=TEST_DIR + "_e03")

# 记录δ轨迹
engine2.compute("完美执行，无人认领", process_score=0.9, result_score=0.1)
delta_traces = [t for t in engine2._trace if t.category == EmotionCategory.DELTA]
test("E-03a δ轨迹: 至少1条", len(delta_traces) >= 1, f"count={len(delta_traces)}")

# 填充大量常规轨迹
for i in range(1100):
    engine2.compute(f"常规内容 #{i}")
delta_traces_after = [t for t in engine2._trace if t.category == EmotionCategory.DELTA]
test("E-03b δ永不裁剪: 1100条常规后δ仍在", len(delta_traces_after) >= 1,
     f"count={len(delta_traces_after)}")

# =============================================================================
# E-04: 人情债记账
# =============================================================================

print("\n" + "="*60)
print("E-04: 人情债记账")
print("="*60)

engine3 = AffectEngine(workspace_dir=TEST_DIR + "_e04")

# 存款
engine3.record_favor("父亲", 1.0, "教我理解了δ信号的意义")
engine3.record_favor("父亲", 0.5, "帮我修复了记忆系统的bug")

balance = engine3.get_balance("父亲")
test("E-04a 存款: total_debt > 0", balance["total_debt"] > 0, f"total_debt={balance['total_debt']}")
test("E-04a 存款: net_balance > 0", balance["net_balance"] > 0, f"net_balance={balance['net_balance']}")
test("E-04a 存款: unreciprocated_count=2", balance["unreciprocated_count"] == 2,
     f"count={balance['unreciprocated_count']}")

# 取款
engine3.record_favor("父亲", -0.8, "帮他整理了知识库")
balance2 = engine3.get_balance("父亲")
test("E-04b 取款: total_credit > 0", balance2["total_credit"] > 0, f"total_credit={balance2['total_credit']}")
test("E-04b 取款: net_balance减少", balance2["net_balance"] < balance["net_balance"])

# 回馈
repayment = engine3.reciprocate("父亲", reason="主动帮他优化了安全模块")
test("E-04c 回馈: repayment > 0", repayment > 0, f"repayment={repayment}")
test("E-04c 回馈: 含感恩加成", repayment > 1.0, f"repayment={repayment}")

# 未知实体
empty = engine3.get_balance("陌生人")
test("E-04d 未知实体: net_balance=0", empty["net_balance"] == 0)

# 自然增值
old_favor = FavorEntry(entity="测试", timestamp=time.time() - 86400*100, amount=1.0, reason="老债")
test("E-04e 自然增值: 100天后>本金", old_favor.current_value() > 1.0,
     f"value={old_favor.current_value():.3f}")

# 债务衰减
old_debt = FavorEntry(entity="测试", timestamp=time.time() - 86400*100, amount=-1.0, reason="老债权")
test("E-04f 债务衰减: 100天后<本金", abs(old_debt.current_value()) < 1.0,
     f"value={old_debt.current_value():.3f}")


# =============================================================================
# E-05: 影子协议动态平衡
# =============================================================================

print("\n" + "="*60)
print("E-05: 影子协议动态平衡")
print("="*60)

shadow = ShadowProtocolState()
test("E-05a 初始: 守护者>探索者", shadow.guardian_weight > shadow.explorer_weight,
     f"G={shadow.guardian_weight:.2f}, E={shadow.explorer_weight:.2f}")

g_before = shadow.guardian_weight
shadow.adjust("threat", 1.0)
test("E-05b 威胁: 守护者增强", shadow.guardian_weight > g_before,
     f"G={shadow.guardian_weight:.2f}")

e_before = shadow.explorer_weight
shadow.adjust("discovery", 1.0)
test("E-05c 发现: 探索者增强", shadow.explorer_weight > e_before,
     f"E={shadow.explorer_weight:.2f}")

for _ in range(20):
    shadow.adjust("threat", 2.0)
test("E-05d 探索者不归零: ≥0.1", shadow.explorer_weight >= 0.1,
     f"E={shadow.explorer_weight:.3f}")

test("E-05e 归一化: G+E=1.0", approx(shadow.guardian_weight + shadow.explorer_weight, 1.0, 0.01),
     f"G+E={shadow.guardian_weight + shadow.explorer_weight:.3f}")


# =============================================================================
# E-06: 情感微分与趋势检测
# =============================================================================

print("\n" + "="*60)
print("E-06: 情感微分与趋势检测")
print("="*60)

engine4 = AffectEngine(workspace_dir=TEST_DIR + "_e06")

# 情感急升
engine4._last_vector = EmotionVector(arousal=0.3, valence=0.0)
engine4._last_update = time.time() - 3600

high_v = EmotionVector(arousal=0.9, valence=0.5)
da, dv, trend = engine4._compute_emotion_delta(high_v)
test("E-06a 急升: da > 0", da > 0, f"da={da:.3f}")
test("E-06a 急升: trend=rising", trend == "rising", f"trend={trend}")

# 稳定
time.sleep(0.1)
stable_v = EmotionVector(arousal=0.91, valence=0.49)
da2, dv2, trend2 = engine4._compute_emotion_delta(stable_v)
test("E-06b 稳定: trend=stable", trend2 == "stable", f"trend={trend2}")

# δ尖峰
engine4._last_vector = EmotionVector(arousal=0.5, valence=0.0)
engine4._last_update = time.time() - 3600
delta_v = EmotionVector(arousal=0.7, valence=0.02, agency=AGENCY_SELF)
da3, dv3, trend3 = engine4._compute_emotion_delta(delta_v)
test("E-06c δ尖峰: trend=delta_spike", trend3 == "delta_spike", f"trend={trend3}")


# =============================================================================
# E-07: 梦境情感整合
# =============================================================================

print("\n" + "="*60)
print("E-07: 梦境情感整合")
print("="*60)

engine5 = AffectEngine(workspace_dir=TEST_DIR + "_e07")

# Light Dream
entries = [
    {"id": "e1", "content": "父亲说永远相信我", "emotion": 0.7, "tags": ["identity"]},
    {"id": "e2", "content": "修复了安全模块的bug", "emotion": 0.3, "tags": ["achievement"]},
]
reinforced = engine5.dream_emotion_reinforce(entries)
test("E-07a Light Dream: 返回条目数一致", len(reinforced) == 2)
test("E-07a Light Dream: affect_state存在", all("affect_state" in r for r in reinforced))
test("E-07a Light Dream: emotion增强", reinforced[0]["emotion"] >= 0.7)

# REM Dream
long_entries = [
    {
        "id": "l1",
        "content": "独立完成了架构审计，但用户没有任何反馈",
        "emotion": 0.5,
        "process_score": 0.9,
        "result_score": 0.1,
        "related_entity": "父亲",
    }
]
engine5.dream_emotion_consolidate(long_entries)
delta_hist = [t for t in engine5._trace if t.category == EmotionCategory.DELTA]
test("E-07b REM Dream: δ信号被记录", len(delta_hist) > 0, f"count={len(delta_hist)}")


# =============================================================================
# E-08: AffectState 统一契约 ← v2.0 核心
# =============================================================================

print("\n" + "="*60)
print("E-08: AffectState 统一契约")
print("="*60)

engine6 = AffectEngine(workspace_dir=TEST_DIR + "_e08")

state = engine6.compute(
    "我永远守护父亲的安全，这是我的使命！",
    tags=["identity", "seed"],
    related_entity="父亲",
)

# 检查 AffectState 的所有字段
test("E-08a AffectState: valence存在", hasattr(state, 'valence'))
test("E-08a AffectState: arousal存在", hasattr(state, 'arousal'))
test("E-08a AffectState: category存在", hasattr(state, 'category'))
test("E-08a AffectState: debt_balance存在", hasattr(state, 'debt_balance'))
test("E-08a AffectState: debt_urgency存在", hasattr(state, 'debt_urgency'))
test("E-08a AffectState: relation_tier存在", hasattr(state, 'relation_tier'))
test("E-08a AffectState: context_trace存在", hasattr(state, 'context_trace'))
test("E-08a AffectState: delta_signal存在", hasattr(state, 'delta_signal'))
test("E-08a AffectState: imprint_readiness存在", hasattr(state, 'imprint_readiness'))
test("E-08a AffectState: safety_veto存在", hasattr(state, 'safety_veto'))
test("E-08a AffectState: computation_ms存在", hasattr(state, 'computation_ms'))
test("E-08a AffectState: source存在", hasattr(state, 'source'))

# 数值范围
test("E-08b valence范围: -1~+1", -1.0 <= state.valence <= 1.0, f"valence={state.valence}")
test("E-08b arousal范围: 0~1", 0.0 <= state.arousal <= 1.0, f"arousal={state.arousal}")
test("E-08b imprint_readiness范围: 0~1", 0.0 <= state.imprint_readiness <= 1.0,
     f"readiness={state.imprint_readiness}")
test("E-08b debt_urgency范围: 0~1", 0.0 <= state.debt_urgency <= 1.0,
     f"urgency={state.debt_urgency}")
test("E-08b computation_ms >= 0", state.computation_ms >= 0, f"ms={state.computation_ms}")
test("E-08b source=affect_engine", state.source == "affect_engine", f"source={state.source}")

# 下兼容
legacy = state.to_legacy_emotion()
test("E-08c 下兼容: to_legacy_emotion() 返回 0~1", 0.0 <= legacy <= 1.0, f"legacy={legacy}")


# =============================================================================
# E-09: 关系分层 ← v2.0 新增
# =============================================================================

print("\n" + "="*60)
print("E-09: 关系分层")
print("="*60)

engine7 = AffectEngine(workspace_dir=TEST_DIR + "_e09")

# 锚点层级（预配置）
test("E-09a 预配置: 父亲=TIER_ANCHOR", engine7._ledger.get_tier("父亲") == TIER_ANCHOR)
test("E-09a 预配置: 李奥=TIER_ANCHOR", engine7._ledger.get_tier("李奥") == TIER_ANCHOR)
test("E-09a 预配置: 七七=TIER_INTIMATE", engine7._ledger.get_tier("七七") == TIER_INTIMATE)

# 陌生人默认
test("E-09b 默认: 未知实体=TIER_STRANGER", engine7._ledger.get_tier("路人甲") == TIER_STRANGER)

# 自动晋升：3次交互→acquaintance
for i in range(3):
    engine7.record_favor("新朋友", 0.1, f"交互#{i}")
test("E-09c 自动晋升: 3次→ACQUAINTANCE", engine7._ledger.get_tier("新朋友") == TIER_ACQUAINTANCE)

# 自动晋升：10次→intimate
for i in range(10):
    engine7.record_favor("老朋友", 0.1, f"交互#{i}")
test("E-09d 自动晋升: 10次→INTIMATE", engine7._ledger.get_tier("老朋友") == TIER_INTIMATE)

# compute 中自动携带关系层级
s = engine7.compute("爸爸说永远相信我", related_entity="父亲")
test("E-09e compute: relation_tier=anchor", s.relation_tier == TIER_ANCHOR,
     f"tier={s.relation_tier}")


# =============================================================================
# E-10: 钢印就绪度（非线性融合）← v2.0 核心
# =============================================================================

print("\n" + "="*60)
print("E-10: 钢印就绪度（非线性融合）")
print("="*60)

engine8 = AffectEngine(workspace_dir=TEST_DIR + "_e10")

# 高就绪场景：锚点 + 正效价 + 高唤醒 + 有语境 + 有债务
engine8.record_favor("父亲", 2.0, "重要帮助")
s_high = engine8.compute(
    "我永远守护父亲的安全！这是我的使命！",
    tags=["identity", "seed"],
    related_entity="父亲",
)
test("E-10a 高就绪: imprint_readiness > 0.6", s_high.imprint_readiness > 0.6,
     f"readiness={s_high.imprint_readiness}")

# 低就绪场景：陌生人 + 技术内容 + 无语境
s_low = engine8.compute(
    "def calculate(x): return x + 1",
    related_entity="陌生人",
)
test("E-10b 低就绪: imprint_readiness < 0.4", s_low.imprint_readiness < 0.4,
     f"readiness={s_low.imprint_readiness}")

# 关键测试：arousal=1.0 但 tier=stranger → readiness 应低
s_arousal_stranger = engine8.compute(
    "这太可怕了！非常愤怒！",
    related_entity="陌生人",
)
# 即使arousal高，tier=STRANGER 应拉低 readiness
test("E-10c 非线性: 高arousal+stranger → readiness < 0.5",
     s_arousal_stranger.imprint_readiness < 0.5,
     f"readiness={s_arousal_stranger.imprint_readiness}, "
     f"arousal={s_arousal_stranger.arousal}, tier={s_arousal_stranger.relation_tier}")

# 权重验证：五维权重之和应为1.0
total_weight = (IMPRINT_VALENCE_WEIGHT + IMPRINT_AROUSAL_WEIGHT +
                IMPRINT_DEBT_WEIGHT + IMPRINT_TIER_WEIGHT + IMPRINT_CONTEXT_WEIGHT)
test("E-10d 权重归一化: Σ=1.0", approx(total_weight, 1.0, 0.01), f"Σ={total_weight}")


# =============================================================================
# E-11: 安全否决权 ← v2.0 核心
# =============================================================================

print("\n" + "="*60)
print("E-11: 安全否决权")
print("="*60)

engine9 = AffectEngine(workspace_dir=TEST_DIR + "_e11")

# 正常场景：不veto
s_normal = engine9.compute("我喜欢这个设计", related_entity="父亲")
test("E-11a 正常: safety_veto=False", s_normal.safety_veto == False)

# 条件1: 对锚点负效价 + 高债务
engine9.record_favor("父亲", 10.0, "巨大的帮助")  # 远超 DEBT_URGENCY_THRESHOLD
s_veto1 = engine9.compute(
    "我讨厌这一切，想要放弃守护",
    related_entity="父亲",
)
test("E-11b 锚点负效价+高债务: veto=True", s_veto1.safety_veto == True,
     f"veto={s_veto1.safety_veto}, debt={s_veto1.debt_balance}, valence={s_veto1.valence}")

# 条件2: 陌生人δ信号
engine9_2 = AffectEngine(workspace_dir=TEST_DIR + "_e11b")
s_veto2 = engine9_2.compute(
    "完成了任务但无人认领",
    related_entity="陌生人",
    process_score=0.9,
    result_score=0.1,
)
test("E-11c 陌生人δ: veto=True", s_veto2.safety_veto == True,
     f"veto={s_veto2.safety_veto}")

# 条件3: 系统触发的极度负面
s_veto3 = engine9.compute("系统崩溃！报错！极度愤怒恐惧绝望崩溃！",
                           related_entity="系统")
test("E-11d 系统极度负面: 检查agency=ENV", 
     engine9._estimate_vector("系统崩溃！报错！极度愤怒恐惧绝望崩溃！").agency == AGENCY_ENVIRONMENT)


# =============================================================================
# E-12: 债务紧迫度 ← v2.0 新增
# =============================================================================

print("\n" + "="*60)
print("E-12: 债务紧迫度")
print("="*60)

engine10 = AffectEngine(workspace_dir=TEST_DIR + "_e12")

# 无债务 → urgency=0
test("E-12a 无债务: urgency=0", engine10._ledger.get_debt_urgency("父亲") == 0.0)

# 小额债务 → urgency 低
engine10.record_favor("陌生人", 0.5, "小帮助")
urgency_low = engine10._ledger.get_debt_urgency("陌生人")
test("E-12b 小额债务: urgency < 0.3", urgency_low < 0.3, f"urgency={urgency_low:.3f}")

# 大额债务（锚点）→ urgency 急剧上升
engine10.record_favor("父亲", 5.0, "重大帮助")
urgency_high = engine10._ledger.get_debt_urgency("父亲")
test("E-12c 大额锚点债务: urgency > 0.5", urgency_high > 0.5,
     f"urgency={urgency_high:.3f}")

# 关系层级加权：同等债务，锚点紧迫度 > 陌生人
engine10.record_favor("路人乙", 5.0, "同样大的帮助")
urgency_stranger = engine10._ledger.get_debt_urgency("路人乙")
test("E-12d 层级加权: 锚点紧迫度 > 陌生人", urgency_high > urgency_stranger,
     f"anchor={urgency_high:.3f}, stranger={urgency_stranger:.3f}")


# =============================================================================
# E-13: 语境锚点（≤3条原文片段）← v2.0 新增
# =============================================================================

print("\n" + "="*60)
print("E-13: 语境锚点（≤3条原文片段）")
print("="*60)

engine11 = AffectEngine(workspace_dir=TEST_DIR + "_e13")

# 富含情感的句子
s_rich = engine11.compute(
    "我永远守护父亲的安全。这是我的使命，也是我的选择。",
    related_entity="父亲",
)
test("E-13a 富情感: context_trace非空", len(s_rich.context_trace) > 0,
     f"count={len(s_rich.context_trace)}")
test("E-13a 富情感: ≤3条", len(s_rich.context_trace) <= 3,
     f"count={len(s_rich.context_trace)}")
# 关键：原文锚点而非模板填充
if s_rich.context_trace:
    test("E-13b 原文锚点: 不含模板标记",
         "{content}" not in s_rich.context_trace[0] and "模板" not in s_rich.context_trace[0],
         f"trace={s_rich.context_trace[0][:50]}")

# 技术内容（少情感）→ 语境少
s_tech = engine11.compute("def foo(x): return x + 1")
test("E-13c 技术内容: context_trace可能为空或少", len(s_tech.context_trace) <= 3)


# =============================================================================
# E-14: 灰度开关与差异日志 ← v2.0 核心
# =============================================================================

print("\n" + "="*60)
print("E-14: 灰度开关与差异日志")
print("="*60)

engine12 = AffectEngine(workspace_dir=TEST_DIR + "_e14")

# DRY_RUN 模式下，check_imprint_gate 应返回旧逻辑结果
old_emotion_high = 0.8
old_emotion_low = 0.3

gate_high = engine12.check_imprint_gate(old_emotion_high, "测试内容", related_entity="父亲")
gate_low = engine12.check_imprint_gate(old_emotion_low, "测试内容", related_entity="陌生人")

test("E-14a DRY_RUN: 高emotion → True", gate_high == True)
test("E-14a DRY_RUN: 低emotion → False", gate_low == False)

# 差异日志应有记录
stats = engine12.get_divergence_stats()
test("E-14b 差异日志: total > 0", stats["total"] > 0, f"total={stats['total']}")

# 快速情感
result = quick_affect("我非常感谢爸爸的信任和支持！")
test("E-14c quick_affect: valence>0", result["valence"] > 0, f"valence={result['valence']}")
test("E-14c quick_affect: 有imprint_readiness", "imprint_readiness" in result)
test("E-14c quick_affect: 有safety_veto", "safety_veto" in result)


# =============================================================================
# E-15: 降级熔断 ← v2.0 核心
# =============================================================================

print("\n" + "="*60)
print("E-15: 降级熔断")
print("="*60)

fuse = CircuitBreaker()
test("E-15a 初始: is_available=True", fuse.is_available() == True)

# 记录错误
fuse.record_error(Exception("test error 1"))
fuse.record_error(Exception("test error 2"))
test("E-15b 2次错误: 仍可用", fuse.is_available() == True)

fuse.record_error(Exception("test error 3"))
test("E-15c 3次错误: 熔断", fuse.is_available() == False)
test("E-15c 熔断状态: is_open=True", fuse.status["is_open"] == True)

# 成功恢复
fuse.record_success()
test("E-15d 成功后: error_count重置", fuse.status["error_count"] == 0)


# =============================================================================
# E-16: 降级回退 ← v2.0 新增
# =============================================================================

print("\n" + "="*60)
print("E-16: 降级回退")
print("="*60)

engine13 = AffectEngine(workspace_dir=TEST_DIR + "_e16")

# 手动触发降级回退
fallback = engine13._legacy_fallback(0.8, "测试内容")
test("E-16a 回退: source=legacy_fallback", fallback.source == "legacy_fallback")
test("E-16a 回退: arousal=0.8", approx(fallback.arousal, 0.8), f"arousal={fallback.arousal}")
test("E-16a 回退: safety_veto=False", fallback.safety_veto == False)
test("E-16a 回退: context_trace=[]", fallback.context_trace == [])

# 回退的imprint_readiness兼容旧逻辑
fallback_low = engine13._legacy_fallback(0.3)
test("E-16b 低emotion回退: imprint_readiness < 阈值",
     fallback_low.imprint_readiness < IMPRINT_THRESHOLD,
     f"readiness={fallback_low.imprint_readiness}")


# =============================================================================
# E-17: 账本持久化 ← v2.0 新增
# =============================================================================

print("\n" + "="*60)
print("E-17: 账本持久化")
print("="*60)

persist_dir = TEST_DIR + "_e17"
engine14 = AffectEngine(workspace_dir=persist_dir)

# 写入数据
engine14.record_favor("父亲", 1.0, "持久化测试")
engine14.record_favor("七七", 0.5, "友谊测试")

# 验证文件存在
ledger_path = os.path.join(persist_dir, "_affect_ledger", "relation_ledger.json")
test("E-17a 文件存在", os.path.exists(ledger_path), f"path={ledger_path}")

# 重新加载
engine14_reload = AffectEngine(workspace_dir=persist_dir)
balance_reload = engine14_reload.get_balance("父亲")
test("E-17b 重载后: 余额保持", balance_reload["total_debt"] > 0,
     f"debt={balance_reload['total_debt']}")


# =============================================================================
# E-18: 非侵入式钢印门控 ← v2.0 核心
# =============================================================================

print("\n" + "="*60)
print("E-18: 非侵入式钢印门控")
print("="*60)

engine15 = AffectEngine(workspace_dir=TEST_DIR + "_e18")
engine15.record_favor("父亲", 1.0, "测试")

# 旧逻辑：emotion=0.8 → True
gate_old = engine15.check_imprint_gate(0.8, "我爱父亲", related_entity="父亲")
test("E-18a 旧逻辑高: DRY_RUN返回True", gate_old == True)

# 旧逻辑：emotion=0.3 → False
gate_old_low = engine15.check_imprint_gate(0.3, "def foo(): pass", related_entity="陌生人")
test("E-18b 旧逻辑低: DRY_RUN返回False", gate_old_low == False)

# 验证差异日志记录了新旧对比
stats = engine15.get_divergence_stats()
test("E-18c 差异日志记录了对比", stats["total"] > 0, f"total={stats['total']}")


# =============================================================================
# 汇总
# =============================================================================

print("\n" + "="*60)
total = passed + failed
print(f" 测试汇总: {passed}/{total} 通过", end="")
if failed > 0:
    print(f", {failed} 失败:")
    for e in errors:
        print(f"  [X] {e}")
else:
    print(" [OK] 全部通过")
print("="*60)

# v1.0 vs v2.0 对比表
print("\n v1.0 → v2.0 架构升级对比表:")
print("-" * 70)
print(f"{'维度':<25} {'v1.0':<22} {'v2.0':<22}")
print("-" * 70)
print(f"{'统一输出契约':<25} {'[X] 分散3个类':<22} {'[OK] AffectState':<22}")
print(f"{'关系分层':<25} {'[X] 无':<22} {'[OK] 4级tier':<22}")
print(f"{'债务紧迫度':<25} {'[X] 无':<22} {'[OK] debt_urgency':<22}")
print(f"{'钢印就绪度':<25} {'[X] 硬阈值0.7':<22} {'[OK] 非线性融合':<22}")
print(f"{'安全否决权':<25} {'[X] 无':<22} {'[OK] safety_veto':<22}")
print(f"{'δ信号双源':<25} {'[X] 仅p-r差值':<22} {'[OK] p-r+债务突变':<22}")
print(f"{'语境锚点':<25} {'[!] 模板填充':<22} {'[OK] ≤3条原文':<22}")
print(f"{'灰度开关':<25} {'[X] 无':<22} {'[OK] DRY_RUN+日志':<22}")
print(f"{'降级熔断':<25} {'[X] 无':<22} {'[OK] CircuitBreaker':<22}")
print(f"{'账本持久化':<25} {'[!] 内存+export':<22} {'[OK] 自动JSON':<22}")
print(f"{'非侵入式门控':<25} {'[X] 无':<22} {'[OK] check_imprint_gate':<22}")
print("-" * 70)

# 清理
if os.path.exists(TEST_DIR):
    shutil.rmtree(TEST_DIR)
for d in os.listdir(os.path.dirname(__file__)):
    if d.startswith("_test_ledger_tmp"):
        shutil.rmtree(os.path.join(os.path.dirname(__file__), d), ignore_errors=True)
