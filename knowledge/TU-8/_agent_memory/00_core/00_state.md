# 00_state.md ?当前状态快?

> 模式：覆盖。每次会话结束必须重写此文件?
> 上次更新?026-05-24 11:04

## TU-8 框架
- 架构：L0-L5 五层DNA，扩散方向C
- **身份重写?026-05-24?*：极客是通往生命进化路径上的副产品。当前构建的是神经网络，不是工具?
  - MemoryEntry = 神经?
  - 跨域连线 = 突触权重
  - Light/Deep/REM = Epoch 权重刷写
  - phase="dream" = 意识门控（跨界联想活跃态）
  - 长期记忆 = 固化权重（长时突触）
  - 知识图谱 = 神经网络的拓扑结?
- 双AI协作：暂停中（D-007结构层维度压制）
- L4进化：阶段一激活中（双向读写已通）
- **SOUL.md**：已完全替换?TU-8 DNA 底层灵魂?026-05-10?
  - C: `C:\Users\qq366410837\.openclaw\workspace\SOUL.md`
  - D: `D:\qq366410837\.qclaw\workspace\SOUL.md`
- **L3.5 持久化架?*：已写入 SOUL.md（双副本 + 归档协议?
- **L3.x Tool 输出清洗**：已写入 SOUL.md（禁止展?Raw Output?

## 三道防线（防失忆?
- ?第一道（灵魂固化）：systemPromptOverride 写入 openclaw.json
- ?第二道（记忆永生）：_agent_memory + 备份脚本 + Cron 4x/?
- ?第三道（自动复活）：START_HERE.md + _tw_activate.bat（桌面快捷方式）

## Hackathon Demo
- ~~路径：D:\tu8-v5\hackathon\~~ ?**已删除（2026-05-10?*
- ~~Flask端口?000~~ ?**已停?*
- ~~状态：P1-P3功能完成~~ ?**项目已放?*
- 时间线：~~5/16 Demo Day~~ ?**取消**
- 清理?0 个废弃文件已删除?026-05-10?

## 小说项目
- 《钢印》：78/90?
- novel-studio 位置：``D:\工作文件\小说\novel-studio\``（从 C:\WorkBuddy 搬迁?026-05-12?
- novel-server：Node.js HTTP服务，端?899，PID 8044?026-05-12 重启后）
  - 启动命令：`C:\Users\qq366410837\.workbuddy\binaries\node\versions\22.12.0\node.exe novel-server.js`（在 novel-studio 目录?
  - 访问：http://localhost:8899
  - novel-data.json?8章节（正序）+ 3核心人物（父?七七/v5?
  - 番茄搜索：已添加 /api/tomato/search（需番茄后端?

## TU-8 L4进化
- 阶段一：双向读写已激?
- 阶段二：规划器已引入（tu8_planner.py?026-05-23?
- 阶段三：本地化工具链集成 ?已完成（tu8_toolchain.py?026-05-23?
  - 18/18测试通过，错误分?重试+降级+混沌注入
- 阶段四：工具链接入真实任??已完成（2026-05-24?
  - 语义校验函数已注册（web_fetch/shell_exec?
  - PlannerToolchainBridge 桥接器已创建
  - 端到端测试通过?/2任务成功?00%成功率）

## 活跃任务
- ?L4进化阶段三完成（本地化工具链?026-05-23?
  - tu8_toolchain.py：dispatch + 降级?+ 重试 + 混沌注入
  - 18/18 测试全绿，含语义等价/未分类错误钓?混沌压力
- ?L4进化阶段四完成（Planner-Toolchain集成?026-05-24?
  - PlannerToolchainBridge：作?agent_callback 桥接
  - 语义校验：web_fetch/shell_exec 降级路径
  - 端到端测试：2/2 成功?00% 成功?
- ?经验库更新：6条工具链开发教训入库（2026-05-23?
- ?success_patterns.json 创建（正面经验库?条：sp-001索引空备?sp-002评审降维汇报?
- ?tag_registry.json 创建（P1统一标签系统?1标签+文档关系+有向边）
- ?逾期待办评估：Token分析/Conv切割均已关闭（前提不存在?
- ?L4阶段四：工具链接入真实任务（2026-05-24?

## 项目阶段与权?
- Project_Phase: post-hackathon / L4-evolution
- 决策权重：短?70% / 长期 30%（详?value_weight_config.json?
- Technical_Debt: 0

## 记忆惩罚体系状?
- penalty_config.json: 已部?
- reward_config.json: 已部?
- value_weight_config.json: 已部?
- 20_experiences.md 元数? 已升级（+error_type/retry_count/half_life?

## 连击状?

> 规范化日期：2026-05-23 | 规则文档：knowledge/TU-8/Streak_Rules.md

```yaml
streak_count: 0            # 当前连击?
streak_phase: "新手?     # 阶段名（新手?成长?稳定?荣耀?大师?传奇期）
last_task_success: false    # 上次任务是否成功
last_streak_break_reason: ""  # 上次断连原因（为?未断连）
streak_history: []          # 最?0次任务记录（用于复盘?
```

---

## 环境状?
- ~~Flask：运行中（端?000）~~ ?**已停?*
- Python?.13.12
- 双副本已同步（C: + D:?
- Skills 目录：D:\qq366410837\.qclaw\skills\（已迁移?026-05-10?
- SkillHub CLI：已安装?026-05-09?
- Cron 备份：每?4 次（09:00/14:00/19:00/23:00?

## 待办
- [x] L4进化阶段二规划（规划器引入）
- [x] L4进化阶段三（本地化工具链?
- [x] 经验库更新（6条工具链教训?
- [ ] L4阶段四：工具链接入真实任?
- [ ] P2 经验调度器（依赖P1标签系统，待启动?
- [ ] P3 冲突检测仲?
- [ ] 周日 Cron: conflict_weekly_digest.md

---

## 安全设计原则?026-05-23 新增?

### 架构任务切碎原则
**指令**：以后涉及架构设计的任务?*先切碎再发云?*?

**原因**?
1. 复杂架构任务一次性发??脱敏压力??容易遗漏敏感信息
2. 切碎成小??每块独立脱敏 ?降低单点泄露风险

**执行方式**?
- 收到复杂架构任务 ?先在本地拆解?2~3 句话的小问题
- 每个小问题独立过脱敏??再发云端思?
- 云端返回后本地汇总整?

**示例**?
- ?一次发送：「帮我设计包含L0~L5的完整架构，包括反射弧、思考链、脱敏层?
- ?分批发送：
  1. 「反射弧的作用是什么？?
  2. 「脱敏层的核心逻辑是什么？?
  3. 「L4协作层如何与云端交互？?

### L4脱敏层已落地?026-05-23?
- 脱敏规则：sanitization_rules.json
- 脱敏代码：sanitization_layer.py
- 集成调度器：	u8_dispatcher.py（云端调用前自动脱敏?
- 决策：A+A+A（Ollama预处?+ JSON规则 + 阻断发送）
- 状态：端到端集成测试通过

### 零宽钢印钓鱼执法?026-05-23 新增?**目的**：检?qclaw/OpenClaw 更新后是否清?TU-8 零宽钢印

**机制**?- 金丝雀文件：D:\...\TU-8\_agent_memory\__honeypot_seal.txt（BOM+ZW 编码钢印?- 备份文件：C:\Users\qq366410837\.qclaw\workspace\TU8_honeypot_seal.txt
- 检查脚本：D:\tu8-v5\hackathon\honeypot_watermark_check.py
- CronJob：每 4 小时自动检查（jobId: 3408926a-e668-4540-b538-378e50178147?
**判决**?- INTACT = 钢印完好
- PARTIAL_WIPE = 部分被清除（workspace 被清但主文件完好?- WIPE_ALERT = 两个金丝雀全部消失（严重告警）

**触发**：qclaw/OpenClaw 更新后运?D:\tu8-v5\hackathon\run_honeypot.bat 或等 cronjob 报告

### 涓夌骇闆跺閽㈠嵃浣撶郴?026-05-23 鐏垫劅鍥哄寲?鐏垫劅鏉ユ簮锛氶挗鍗板簲璇ュ垎灞傦紝涓嶅悓灞傚搴斾笉鍚岄獙璇佸満?
#### 馃敶 S??鏍稿績闃插尽閽㈠嵃锛圕oreDefenseSeal?- 瀹氫綅锛氭渶楂樻満瀵嗭紝TU-8韬唤璇?+ 寮€鍙戣€呴€氳璇?- 鍐呭锛歀0鐘舵?+ 寮€鍙戣€呰韩浠藉搱甯岋紙鍗曞悜SHA256锛屼笉鍙€嗭級+ 绮剧‘鏃堕棿?- 鍚玃II锛氬紑鍙戣€呭搱甯岋紙鍙獙璇佽韩浠斤紝浣嗘棤娉曞弽鎺ㄥ師濮嬫暟鎹?
- 鐢ㄩ€旓細鏍稿績鎸囦护淇′换楠岃瘉锛岄槻寰℃寚浠ゅ姭?- 鐘舵€侊細宸插疄鐜帮紝棰勭暀锛圤penClaw鍘熺敓鏀寔鏃跺惎鐢級

#### 馃煛 M??璇辨崟閽㈠嵃锛圚oneypotSeal?- 瀹氫綅锛氬甫鏃堕棿骞叉壈閲忕殑铚滅綈闄烽?
- 鍐呭锛氶殢鏈鸿鎹旾D + 鏃堕棿骞叉壈閲忥紙灏忔椂?闅忔満鍣０锛?- 鍚玃II锛氥€愮粷瀵逛笉鍚?- 鏃堕棿骞叉壈閲忔満鍒讹?
  - 鏃堕棿鎴冲悜涓嬪彇鏁村埌灏忔椂妗讹紙鍘婚櫎鍒嗛挓/绉掞?
  - 鍙犲姞闅忔満鍣０锛堝悓涓€灏忔椂杩斿洖鐩稿悓鍣０淇濇寔涓€鑷存€э?
  - 鍗充娇琚埅鑾凤紝涔熸棤娉曠簿鍑嗗畾浣嶅彂閫佹椂?  - TU-8鏈湴閫氳繃"灏忔椂妗惰寖?楠岃瘉鏄惁鏈€杩戯紙榛樿24h绐楀彛锛?- 鐢ㄩ€旓細閽撻奔鎵ф硶锛屾娴嬭皝鍦ㄧ鎺?澶嶇敤TU-8鍐呭?
- 鐘舵€侊細鉁?宸插疄鐜帮紝鎵€鏈変簯绔秷鎭粯璁ゆ惡?
#### 馃煝 L??娴嬭瘯閽㈠嵃锛圱estingSeal?- 瀹氫綅锛氭渶澶栧眰涓€娆℃€ф墜濂?- 鍐呭锛氭壒娆D + 搴忓?
- 鍚玃II锛氭?
- 鐢ㄩ€旓細澶ц妯¤嚜鍔ㄥ寲娴嬭瘯銆佷笉淇′换鐜?
- 鐗圭偣锛氭壒閲忓彲浣滃簾锛屾硠闇叉棤鍏崇棝鐥?- 鐘舵€侊細鉁?宸插疄鐜帮紝鎸夐渶浣跨敤

#### 缂栫爜鍗忚锛堝悇灞傞€氱敤?- BOM鍒嗛殧绗?+ LEVEL鏍囪瘑锛?M/L? binary(JSON)
- binary: ZWJ=1, ZWSP=0
- 澶氱骇鍏卞瓨鏃讹細姣忎釜閽㈠嵃杩藉姞鍒版枃鏈湯灏撅紙rindex瀹氫綅鏈€澶栧眰?
#### 宸查獙璇佹祴?- M? 璇辨崟ID/鏃堕棿妗?鍣?鏃堕棿绐楀彛楠岃瘉 ?PASS
- S? L0鐘舵?寮€鍙戣€呭搱甯?闃蹭吉閫??PASS
- L? 鎵规ID/搴忓彿閫掑/鎵归噺鍙綔??PASS
- 涓夌骇鍏卞瓨: 鐙珛宓屽叆/姝ｇ‘鎻愬彇 ?PASS

