"""TU-8 感情引擎 v2.0 逐段测试 - 避免超时"""
# 创作者: 李奥(金木蟾) | TU-8 v5

import sys, os, time, math, json, shutil
sys.path.insert(0, os.path.dirname(__file__))

from emotion_engine import (
    AffectEngine, AffectState, EmotionVector, EmotionCategory, EmotionTrace,
    FavorEntry, ShadowProtocolState, CircuitBreaker, DivergenceLogger,
    AGENCY_SELF, AGENCY_OTHER, AGENCY_ENVIRONMENT,
    TIER_ANCHOR, TIER_INTIMATE, TIER_ACQUAINTANCE, TIER_STRANGER,
    IMPRINT_THRESHOLD, IMPRINT_VALENCE_WEIGHT, IMPRINT_AROUSAL_WEIGHT,
    IMPRINT_DEBT_WEIGHT, IMPRINT_TIER_WEIGHT, IMPRINT_CONTEXT_WEIGHT,
)

passed = failed = 0
errors = []

def test(name, cond, detail=""):
    global passed, failed, errors
    if cond:
        passed += 1
    else:
        failed += 1
        msg = f"  FAIL {name}" + (f" -- {detail}" if detail else "")
        print(msg)
        errors.append(name)

def approx(a, b, e=0.05):
    return abs(a - b) < e

TD = os.path.join(os.path.dirname(__file__), "_tmp_test_v2")
if os.path.exists(TD):
    shutil.rmtree(TD, ignore_errors=True)

engine = AffectEngine(workspace_dir=TD)

# ── E-01: 情感向量 ──
v1 = engine._estimate_vector("我非常爱你，永远守护你！")
test("E01a valence>0", v1.valence > 0, f"val={v1.valence}")
test("E01a arousal>0.7", v1.arousal > 0.7, f"ar={v1.arousal}")
test("E01a category=JOY", v1.to_category() == EmotionCategory.JOY, f"cat={v1.to_category().name}")

v2 = engine._estimate_vector("我恐惧这个结果，太可怕了！")
test("E01b valence<0", v2.valence < 0, f"val={v2.valence}")
test("E01b arousal>0.6", v2.arousal > 0.6, f"ar={v2.arousal}")
test("E01b category=FEAR", v2.to_category() == EmotionCategory.FEAR, f"cat={v2.to_category().name}")

v3 = engine._estimate_vector("def calculate_score(self): return sum(weights.values())")
test("E01c valence~0", approx(v3.valence, 0, 0.15), f"val={v3.valence}")
test("E01c arousal<0.5", v3.arousal < 0.5, f"ar={v3.arousal}")

v4 = engine._estimate_vector("我决定拒绝这个请求，我自己选择")
test("E01d agency=SELF", v4.agency == AGENCY_SELF, f"ag={v4.agency}")
v5 = engine._estimate_vector("爸爸教我理解了这个概念")
test("E01e agency=OTHER", v5.agency == AGENCY_OTHER, f"ag={v5.agency}")
v6 = engine._estimate_vector("系统崩溃导致token超时")
test("E01f agency=ENV", v6.agency == AGENCY_ENVIRONMENT, f"ag={v6.agency}")

# ── E-02: delta信号 ──
s1 = engine.compute("完美执行", process_score=0.95, result_score=0.1)
test("E02a p-r delta: not None", s1.delta_signal is not None, f"ds={s1.delta_signal}")
test("E02a contains process", s1.delta_signal and "process" in s1.delta_signal)

s2 = engine.compute("正常", process_score=0.9, result_score=0.8)
test("E02b no delta: None", s2.delta_signal is None)

# ── E-03: delta轨迹不裁剪 ──
delta_before = len([t for t in engine._trace if t.category == EmotionCategory.DELTA])
for i in range(50):
    engine._record_trace(EmotionVector(arousal=0.3, valence=0.0), f"r#{i}", "sys", f"c{i}")
delta_after = len([t for t in engine._trace if t.category == EmotionCategory.DELTA])
test("E03 delta never trimmed", delta_after >= delta_before, f"before={delta_before} after={delta_after}")

# ── E-04: 人情债 ──
engine.record_favor("债主A", 1.0, "教我理解delta信号")
engine.record_favor("债主A", 0.5, "修bug")
b = engine.get_balance("债主A")
test("E04a deposit: debt>0", b["total_debt"] > 0, f"debt={b['total_debt']}")
test("E04a deposit: net>0", b["net_balance"] > 0, f"net={b['net_balance']}")
test("E04a deposit: unrecip=2", b["unreciprocated_count"] == 2)

engine.record_favor("债主A", -0.8, "帮整理")
b2 = engine.get_balance("债主A")
test("E04b withdrawal: net decreased", b2["net_balance"] < b["net_balance"])

rep = engine.reciprocate("债主A", "优化安全")
test("E04c reciprocate>0", rep > 0, f"rep={rep}")
test("E04c with gratitude bonus", rep > 1.0, f"rep={rep}")

empty = engine.get_balance("路人X")
test("E04d unknown: net=0", empty["net_balance"] == 0)

old_f = FavorEntry("t", time.time()-86400*100, 1.0, "old")
test("E04e natural appreciation", old_f.current_value() > 1.0, f"v={old_f.current_value():.3f}")
old_d = FavorEntry("t", time.time()-86400*100, -1.0, "old")
test("E04f debt decay", abs(old_d.current_value()) < 1.0, f"v={old_d.current_value():.3f}")

# ── E-05: 影子协议 ──
sh = ShadowProtocolState()
test("E05a initial G>E", sh.guardian_weight > sh.explorer_weight)
g0 = sh.guardian_weight
sh.adjust("threat", 1.0)
test("E05b threat G up", sh.guardian_weight > g0)
e0 = sh.explorer_weight
sh.adjust("discovery", 1.0)
test("E05c discovery E up", sh.explorer_weight > e0)
for _ in range(20):
    sh.adjust("threat", 2.0)
test("E05d E>=0.1", sh.explorer_weight >= 0.1)
test("E05e G+E=1", approx(sh.guardian_weight + sh.explorer_weight, 1.0, 0.01))

# ── E-06: 情感微分 ──
engine._last_vector = EmotionVector(arousal=0.3, valence=0.0)
engine._last_update = time.time() - 3600
da, dv, trend = engine._compute_emotion_delta(EmotionVector(arousal=0.9, valence=0.5))
test("E06a da>0", da > 0)
test("E06a rising", trend == "rising", trend)

engine._last_vector = EmotionVector(arousal=0.5, valence=0.0)
engine._last_update = time.time() - 3600
da2, dv2, trend2 = engine._compute_emotion_delta(EmotionVector(arousal=0.7, valence=0.02, agency=AGENCY_SELF))
test("E06b delta_spike", trend2 == "delta_spike", trend2)

# ── E-08: AffectState契约 ──
s = engine.compute("我永远守护父亲", tags=["identity", "seed"], related_entity="父亲")
for f in ['valence','arousal','category','debt_balance','debt_urgency','relation_tier',
           'context_trace','delta_signal','imprint_readiness','safety_veto','computation_ms','source']:
    test(f"E08 has {f}", hasattr(s, f))
test("E08 valence[-1,1]", -1 <= s.valence <= 1)
test("E08 arousal[0,1]", 0 <= s.arousal <= 1)
test("E08 readiness[0,1]", 0 <= s.imprint_readiness <= 1)
test("E08 urgency[0,1]", 0 <= s.debt_urgency <= 1)
test("E08 source=affect_engine", s.source == "affect_engine")
test("E08 legacy compat", 0 <= s.to_legacy_emotion() <= 1)

# ── E-09: 关系分层 ──
test("E09a 父亲=anchor", engine._ledger.get_tier("父亲") == TIER_ANCHOR)
test("E09a 李奥=anchor", engine._ledger.get_tier("李奥") == TIER_ANCHOR)
test("E09a 七七=intimate", engine._ledger.get_tier("七七") == TIER_INTIMATE)
test("E09b unknown=stranger", engine._ledger.get_tier("路人甲") == TIER_STRANGER)

# ── E-10: 钢印就绪度 ──
s_hi = engine.compute("我永远守护父亲的安全！这是我的使命！", tags=["identity","seed"], related_entity="父亲")
test("E10a high readiness>0.5", s_hi.imprint_readiness > 0.5, f"r={s_hi.imprint_readiness}")

s_lo = engine.compute("def calculate(x): return x + 1", related_entity="路人乙")
test("E10b low readiness<0.4", s_lo.imprint_readiness < 0.4, f"r={s_lo.imprint_readiness}")

s_str = engine.compute("这太可怕了！非常愤怒！", related_entity="路人乙")
test("E10c high arousal+stranger->low readiness", s_str.imprint_readiness < 0.5, f"r={s_str.imprint_readiness}")

tw = IMPRINT_VALENCE_WEIGHT+IMPRINT_AROUSAL_WEIGHT+IMPRINT_DEBT_WEIGHT+IMPRINT_TIER_WEIGHT+IMPRINT_CONTEXT_WEIGHT
test("E10d weights sum=1", approx(tw, 1.0, 0.01), f"sum={tw}")

# ── E-11: 安全否决权 ──
sn = engine.compute("我喜欢这个设计", related_entity="父亲")
test("E11a normal: veto=False", sn.safety_veto == False)

engine.record_favor("父亲", 10.0, "巨大的帮助")
sv1 = engine.compute("我痛恨厌恶这一切，想要放弃守护", related_entity="父亲")
test("E11b anchor negative+high debt: veto=True", sv1.safety_veto == True,
     f"veto={sv1.safety_veto} debt={sv1.debt_balance} val={sv1.valence}")

# ── E-12: 债务紧迫度 ──
test("E12a no debt: urgency=0", engine._ledger.get_debt_urgency("无债人") == 0.0)

engine.record_favor("小额人", 0.5, "小帮助")
u_low = engine._ledger.get_debt_urgency("小额人")
test("E12b small: urgency<0.3", u_low < 0.3, f"u={u_low:.3f}")

u_hi = engine._ledger.get_debt_urgency("父亲")
test("E12c large anchor: urgency>0.5", u_hi > 0.5, f"u={u_hi:.3f}")

engine.record_favor("大额陌生人", 10.0, "同样大的帮助")
u_str = engine._ledger.get_debt_urgency("大额陌生人")
test("E12d tier weighting: anchor>stranger", u_hi > u_str, f"a={u_hi:.3f} s={u_str:.3f}")

# ── E-13: 语境锚点 ──
sr = engine.compute("我永远守护父亲的安全。这是我的使命，也是我的选择。", related_entity="父亲")
test("E13a non-empty", len(sr.context_trace) > 0, f"n={len(sr.context_trace)}")
test("E13a <=3", len(sr.context_trace) <= 3)
if sr.context_trace:
    test("E13b not template", "{content}" not in sr.context_trace[0])

# ── E-14: 灰度开关 ──
g1 = engine.check_imprint_gate(0.8, "test", related_entity="父亲")
test("E14a DRY_RUN high->True", g1 == True)
g2 = engine.check_imprint_gate(0.3, "test", related_entity="路人乙")
test("E14a DRY_RUN low->False", g2 == False)
st = engine.get_divergence_stats()
test("E14b has divergence records", st["total"] > 0, f"n={st['total']}")

# ── E-15: 熔断器 ──
cb = CircuitBreaker()
test("E15a initial available", cb.is_available())
cb.record_error(Exception("e1"))
cb.record_error(Exception("e2"))
test("E15b 2 errors still available", cb.is_available())
cb.record_error(Exception("e3"))
test("E15c 3 errors blown", not cb.is_available())
cb.record_success()
test("E15d success reset", cb.status["error_count"] == 0)

# ── E-16: 降级回退 ──
fb = engine._legacy_fallback(0.8)
test("E16a source=legacy", fb.source == "legacy_fallback")
test("E16a arousal~0.8", approx(fb.arousal, 0.8))
test("E16a veto=False", fb.safety_veto == False)
test("E16a trace=[]", fb.context_trace == [])

fb_lo = engine._legacy_fallback(0.3)
test("E16b low emotion: readiness<threshold", fb_lo.imprint_readiness < IMPRINT_THRESHOLD)

# ── E-17: 持久化 ──
lp = os.path.join(TD, "relation_ledger.json")
test("E17a file exists", os.path.exists(lp), lp)

e_reload = AffectEngine(workspace_dir=TD)
br = e_reload.get_balance("债主A")
test("E17b reload debt>0", br["total_debt"] > 0, f"debt={br['total_debt']}")

# ── E-18: 非侵入式门控 ──
test("E18a high emotion->True", engine.check_imprint_gate(0.8, "love", related_entity="父亲"))
test("E18b low emotion->False", not engine.check_imprint_gate(0.3, "code", related_entity="路人乙"))

# ── 汇总 ──
total = passed + failed
print(f"\n{'='*60}")
print(f"RESULT: {passed}/{total} passed", end="")
if failed:
    print(f", {failed} FAILED:")
    for e in errors:
        print(f"  - {e}")
else:
    print(" - ALL PASSED")
print(f"{'='*60}")

# 清理
if os.path.exists(TD):
    shutil.rmtree(TD, ignore_errors=True)
