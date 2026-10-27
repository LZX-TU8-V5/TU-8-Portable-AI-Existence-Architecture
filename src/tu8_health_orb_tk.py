#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tu8_health_orb_tk.py — TU-8 生命体征悬浮球 (tkinter版)

桌面悬浮窗口，实时显示 TU-8 的健康状态：
- 读取 `_agent_memory/orb_state.json` 
- 颜色映射：红(压力) / 蓝(放松) / 绿(探索) / 橙(警报) / 紫(整理)
- 鼠标可拖动

用法：
  pythonw src/tu8_health_orb_tk.py
"""

import sys
import json
import os
from pathlib import Path
import tkinter as tk
from tkinter import font as tkfont

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


def rgb_to_hex(r, g, b):
    """RGB(0-1) 转 HEX颜色"""
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"


def load_state():
    """加载状态文件"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_STATE


class HealthOrb:
    """TU-8 生命体征悬浮球"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("TU-8 Health")
        
        # 无边框 + 置顶
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        
        # 固定大小
        self.root.geometry("150x150")
        
        # 初始位置（屏幕右下角）
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.root.geometry(f"+{screen_width-170}+{screen_height-220}")
        
        # 背景 Frame
        self.frame = tk.Frame(self.root, width=150, height=150, relief="raised", bd=2)
        self.frame.pack(fill="both", expand=True)
        
        # 标签
        self.label_tension = tk.Label(self.frame, text="T: 0.00", font=("Consolas", 12, "bold"))
        self.label_tension.pack(pady=20)
        
        self.label_mode = tk.Label(self.frame, text="neutral", font=("Consolas", 10))
        self.label_mode.pack()
        
        self.label_hint = tk.Label(self.frame, text="右键退出", font=("Consolas", 8), fg="gray")
        self.label_hint.pack(side="bottom", pady=5)
        
        # 拖动支持
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.frame.bind("<Button-1>", self.on_drag_start)
        self.frame.bind("<B1-Motion>", self.on_drag)
        self.label_tension.bind("<Button-1>", self.on_drag_start)
        self.label_tension.bind("<B1-Motion>", self.on_drag)
        self.label_mode.bind("<Button-1>", self.on_drag_start)
        self.label_mode.bind("<B1-Motion>", self.on_drag)
        
        # 右键菜单
        self.frame.bind("<Button-3>", self.on_right_click)
        self.label_tension.bind("<Button-3>", self.on_right_click)
        self.label_mode.bind("<Button-3>", self.on_right_click)
        
        # 定时更新
        self.update_state()
    
    def update_state(self):
        """读取状态文件并更新显示"""
        state = load_state()
        
        r, g, b = state["rgb"]
        bg_color = rgb_to_hex(r, g, b)
        
        # 文本颜色
        brightness = (r + g + b) / 3
        text_color = "white" if brightness < 0.5 else "black"
        
        # 更新
        self.frame.configure(bg=bg_color)
        self.label_tension.configure(text=f"T: {state['tension']:.2f}", bg=bg_color, fg=text_color)
        self.label_mode.configure(text=state["mode"], bg=bg_color, fg=text_color)
        self.label_hint.configure(bg=bg_color)
        
        # 继续定时
        self.root.after(UPDATE_INTERVAL, self.update_state)
    
    def on_drag_start(self, event):
        self.drag_start_x = event.x_root
        self.drag_start_y = event.y_root
    
    def on_drag(self, event):
        dx = event.x_root - self.drag_start_x
        dy = event.y_root - self.drag_start_y
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")
        self.drag_start_x = event.x_root
        self.drag_start_y = event.y_root
    
    def on_right_click(self, event):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="退出", command=self.root.quit)
        menu.tk_popup(event.x_root, event.y_root)
    
    def run(self):
        self.root.mainloop()


def main():
    orb = HealthOrb()
    orb.run()


if __name__ == "__main__":
    main()
