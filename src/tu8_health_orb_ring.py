#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tu8_health_orb_ring.py — v5 重建版

昨天能显示的版本（PID 36600）的基础上：
- 加上 SetProcessDpiAwareness(2) 防止坐标×2
- 修复 colorkey 透明（用 #FF00FF = RGB(255,0,255)）
- 保留色环 PPM 渲染、三球、tooltip、拖动
"""
import json, math, sys
from pathlib import Path
import tkinter as tk
import ctypes
from ctypes import windll, wintypes

# ═══════════════════════════════════════════════════════════════
# DPI-aware first
# ═══════════════════════════════════════════════════════════════
try:
    _shcore = ctypes.cdll.LoadLibrary("shcore.dll")
    _spda = _shcore.SetProcessDpiAwareness
    _spda.argtypes = [wintypes.UINT]; _spda.restype = wintypes.UINT
    r = _spda(2); print(f"DPI-aware: {r}")
except Exception as e:
    print(f"DPI-aware skipped: {e}")

# ═══════════════════════════════════════════════════════════════
# Windows API
# ═══════════════════════════════════════════════════════════════
_u32 = windll.user32
_g32 = windll.gdi32

def WND(hwnd, idx, val):
    _u32.SetWindowLongW.argtypes = [wintypes.HWND, wintypes.INT, wintypes.LONG]
    _u32.SetWindowLongW.restype = wintypes.LONG
    return _u32.SetWindowLongW(hwnd, idx, val)

_u32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.COLORREF,
                                             wintypes.BYTE, wintypes.DWORD]
_u32.SetLayeredWindowAttributes.restype = wintypes.BOOL

# ═══════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════
TRANSPARENT_COLOR = 0x00FF00FF   # #FF00FF = RGB(255,0,255)
LWA_COLORKEY = 0x1
LWA_ALPHA = 0x2
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020

R = 130        # 色环外半径
RING_W = 22    # 色环宽度
r_center = 55  # 中心白圆半径
BALL_R = 15    # 滑球半径
RING_GAP = BALL_R + 4  # 滑球与轨道间隙
ORB_R = R  # 轨道半径 = 色环外半径，滑球圆心在色环上
# 窗口尺寸 = 色环外半径 + 球半径 + padding，向上取整为偶数
W = H = (R + BALL_R + 10) * 2  # 必须 >= (R+BALL_R)*2 = 290

# ─────────────────────────────────────────────────────────────
# 色相-张力映射
#
# RYB 色彩模型（认知语义）：
#   FOCUS(红) hue=0°   → 负载：烫/重/执行压力
#   DRIFT(黄) hue=60°  → 探索：热/主动试探（独立预警通道，不参与中心色）
#   PROBE(蓝) hue=240° → 稳态：冷/定/结构锚点
#
# 极坐标规则：
#   饱和度 → 径向半径（高→外圈贴合色环，低→收缩到中心）
#   明度   → 发光感（FOCUS/PROBE 由紧迫度；DRIFT 由探索值）
#
# 中心圆 = FOCUS × PROBE 的 RYB 合成（DRIFT 独立预警，不参与）
# ─────────────────────────────────────────────────────────────
BALL_META = {
    "FOCUS": {"hue_deg":   0, "label": "载",   "tip": "负载：烫手，系统正在消耗能量执行"},
    "DRIFT": {"hue_deg":  60, "label": "探",   "tip": "探索：主动试探，临界预警（独立通道）"},
    "PROBE": {"hue_deg": 240, "label": "稳",   "tip": "稳态：冷感，结构完整性与低熵基底"},
}

# ═══════════════════════════════════════════════════════════════
# 代数化优化：预计算色相角的 cos/sin
#
# 【定义层】色相 = 固定角度区域（FOCUS=0° / DRIFT=60° / PROBE=240°）
# 【执行层】运行时只有乘加运算，无任何超越数调用
#
# 判断标准：把 π 换成符号 P，能否通过代数恒等式消掉？
# → cos/sin 预计算为浮点常量（等价于代数数逼近），
#   运行时执行 bx = cx + r * cos_0，完全消掉
# ═══════════════════════════════════════════════════════════════
def _build_trig_table():
    """
    预计算三球的 cos/sin 值到 (cos_angle, sin_angle) 元组。
    偏移 -90° 让 0° 从12点钟（上方）开始。
    """
    table = {}
    for name, meta in BALL_META.items():
        deg = meta["hue_deg"] - 90  # 偏移：12点钟方向 = 0°
        rad = deg * (math.pi / 180.0)  # 启动时一次性计算，含 π 是安全的（不在热路径）
        table[name] = (math.cos(rad), math.sin(rad))
    return table

# 模块加载时一次性初始化，运行时代码只做 r * cos + cx
_BALL_TRIG = _build_trig_table()

# ═══════════════════════════════════════════════════════════════
# PPM 色环预计算
# ═══════════════════════════════════════════════════════════════
def _hsv2rgb(h, s, v):
    if s == 0: return v, v, v
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p, q, t = v*(1-s), v*(1-f*s), v*(1-(1-f)*s)
    i %= 6
    return [(v,t,p),(f,v,p),(p,v,t),(p,f,v),(t,p,v),(v,p,f)][i]

def build_hue_ring_ppm():
    """生成完整覆盖 Canvas 的色环 PPM 图像"""
    cx = cy = W // 2
    rows = []
    for py in range(H):
        row = []
        for px in range(W):
            dx, dy = px - cx, py - cy
            dist = math.sqrt(dx*dx + dy*dy)
            if R - RING_W <= dist <= R:
                # 色环区域
                angle = math.atan2(-dy, dx)
                hue = (angle / (2 * math.pi) + 0.5) % 1.0
                r_c, g_c, b_c = _hsv2rgb(hue, 0.85, 0.95)
                row.append((min(255, int(r_c*255+0.5)),
                             min(255, int(g_c*255+0.5)),
                             min(255, int(b_c*255+0.5))))
            elif dist <= r_center:
                # 中心透明（Canvas 层会画动态中心圆）
                row.append((255, 0, 255))
            else:
                # colorkey 透明色
                row.append((255, 0, 255))
        rows.append(row)
    header = f"P6\n{W} {H}\n255\n".encode()
    data = b"".join(b"".join(bytes(p) for p in row) for row in rows)
    return header + data

# ═══════════════════════════════════════════════════════════════
# 取色环像素（用于三球定位）
# ═══════════════════════════════════════════════════════════════
def _hsv2rgb_for_ball(h, s, v):
    if s == 0: return v, v, v
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p, q, t = v*(1-s), v*(1-f*s), v*(1-(1-f)*s)
    i %= 6
    return [(v,t,p),(f,v,p),(p,v,t),(p,f,v),(t,p,v),(v,p,f)][i]

def _hsv_to_rgb8(h_deg, s, v):
    """HSV → (r,g,b) 0-255，h_deg ∈ [0,360]"""
    h = (h_deg % 360) / 360.0
    if s == 0:
        g = b = int(v * 255 + 0.5)
        return g, g, g
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    r, g, b = [(v, t, p),(p, v, t),(p, t, v),(t, p, v),(v, p, t),(q, p, v)][i]
    return int(r*255+0.5), int(g*255+0.5), int(b*255+0.5)


def _ball_hsv(name, sat, urgency=0.5):
    """
    返回球的 HSV 颜色。
    - FOCUS(红): hue=0°, sat=负载强度, val=紧迫度
    - DRIFT(黄): hue=60°(RYB黄色), sat=探索强度
      但黄球是独立预警通道——常态暗饱和，临界才亮起
    - PROBE(蓝): hue=240°, sat=稳态强度, val=紧迫度
    """
    meta = BALL_META[name]
    hue_deg = meta["hue_deg"]

    if name == "DRIFT":
        # 黄球=探索=烫手。常态暗亮，临界触发。
        # 高探索值 → 高饱和+高明度（烫）；低探索值 → 低饱和+暗（冷）
        # [修复] 提高基准明度，确保低饱和时仍是黄色而非暗绿
        val = 0.45 + sat * 0.5
        # [修复] 提高最小饱和度，避免过淡的黄色偏绿
        sat = max(sat, 0.35)
    else:
        val = 0.38 + urgency * 0.58

    return hue_deg, sat, val


def _ball_xy_by_name(sat, name):
    """
    代数化极坐标定位（按名称查表，无超越数运行时调用）。

    参数：
      sat: 球饱和度（决定径向位置）
      name: 球名称（FOCUS / DRIFT / PROBE）

    运行时执行：bx = cx + r * cos_0, by = cy + r * sin_0
    纯代数运算，无 math.cos / math.sin / math.radians 调用

    【π-可擦除性验证】：
      cos/sin 预计算为浮点常量（等价于代数数逼近）。
      把预计算换成符号 P，运行时 bx = cx + r * P * cos_0 无意义 →
      说明 cos/sin 被"消耗"在预计算中，不残留于运行时状态。
    """
    cx = cy = W // 2
    r = max(sat * ORB_R, ORB_R * 0.55)  # 最小半径约束
    cos_a, sin_a = _BALL_TRIG[name]      # 预计算常量（启动时一次性计算）
    return cx + r * cos_a, cy + r * sin_a


def _ball_xy(sat, hue_deg):
    """
    极坐标定位（兼容接口，路由到代数化版本）。

    参数：
      sat: 球饱和度
      hue_deg: 色相角度（0/60/240）

    内部实现：按角度查表 → _ball_xy_by_name
    运行时无超越数：hue_deg → 名称查表 → cos/sin 查表 → 乘加
    """
    # 固定映射：角度 → 名称
    _deg_to_name = {0: "FOCUS", 60: "DRIFT", 240: "PROBE"}
    name = _deg_to_name.get(int(round(hue_deg % 360)), "FOCUS")
    return _ball_xy_by_name(sat, name)


def _center_bg_hsv(f_sat, p_sat, tension):
    """
    中心圆背景色 = 红(负载) × 蓝(稳态) 的 RYB 混合。
    黄(探索) 不参与合成，作为独立预警通道。

    RYB 语义映射：
    - 负载高(红浓) + 稳态高(蓝浓) → 紫 (高负荷但有根基)
    - 负载高(红浓) + 稳态低(蓝淡) → 暖橙/粉 (高负荷+失控边缘)
    - 负载低(红淡) + 稳态高(蓝浓) → 冷蓝/青 (从容稳固)
    - 负载低(红淡) + 稳态低(蓝淡) → 中性灰白 (最佳心流态)

    参数：
    - f_sat: 红球饱和度（负载强度）
    - p_sat: 蓝球饱和度（稳态强度）
    - tension: 综合张力（控制明度）
    """
    total_rb = f_sat + p_sat
    if total_rb < 0.001:
        return 0, 0, 0.82  # 默认中性灰白

    # RYB 色相映射：红(0°)=负载，蓝(240°)=稳态
    # 在色轮上，负载→暖色，稳态→冷色
    # 红+蓝 → 紫/洋红区（160-280°）
    # 色相计算：负载越高越偏红(0°)，稳态越高越偏蓝(240°)
    hue = 120.0 * f_sat / total_rb + 240.0 * p_sat / total_rb

    # 饱和度：负载+稳态总量（代表系统被占据的程度）
    avg_s = min(total_rb / 2.0, 1.0)

    # 明度：综合张力驱动，越紧张越亮（接近报警态）
    avg_v = 0.38 + tension * 0.52

    return hue % 360, avg_s, min(avg_v, 0.95)

# ═══════════════════════════════════════════════════════════════
# Tooltip 窗口
# ═══════════════════════════════════════════════════════════════
class Tooltip(tk.Toplevel):
    def __init__(self, parent, text):
        super().__init__(parent)
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg="#FFF8DC", bd=1, relief="solid")
        tk.Label(self, text=text, font=("微软雅黑", 9),
                 bg="#FFF8DC", fg="#333").pack(padx=6, pady=3)
        self._shown = False

    def show(self, x, y):
        self.geometry(f"+{x+10}+{y-10}")
        self.deiconify()
        self._shown = True

    def hide(self):
        self.withdraw()
        self._shown = False

# ═══════════════════════════════════════════════════════════════
# 路径定义
# ═══════════════════════════════════════════════════════════════
WS        = Path(__file__).parent.parent
LAMBDA_F  = WS / "_agent_memory" / "lambda_state.json"  # 唯一数据源（interopertive_cortex 写入）
ORB_F     = WS / "_agent_memory" / "orb_state.json"

MODE_LABELS = {
    "stress":    "压力态",
    "explore":   "探索态",
    "relax":     "放松态",
    "conserve":  "节能态",
    "dream":     "梦境态",
    "neutral":   "中性态",
}

def _safe_read(path: Path, fallback=None):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return fallback


def _calc_tension_rgb():
    """
    张力体线计算（单一数据源：lambda_state.json）。
    F(红) = Focus/负载   = max(焦虑,愤怒,恐惧)*0.6 + 外部痛觉*0.4
    D(绿) = Drift/感知   = 好奇心*0.6 + 盆地健康*0.4
    P(蓝) = Probe/稳态   = 1 - 内部痛觉
    """
    TENSION_MAX = 1.0  # [P0-2d] 改为 1.0：lambda_state 是 [0,1] 归一化，不是 surface_tension 原始 [0,3]
    # 单一数据源：interopertive_cortex 写入
    ls = _safe_read(LAMBDA_F, {})
    anxiety    = ls.get("anxiety",    0.0)
    anger      = ls.get("anger",      0.0)
    fear       = ls.get("fear",       0.0)
    curiosity  = ls.get("curiosity",  0.3)
    basin_h    = ls.get("basin_health", 0.7)
    pain_ext   = ls.get("pain_ext",   0.0)
    pain_int   = ls.get("pain_int",   0.0)
    lam_mode   = ls.get("mode",       "neutral")
    joy = ls.get("joy",  0.0)
    love = ls.get("love", 0.0)

    # F = Focus/负载（红）
    red_raw = max(anxiety, anger, fear) * 0.6 + pain_ext * 0.4
    red = min(red_raw / TENSION_MAX, 1.0)

    # D = Drift/感知（绿）
    green_raw = curiosity * 0.6 + basin_h * 0.4
    green = min(green_raw, 1.0)

    # P = Probe/稳态（蓝）
    blue = min(1.0 - pain_int, 1.0)

    # 综合张力
    tension = red * 0.6 + (1 - blue) * 0.4

    # 模式判断
    if red > 0.7:
        mode = "stress"
    elif green > 0.5 and red > 0.3 and blue > 0.3:
        mode = "explore"
    elif blue > 0.6 and red < 0.3:
        mode = "relax"
    elif lam_mode in ("conserve", "unknown"):
        mode = "conserve"
    elif joy + love > 1.5:
        mode = "explore"
    else:
        mode = "neutral"

    return {
        "focus_load":       round(red,   3),
        "perception_drift": round(green, 3),
        "probe_stability":  round(blue,  3),
        "tension_score":    round(tension, 3),
        "mode":            MODE_LABELS.get(mode, mode),
    }


class _OrbCache:
    """防空转缓存：只在新数据时才更新"""
    def __init__(self):
        self.vals       = None
        self.last_mtime = 0.0

    def get(self):
        # 单一数据源 + orb 状态兜底
        files = [LAMBDA_F, ORB_F]
        newest_mtime = max((f.stat().st_mtime for f in files if f.exists()), default=0.0)
        if newest_mtime > self.last_mtime or self.vals is None:
            self.last_mtime = newest_mtime
            self.vals = _calc_tension_rgb()
        return self.vals

_orb_cache = _OrbCache()


def read_tu8_values():
    return _orb_cache.get()

# ═══════════════════════════════════════════════════════════════
# 主类
# ═══════════════════════════════════════════════════════════════
class TU8HealthOrb:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("TU8 Health Orb")
        self.root.geometry(f"{W}x{H}+50+50")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        # colorkey 透明背景
        self.root.configure(bg="#FF00FF")

        # colorkey 透明
        hwnd = int(self.root.winfo_id())
        style = _u32.GetWindowLongW(hwnd, -20)
        _u32.SetWindowLongW(hwnd, -20, style | WS_EX_LAYERED)
        _u32.SetLayeredWindowAttributes(hwnd, 0x00FF00FF, 0, LWA_COLORKEY)

        # PPM 色环图像
        self._ppm = build_hue_ring_ppm()
        self._ppm_img = tk.PhotoImage(data=self._ppm)

        # Canvas
        self.cv = tk.Canvas(self.root, width=W, height=H,
                            bg="#FF00FF", highlightthickness=0)
        self.cv.pack()
        self.cv.create_image(0, 0, anchor="nw", image=self._ppm_img)

        # 三球（极坐标：色相固定，饱和度决定半径）
        self.ball_items = {}
        self.ball_labels = {}
        self.tooltip_balls = {}  # name -> tooltip text
        for name, meta in BALL_META.items():
            hue_deg = meta["hue_deg"]
            # 初始用中等饱和度 0.5 定位
            hue, sat, val = _ball_hsv(name, 0.5, 0.5)
            r_c, g_c, b_c = _hsv_to_rgb8(hue, sat, val)
            color = f"#{r_c:02X}{g_c:02X}{b_c:02X}"
            bx, by = _ball_xy(0.5, hue_deg)  # 初始半径=0.5×ORB_R
            outline = "#222" if name == "FOCUS" else ("#111" if name == "DRIFT" else "#003")
            item = self.cv.create_oval(bx-BALL_R, by-BALL_R, bx+BALL_R, by+BALL_R,
                                       fill=color, outline=outline, width=1.5, tags=f"ball_{name}")
            lbl = self.cv.create_text(bx, by, text=meta["label"][:1], font=("Arial", 8, "bold"),
                                      fill="white", tags=f"lbl_{name}")
            self.ball_items[name] = (item, lbl)
            self.tooltip_balls[name] = meta["tip"]

        # 中心圆（动态颜色 + 文字）
        self.tension_lbl = None
        self.mode_lbl = None
        cx = cy = W // 2
        # 初始中心圆背景色（红=0.5, 蓝=0.5, 张力=0.5）
        bh, bs, bv = _center_bg_hsv(0.5, 0.5, 0.5)
        br_c, bg_c, bb_c = _hsv_to_rgb8(bh, bs, bv)
        bg_color = f"#{br_c:02X}{bg_c:02X}{bb_c:02X}"
        self._center_circle = self.cv.create_oval(cx-r_center+2, cy-r_center+2,
                                                   cx+r_center-2, cy+r_center-2,
                                                   fill=bg_color, outline="")
        self.tension_lbl = self.cv.create_text(cx, cy-8, text="--",
                                                font=("Arial", 16, "bold"), fill="#333")
        self.mode_lbl = self.cv.create_text(cx, cy+10, text="张力·--",
                                             font=("Arial", 9), fill="#666")

        # tooltip
        self.tooltip = Tooltip(self.root, "")

        # 拖动
        self._drag = {"on": False, "x": 0, "y": 0}
        self.cv.bind("<Button-1>", self._on_down)
        self.cv.bind("<B1-Motion>", self._on_move)
        self.cv.bind("<ButtonRelease-1>", self._on_up)

        # 悬停检测（用画布级事件 + find_closest）
        self.cv.bind("<Motion>", self._on_motion)

        # 右键退出
        self.root.bind("<Button-3>", lambda e: self.root.destroy())

        # 刷新
        self.refresh()
        self.root.after(50, self._refresh_loop)

        print(f"Orb ready: {W}x{H}")
        self.root.mainloop()

    def _refresh_loop(self):
        self.refresh()
        self.root.after(50, self._refresh_loop)

    def refresh(self):
        vals = read_tu8_values()
        cx = cy = W // 2

        # ── 三球：极坐标定位 + 动态颜色 ──────────────────
        # F,D,P 同时也是饱和度（决定半径）
        sat_map = {
            "FOCUS": vals["focus_load"],
            "DRIFT": vals["perception_drift"],
            "PROBE": vals["probe_stability"],
        }
        urgency = 1.0 - vals.get("probe_stability", 0.5)  # 稳态越高，紧迫感越低

        for name, meta in BALL_META.items():
            sat = sat_map[name]
            hue_deg = meta["hue_deg"]

            # 位置：饱和度 → 半径（极坐标）
            bx, by = _ball_xy(sat, hue_deg)

            # 颜色：HSV → RGB
            h, s, v = _ball_hsv(name, sat, urgency)
            r_c, g_c, b_c = _hsv_to_rgb8(h, s, v)
            color = f"#{r_c:02X}{g_c:02X}{b_c:02X}"

            item, lbl = self.ball_items[name]
            self.cv.coords(item, bx-BALL_R, by-BALL_R, bx+BALL_R, by+BALL_R)
            self.cv.itemconfig(item, fill=color)
            # 文字定位跟随
            self.cv.coords(lbl, bx, by)

        # ── 中心圆：RYB混合色 = 红(负载) × 蓝(稳态) ────
        # 黄球(探索)是独立预警通道，不参与中心色合成
        tension = vals.get("tension_score", 0.5)
        bh, bs, bv = _center_bg_hsv(sat_map["FOCUS"], sat_map["PROBE"], tension)
        br_c, bg_c, bb_c = _hsv_to_rgb8(bh, bs, bv)
        bg_color = f"#{br_c:02X}{bg_c:02X}{bb_c:02X}"
        self.cv.itemconfig(self._center_circle, fill=bg_color)

        # ── 中心文字 ─────────────────────────────────────
        self.cv.itemconfig(self.tension_lbl, text=f"{tension:.2f}")
        self.cv.itemconfig(self.mode_lbl, text=f"张力·{vals.get('mode','--')}")

    def _on_down(self, e):
        self._drag = {"on": True, "x": e.x, "y": e.y}

    def _on_move(self, e):
        if not self._drag["on"]: return
        dx = e.x - self._drag["x"]
        dy = e.y - self._drag["y"]
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")

    def _on_up(self, e):
        self._drag["on"] = False

    _hover_item = None

    def _on_motion(self, e):
        # 找最近的画布项
        items = self.cv.find_overlapping(e.x-2, e.y-2, e.x+2, e.y+2)
        item_id = items[0] if items else None
        if item_id == self._hover_item:
            return  # 同项，不重复触发
        self._hover_item = item_id
        if item_id is None:
            self.tooltip.hide()
            return
        tags = self.cv.gettags(item_id)
        for name in ["FOCUS", "DRIFT", "PROBE"]:
            if f"ball_{name}" in tags:
                self.tooltip.configure(text=self.tooltip_balls[name])
                sx = self.root.winfo_x() + e.x + 15
                sy = self.root.winfo_y() + e.y - 10
                self.tooltip.show(sx, sy)
                return
        self.tooltip.hide()

if __name__ == "__main__":
    TU8HealthOrb()
