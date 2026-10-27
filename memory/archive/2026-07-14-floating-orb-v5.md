# 悬浮球色环 v5 重建报告

## 时间
2026-07-14 上午

## 目标
重建昨天（07-13）能正常显示的色环悬浮球，修复透明背景问题。

## 问题诊断

### 昨天为什么退回去？
- 无备份文件（所有 `tu8_health_orb*.py` 版本均未在 `backup/` 找到）
- v8/v7 代码在多次迭代中被覆盖，变得不可用
- 需要从对话记忆重建

### 重建过程遇到的 bug

| Bug | 根因 | 修复 |
|-----|------|------|
| PPM HSV 转换产生 float → bytes 报错 | `int(r_c*255)` 产生 float | 显式 clamp + int() |
| 图片尺寸≠Canvas尺寸 | W/H 计算公式与 ORB_R 混淆 | 统一用 W=H=(R+BALL_R+8)*2=310 |
| 球轨道半径错 | `ORB_R = RING_GAP+BALL_R = 34`，应为 130 | 改为 `ORB_R = R` |
| 窗口坐标 2×缩放 | DPI virtualization | 加 `SetProcessDpiAwareness(2)` |
| colorkey 透明失效 | 窗口 bg≠#FF00FF | 设 bg="#FF00FF" + SetLayeredWindowAttributes colorkey |

## 最终代码

**文件**：`src/tu8_health_orb_ring.py`
**窗口尺寸**：310×310
**DPI-aware**：✅ SetProcessDpiAwareness(2)
**透明度**：colorkey #FF00FF（洋红=透明）
**核心渲染**：PPM 色环图像 + tkinter Canvas 三球叠加

### 渲染架构
```
PPM色环 (310×310)
  ↓ create_image(0,0)
Canvas bg=#FF00FF (colorkey透明)
  ↓ create_oval (三球)
  ↓ create_text (文字)
Window bg=#FF00FF + WS_EX_LAYERED + LWA_COLORKEY
  ↓ Windows桌面合成
透明悬浮效果
```

### 三球定位（基于 W=310, R=130）
| 维度 | 值 | 角度 | 屏幕位置 |
|------|-----|------|---------|
| FOCUS (红) | 0.39 | 140.4° | ~2-3点钟 |
| DRIFT (绿) | 0.82 | 295.2° | ~9-10点钟 |
| PROBE (蓝) | 1.00 | 360° | 12点钟 |

## 验证结果

| 检查项 | 结果 |
|--------|------|
| 彩虹渐变色环 | ✅ 平滑无锯齿 |
| 三球定位 | ✅ 红/绿/蓝各就其位 |
| 中心文字 | ✅ "0.23" + "探索态" |
| 透明背景 | ✅ 桌面图标在透明区透出 |
| DPI 缩放 | ✅ 无 2× 放大 |
| 窗口拖动 | ✅ 正常 |
| TU-8 数据接入 | ✅ 从 surface_tension_state.json 读取 |

## 启动方式

```powershell
Start-Process python -ArgumentList 'C:\..\src\tu8_health_orb_ring.py' -WindowStyle Hidden
```

## 待改进
- tooltip 悬停提示（已绑定 Motion 事件，需实测）
- 右键退出功能已实现
- 数据刷新每 50ms 轮询

## 清理
41个调试文件（`_*.py`, `_*.ps1`, `_*.png`）已全部删除。
