# 任务产物：跨相态通道协议 (cross_phase_channel.py)

## 目标
实现睡眠/清醒/续梦/崩溃四种相态之间的通道管理，防止跨相态传输导致拓扑污染。

## 交付物
- `src/cross_phase_channel.py`（UTF-8，~24KB）
- 状态持久化：`_agent_memory/cross_phase_channel_state.json`（channels / history / seq / updated_at）

## 接口实现
`CrossPhaseChannel` 类完成全部规范方法：
- `open_channel(from, to, reason) -> ChannelReport`
- `close_channel(channel_id, reason) -> str`
- `transfer(channel_id, data) -> TransferReport`（data={"topology","tension","priority",...} → 返回 success/fidelity/warnings）
- `get_open_channels() -> list[ChannelStatus]`
- `get_channel_status(channel_id) -> ChannelStatus | None`
- `get_phase_impedance(from, to) -> float`
- `get_channel_history(limit=20) -> list`
- 公开方法 `calculate_fidelity(raw_data, impedance)`、`check_overload(channel_id)`

## 核心机制
- **阻抗矩阵** `PHASE_IMPEDANCE` + 阈值：`IMPEDANCE_THRESHOLD=0.75`（警告）、`CRITICAL_IMPEDANCE=0.90`（禁止传输）。未定义相态对默认阻抗 1.0=禁止。
- **带宽配额** `CHANNEL_BANDWIDTH`（NORMAL→COLLAPSE / COLLAPSE→NORMAL 配额为 0=禁止）。按 60s 窗口统计，超限→过载降保真度（×0.5）。
- **保真度模型**：`fidelity = 1 - impedance*complexity/100`，complexity 由拓扑节点/叶子数估算（0~100）。
- **集成**：`get_current_phase()` 读取 `phase_state_machine.PhaseStateMachine().get_phase()`（含状态文件回退）；`transfer()` 内调用 `deep_surface_interface.DeepSurfaceInterface().deep_to_surface(...)`，将接口层保真度与通道保真度取交集，并合并污染/完整性警告。

## 自检验证（全部通过）
1. **正常路径** SLEEP→DREAM（阻抗0.2）：fidelity≈0.998，success。
2. **异常路径** NORMAL→DREAM（阻抗0.8）：触发 IMPEDANCE_WARNING，fidelity≈0.971。
3. **崩溃路径禁止** NORMAL→COLLAPSE（阻抗0.9=临界 + 带宽0）：transfer 被禁止，success=False，fidelity=0。
4. **带宽超限** NORMAL→SLEEP（配额5000）：窗口内 8755>5000 → OVERLOAD，fidelity 降至 0.464。

## 备注
- 源文件采用 UTF-8（Python3 默认），执行无碍；仓库内旧模块为 GBK 仅影响文本读取，不影响跨模块调用。
- 修复了末行 `✅` emoji 在 GBK 控制台引发 `UnicodeEncodeError` 的问题（改为 `[OK]`）。
