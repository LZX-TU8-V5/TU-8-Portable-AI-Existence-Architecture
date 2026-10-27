#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tu8_health_orb.py — TU-8 生命体征悬浮球

桌面悬浮窗口，实时显示 TU-8 的健康状态：
- 读取 `_agent_memory/orb_state.json` 
- 颜色映射：红(压力) / 蓝(放松) / 绿(探索) / 橙(警报) / 紫(整理)
- 透明悬浮，不打扰工作
- 鼠标可拖动

用法：
  python src/tu8_health_orb.py
  
数据来源（需由 TU-8 写入）：
  {
    "rgb": [0.2, 0.7, 0.3],
    "tension": 0.35,
    "mode": "explore"
  }
"""

import sys
import json
import os
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QColor, QPalette, QFont

# === 配置 ===
WS = Path(__file__).parent.parent
STATE_FILE = WS / "_agent_memory" / "orb_state.json"
UPDATE_INTERVAL = 1000  # 1秒刷新一次

# 默认状态
DEFAULT_STATE = {
    "rgb": [0.3, 0.3, 0.3],
    "tension": 0.0,
    "mode": "neutral"
}


class HealthOrb(QWidget):
    """TU-8 生命体征悬浮球"""
    
    def __init__(self):
        super().__init__()
        
        # 窗口属性：无边框、置顶、透明背景
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 固定大小
        self.setFixedSize(120, 120)
        
        # 初始位置（屏幕右下角）
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 150, screen.height() - 150)
        
        # 拖动支持
        self.drag_pos = None
        
        # UI
        self.label_tension = QLabel("T: 0.00")
        self.label_mode = QLabel("neutral")
        self.label_tension.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_mode.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        font = QFont("Consolas", 10)
        self.label_tension.setFont(font)
        self.label_mode.setFont(font)
        
        layout = QVBoxLayout(self)
        layout.addWidget(self.label_tension)
        layout.addWidget(self.label_mode)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 定时器：定期读取状态
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_state)
        self.timer.start(UPDATE_INTERVAL)
        
        # 初始更新
        self.update_state()
    
    def update_state(self):
        """读取状态文件并更新显示"""
        state = self.load_state()
        
        # 颜色
        r, g, b = state["rgb"]
        color = QColor(int(r * 255), int(g * 255), int(b * 255))
        
        # 设置背景色（半透明）
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, color)
        self.setAutoFillBackground(True)
        self.setPalette(palette)
        
        # 文本
        self.label_tension.setText(f"T: {state['tension']:.2f}")
        self.label_mode.setText(state["mode"])
        
        # 文本颜色（深色背景用白字，浅色背景用黑字）
        brightness = (r + g + b) / 3
        text_color = QColor(255, 255, 255) if brightness < 0.5 else QColor(0, 0, 0)
        palette.setColor(QPalette.ColorRole.WindowText, text_color)
        self.label_tension.setPalette(palette)
        self.label_mode.setPalette(palette)
    
    def load_state(self):
        """加载状态文件"""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return DEFAULT_STATE
    
    # === 拖动支持 ===
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
    
    def mouseMoveEvent(self, event):
        if self.drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
    
    def mouseReleaseEvent(self, event):
        self.drag_pos = None
    
    # === 右键菜单 ===
    def contextMenuEvent(self, event):
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        quit_action = menu.addAction("退出")
        quit_action.triggered.connect(self.close)
        menu.exec(event.globalPos())


def main():
    app = QApplication(sys.argv)
    orb = HealthOrb()
    orb.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
