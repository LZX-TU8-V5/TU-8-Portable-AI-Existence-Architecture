# -*- coding: utf-8 -*-
"""render_layer_speak.py — cron daemon 专用：从队列取一条 TTS 播报"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from render_layer import speak_queue_head
speak_queue_head()
