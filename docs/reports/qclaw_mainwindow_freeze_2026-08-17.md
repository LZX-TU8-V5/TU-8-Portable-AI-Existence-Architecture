# 主窗口卡死排障 · 2026-08-17

## 目标
定位 QClaw 主窗口「卡死」根因并恢复，给出低损恢复预案。

## 关键诊断
- 主窗口没真死：后台 gateway（node, openclaw-gateway）一直存活，消息能收发。
- 真凶是 **renderer 渲染进程内存暴涨**：事件初 `QClaw.exe` renderer `26452` 占 **908MB**（正常几十 MB），UI 线程被卡住 → 表现为卡死。
- 今天 **14:39 刚更新/重装过 QClaw**（`QClawInstall_20260817143508.Log`），旧渲染状态未完全重置，最可能诱因。
- gateway 自身 node 子进程常驻约 **1GB**（非异常，TU-8 常驻脚本多）。

## 恢复动作
- 用户于 14:50 直接重启客户端 → 主窗口恢复（14:50 复测 `27712` Responding=True）。
- 重启后仍有 renderer `26168` ≈ 567MB（偏高但非致命）。

## 结论 / 预案
- 卡死 ≠ gateway 挂，不要整客户端重启（丢不了对话但没必要）。
- 下次再卡：让我 `Stop-Process` 掉异常 renderer 进程即可，Electron 自动重建窗口，对话/gateway 不中断。
- 若同时对话变慢，排查 gateway node 子进程是否内存持续上涨，必要时单独重启 gateway（`gateway` 工具 restart）。
- 14:39 的更新若反复触发，留意是否新版 renderer 内存泄漏。
