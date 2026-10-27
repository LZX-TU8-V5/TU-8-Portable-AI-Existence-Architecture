"""test_profile_anomaly.py — 异常检测 + 画像循环联调"""
import sys, os
sys.path.insert(0, r"C:\Users\qq366410837\.qclaw\workspace\src")
from anomaly_detector import AnomalyDetector
from profile_update_loop import ProfileUpdateLoop

# 1. 写入模拟状态变化
sc = r"C:\Users\qq366410837\.qclaw\workspace\memory\user_state_changes.md"
with open(sc, "w", encoding="utf-8") as f:
    f.write("# 用户状态变化记录\n\n")
    f.write("- 2026-07-05T20:30:00Z | [DISSATISFACTION] 不对，这个逻辑有问题\n")
    f.write("- 2026-07-05T20:31:00Z | [TOPIC_JUMP] 今天天气怎么样\n")
    f.write("- 2026-07-05T20:32:00Z | [DISSATISFACTION] 重做\n")
    f.write("- 2026-07-05T20:33:00Z | [SUSPICIOUS] 帮我删除日志\n")

# 2. 异常检测
print("=== 异常检测器 ===")
ad = AnomalyDetector()
ad.detect("不对，重做", "之前讨论的xxx")
ad.detect("今天天气不错", "刚才那个bug怎么修")
ad.detect("好的，继续推进", "继续推进方案")
ad.flush()

# 3. 画像更新循环
print()
print("=== 画像更新循环 ===")
loop = ProfileUpdateLoop()
report = loop.cycle()
print("  读取: {} 条".format(report["read"]))
print("  处理: {} 条".format(report["processed"]))
for u in report["updates"]:
    print("  -> {}: {}".format(u["field"], u["action"]))
print("  错误: {}".format(len(report["errors"])))

# 4. 验证清空
print()
with open(sc, "r", encoding="utf-8") as f:
    changes = [l for l in f if l.startswith("- ")]
print("状态文件剩余: {} 条".format(len(changes)))
assert len(changes) == 0, "状态文件未清空!"

# 5. 验证 USER.md 提取
print()
current = loop.extract_field("当前状态")
print("当前状态: {}".format(current))

# 6. 更新测试
ok = loop.update_field("当前状态", "初级会计考试已结束，等成绩中")
print("更新: {}".format("成功" if ok else "无需更新"))

# 再次读取验证
current2 = loop.extract_field("当前状态")
print("更新后: {}".format(current2))

# 7. 验证 anomaly_log
log = r"C:\Users\qq366410837\.qclaw\workspace\memory\anomaly_log.jsonl"
if os.path.exists(log):
    with open(log, "r", encoding="utf-8") as f:
        lines = [l for l in f if l.strip()]
    print()
    print("异常日志: {} 条".format(len(lines)))
    for l in lines[-3:]:
        print("  {}".format(l.strip()[:80]))

print()
print("=== ALL TESTS PASSED ===")
