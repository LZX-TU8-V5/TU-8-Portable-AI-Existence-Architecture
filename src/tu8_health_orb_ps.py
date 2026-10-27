#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tu8_health_orb_ps.py — PS球形色盘版 TU-8 生命体征悬浮球

圆形球体设计：
- 圆周上三个滑块点（红/绿/蓝），按张力比例动态定位
- 中心圆显示当前综合色
- 平滑滑动 + 轨迹拖尾 + 中心圆渐变
- 中文标签

用法：
  pythonw src/tu8_health_orb_ps.py
"""

import sys
import json
import math
from pathlib import Path
from collections import deque

# ═══════════════════════════════════════════════════════════════
# 代数化优化：预计算 360° 整数三角表
#
# 【问题】angle_to_xy() 每帧被调用 7 次，每次做：
#   rad = math.radians(angle - 90)   # 运行时 radians
#   x = CENTER + r * math.cos(rad)   # 运行时 cos
#   y = CENTER + r * math.sin(rad)   # 运行时 sin
#
# 【解决方案】预计算 cos/sin 表（整数角度 0-359）
#   → 运行时仅需：四舍五入 + 查表 + 乘加
#   → 完全消除 math.cos / math.sin / math.radians 调用
#
# 【π-可擦除性】
#   π 仅在 _build_trig_table() 启动时一次性使用，
#   之后所有运行时查询都是纯代数浮点，无 π 残留
# ═══════════════════════════════════════════════════════════════

def _build_trig_table_360():
    """预计算 0-359° 的 (cos, sin) 浮点元组。启动时一次性计算。"""
    table = {}
    for deg in range(360):
        rad = deg * (math.pi / 180.0)  # 含 π，仅启动时
        table[deg] = (math.cos(rad), math.sin(rad))
    return table

# 模块级：360 个 (cos, sin) 元组，运行时零超越数
_TRIG_360 = _build_trig_table_360()
import tkinter as tk

# === 配置 ===
WS = Path(__file__).parent.parent
STATE_FILE = WS / "_agent_memory" / "orb_state.json"
UPDATE_INTERVAL = 50  # 50ms = 20fps

# 默认状态
DEFAULT_STATE = {
    "rgb": [0.3, 0.3, 0.3],
    "tension": 0.0,
    "mode": "neutral"
}

# 模式翻译
MODE_CN = {
    "stress": "压力态",
    "explore": "探索态",
    "relax": "放松态",
    "conserve": "节能态",
    "dream": "梦境态",
    "alert": "警觉态",
    "neutral": "待机",
    "idle": "待机",
}

# 颜色标签（标签始终显示，但位置随滑块）
LABEL_R = "压力"  # 红
LABEL_G = "探索"  # 绿
LABEL_B = "放松"  # 蓝


def load_state():
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_STATE


class HealthOrbPS:
    """PS球形色盘版悬浮球（带动画+中文）"""
    
    SIZE = 280  # 加大以容纳文字
    CENTER = SIZE // 2
    OUTER_R = 100
    INNER_R = 45
    DOT_R = 14
    
    # 动画参数
    LERP_SPEED = 0.12
    TRAIL_LENGTH = 8
    TRAIL_DOT_R = 5
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("TU-8 生命体征")
        
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.95)
        
        self.root.geometry(f"{self.SIZE}x{self.SIZE}")
        
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.root.geometry(f"+{screen_w-self.SIZE-30}+{screen_h-self.SIZE-80}")
        
        self.canvas = tk.Canvas(
            self.root, width=self.SIZE, height=self.SIZE,
            bg="black", highlightthickness=0
        )
        self.canvas.pack()
        
        # 拖动
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.canvas.bind("<Button-1>", self.on_drag_start)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<Button-3>", self.on_right_click)
        
        # 当前显示值（插值用）
        self.cur_r = 0.3
        self.cur_g = 0.3
        self.cur_b = 0.3
        self.cur_tension = 0.0
        self.cur_mode = "neutral"
        
        # 目标值
        self.tgt_r = 0.3
        self.tgt_g = 0.3
        self.tgt_b = 0.3
        self.tgt_tension = 0.0
        self.tgt_mode = "neutral"
        
        # 轨迹历史
        self.trail = deque(maxlen=self.TRAIL_LENGTH)
        
        # 字体
        self.font_label = ("Microsoft YaHei", 10, "bold")
        self.font_main = ("Microsoft YaHei", 16, "bold")
        self.font_sub = ("Microsoft YaHei", 11)
        self.font_hint = ("Microsoft YaHei", 8)
        
        self.update_state()
    
    def lerp(self, a, b, t):
        return a + (b - a) * t
    
    def update_state(self):
        state = load_state()
        
        self.tgt_r = state["rgb"][0]
        self.tgt_g = state["rgb"][1]
        self.tgt_b = state["rgb"][2]
        self.tgt_tension = state["tension"]
        self.tgt_mode = state["mode"]
        
        self.cur_r = self.lerp(self.cur_r, self.tgt_r, self.LERP_SPEED)
        self.cur_g = self.lerp(self.cur_g, self.tgt_g, self.LERP_SPEED)
        self.cur_b = self.lerp(self.cur_b, self.tgt_b, self.LERP_SPEED)
        self.cur_tension = self.lerp(self.cur_tension, self.tgt_tension, self.LERP_SPEED)
        
        self.trail.append((self.cur_r, self.cur_g, self.cur_b))
        
        self.draw_orb()
        self.root.after(UPDATE_INTERVAL, self.update_state)
    
    def angle_to_xy(self, angle_deg, radius):
        """
        角度转坐标（12点钟方向为0°，顺时针）。

        【代数化】运行时无超越数：
          - 先偏移 -90°（canvas 坐标从右/东开始）
          - 整数角度四舍五入 → 查表 _TRIG_360[deg] → 乘加
          - 消除 math.radians / math.cos / math.sin
        """
        # 代数化 + 正确偏移：
        #   1. 先归一化 angle_deg % 360（防止 >360° 的累加角度）
        #   2. 偏移 -90°（12点钟=0° → canvas东=0°）
        #   3. 取整数查表 _TRIG_360
        #   运行时无 math.radians / math.cos / math.sin
        norm_deg = int(((angle_deg % 360) - 90) % 360)
        cos_a, sin_a = _TRIG_360[norm_deg]
        x = self.CENTER + radius * cos_a
        y = self.CENTER + radius * sin_a
        return x, y
    
    def draw_orb(self):
        self.canvas.delete("all")
        cx, cy = self.CENTER, self.CENTER
        r, g, b = self.cur_r, self.cur_g, self.cur_b
        
        # 1. 外圆
        self.canvas.create_oval(
            cx - self.OUTER_R, cy - self.OUTER_R,
            cx + self.OUTER_R, cy + self.OUTER_R,
            outline="#666", width=2, fill="#1a1a1a"
        )
        
        # 2. 轨迹拖尾
        trail_list = list(self.trail)
        for i, (tr, tg, tb) in enumerate(trail_list[:-1]):
            alpha = (i + 1) / len(trail_list)
            r_dot = self.TRAIL_DOT_R * alpha
            avg_angle = ((tr + tg + tb) / 3) * 360 - 90
            x, y = self.angle_to_xy(avg_angle, self.OUTER_R)
            self.canvas.create_oval(
                x - r_dot, y - r_dot, x + r_dot, y + r_dot,
                fill="#444", outline=""
            )
        
        # 3. 三原色滑块
        red_angle = r * 360 - 90
        green_angle = g * 360 - 90
        blue_angle = b * 360 - 90
        
        red_x, red_y = self.angle_to_xy(red_angle, self.OUTER_R)
        green_x, green_y = self.angle_to_xy(green_angle, self.OUTER_R)
        blue_x, blue_y = self.angle_to_xy(blue_angle, self.OUTER_R)
        
        # 红点 + 标签
        self.canvas.create_oval(
            red_x - self.DOT_R, red_y - self.DOT_R,
            red_x + self.DOT_R, red_y + self.DOT_R,
            fill="#ff3333", outline="white", width=2
        )
        # 标签放在点的外侧
        label_r_x, label_r_y = self.angle_to_xy(red_angle, self.OUTER_R + 18)
        self.canvas.create_text(
            label_r_x, label_r_y, text=LABEL_R,
            fill="#ff6666", font=self.font_label
        )
        
        # 绿点 + 标签
        self.canvas.create_oval(
            green_x - self.DOT_R, green_y - self.DOT_R,
            green_x + self.DOT_R, green_y + self.DOT_R,
            fill="#33ff33", outline="white", width=2
        )
        label_g_x, label_g_y = self.angle_to_xy(green_angle, self.OUTER_R + 18)
        self.canvas.create_text(
            label_g_x, label_g_y, text=LABEL_G,
            fill="#66ff66", font=self.font_label
        )
        
        # 蓝点 + 标签
        self.canvas.create_oval(
            blue_x - self.DOT_R, blue_y - self.DOT_R,
            blue_x + self.DOT_R, blue_y + self.DOT_R,
            fill="#3333ff", outline="white", width=2
        )
        label_b_x, label_b_y = self.angle_to_xy(blue_angle, self.OUTER_R + 18)
        self.canvas.create_text(
            label_b_x, label_b_y, text=LABEL_B,
            fill="#6666ff", font=self.font_label
        )
        
        # 4. 中心圆
        center_color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
        self.canvas.create_oval(
            cx - self.INNER_R, cy - self.INNER_R,
            cx + self.INNER_R, cy + self.INNER_R,
            fill=center_color, outline="white", width=1
        )
        
        # 5. 中心文字（中文）
        brightness = (r + g + b) / 3
        text_color = "white" if brightness < 0.5 else "black"
        
        mode_cn = MODE_CN.get(self.cur_mode, self.cur_mode)
        
        self.canvas.create_text(
            cx, cy - 10,
            text=f"张力 {self.cur_tension:.2f}",
            fill=text_color, font=self.font_main
        )
        self.canvas.create_text(
            cx, cy + 12,
            text=mode_cn,
            fill=text_color, font=self.font_sub
        )
        
        # 6. 底部提示
        self.canvas.create_text(
            cx, self.SIZE - 15,
            text="TU-8  ·  左键拖动  ·  右键退出",
            fill="#666", font=self.font_hint
        )
    
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
    orb = HealthOrbPS()
    orb.run()


if __name__ == "__main__":
    main()
