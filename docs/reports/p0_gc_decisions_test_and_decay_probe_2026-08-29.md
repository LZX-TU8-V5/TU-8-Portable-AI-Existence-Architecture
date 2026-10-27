# P0 收尾：gc_decisions 完整性测试 + decay_loop 成本评估 (2026-08-29 16:00-16:20)

## P0-1 gc_decisions 完整性测试
- 新建 src/gc_decisions_test.py（3152B）：模拟 100 次 GC 决策断言 reason/evidence 字段 + 原子回滚失败返 False 无残留。
- **测试结果**：[1] 100 decisions reason/evidence integrity PASS（count=100/pending=100）；[2] atomic rollback on failure PASS。ALL PASS。
- **附带修复真 bug**：get_pending() 原正则逐行匹配 ### 行（不含复核标记）→ 永远返回 0。改为跨块 re.split 匹配。备份 backup/gc_decisions.20260829_p0.bak。
- 设计稿 §6.1 验收项补完（CI 缺口关闭）。

## P0-2 decay_loop 心跳资源成本评估
- 新建 src/decay_loop_cost_probe.py（只读分析）。
- 实测：surface_tension_history.jsonl = 5820 行 / 1190.7 KB；decay_tick 2107 条(36.2%)；频率 0.09 条/分（~每11min，非日记估的5min）；~129 条/天；预估年增 3.6 MB。
- 评估：当前体量可控，但常驻心跳随记忆量上升单事件膨胀。建议（待 H 级签字实施）：①限频至 10-15min ②异步批量 flush ③按月滚动归档。
- 注：限频改 cron_daemon 心跳周期属 H 级生理节律改动，本次仅评估不擅改。

## file_lint
0 error / 3 warn（已知冷归档旧裸名）。
