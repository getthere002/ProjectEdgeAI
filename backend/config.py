# ======================================
# Configuration Settings
# ระบบตรวจจับท่าทางเสี่ยงต่อการหกล้ม
# ======================================

import os

# --- Server Settings ---
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000

# --- Camera Settings ---
# ใช้ 0 สำหรับ webcam ตัวแรก, หรือใส่ URL สำหรับ IP Camera / RTSP
# เช่น "rtsp://user:pass@192.168.1.100:554/stream"
CAMERA_SOURCE = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30

# --- MediaPipe Pose Settings ---
POSE_MIN_DETECTION_CONFIDENCE = 0.5
POSE_MIN_TRACKING_CONFIDENCE = 0.5
POSE_MODEL_COMPLEXITY = 1  # 0=Lite, 1=Full, 2=Heavy

# --- Fall Risk Thresholds ---
# มุมลำตัว (องศา) - มุมเทียบกับแนวตั้ง
BODY_ANGLE_WARNING = 30      # เริ่มเตือน เมื่อเอียง > 30°
BODY_ANGLE_DANGER = 45       # อันตราย เมื่อเอียง > 45°
BODY_ANGLE_FALL = 60         # ตรวจจับหกล้ม เมื่อเอียง > 60°

# ความเร็วการตกลง (normalized units/frame)
VELOCITY_WARNING = 0.02
VELOCITY_DANGER = 0.04
VELOCITY_FALL = 0.08

# มุมข้อเข่า (องศา) - มุมเข่าที่งอมากเกินไป
KNEE_ANGLE_WARNING = 120     # เริ่มเตือน เมื่อเข่างอ < 120°
KNEE_ANGLE_DANGER = 90       # อันตราย เมื่อเข่างอ < 90°

# ฐานยืน (normalized width)
STANCE_WIDTH_WARNING = 0.05  # ฐานยืนแคบเกินไป

# Sway (การแกว่งตัว) - ค่าเบี่ยงเบนมาตรฐานของจุดศูนย์กลาง
SWAY_WARNING = 0.015
SWAY_DANGER = 0.03

# --- Analysis Settings ---
FRAME_BUFFER_SIZE = 30       # จำนวนเฟรมที่เก็บไว้วิเคราะห์ (sliding window)
FALL_CONFIRM_FRAMES = 5     # จำนวนเฟรมที่ต้องตรวจจับต่อเนื่องเพื่อยืนยัน

# --- Alert Settings ---
ALERT_COOLDOWN_SECONDS = 10  # ระยะเวลาขั้นต่ำระหว่างการแจ้งเตือนแต่ละครั้ง (วินาที)

# --- Database Settings ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_PATH = os.path.join(BASE_DIR, "data", "fall_events.db")

# --- Frontend Path ---
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# --- MJPEG Stream Settings ---
JPEG_QUALITY = 70            # คุณภาพ JPEG สำหรับ stream (0-100)
