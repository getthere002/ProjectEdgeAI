# ======================================
# Main Application
# FastAPI Backend สำหรับระบบตรวจจับท่าทางเสี่ยง
# ======================================

import asyncio
import json
import time
import threading
import cv2
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import (
    SERVER_HOST, SERVER_PORT, CAMERA_SOURCE,
    CAMERA_WIDTH, CAMERA_HEIGHT, JPEG_QUALITY, FRONTEND_DIR
)
from pose_detector import PoseDetector
from fall_risk_analyzer import FallRiskAnalyzer
from alert_manager import AlertManager
from database import DatabaseManager


# ======================================
# Global State
# ======================================
class AppState:
    """Global application state"""
    def __init__(self):
        self.database = DatabaseManager()
        self.pose_detector = PoseDetector()
        self.risk_analyzer = FallRiskAnalyzer()
        self.alert_manager = AlertManager(self.database)

        self.camera = None
        self.is_running = False
        self.current_frame = None
        self.current_annotated_frame = None
        self.current_data = {
            'risk_level': 'safe',
            'metrics': {},
            'factors': [],
            'person_detected': False,
            'fps': 0
        }
        self.websocket_clients = set()
        self.frame_lock = threading.Lock()
        self.fps_counter = 0
        self.fps_time = time.time()
        self.current_fps = 0


state = AppState()


# ======================================
# Camera & Processing Thread
# ======================================
def camera_processing_thread():
    """Thread หลักสำหรับอ่านภาพจากกล้องและประมวลผล"""
    print(f"[Camera] Starting camera: {CAMERA_SOURCE}")

    state.camera = cv2.VideoCapture(CAMERA_SOURCE)
    state.camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    state.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

    if not state.camera.isOpened():
        print("[Camera] ERROR: Cannot open camera!")
        state.is_running = False
        return

    print("[Camera] Camera opened successfully")
    state.is_running = True

    while state.is_running:
        ret, frame = state.camera.read()
        if not ret:
            print("[Camera] WARNING: Failed to read frame")
            time.sleep(0.1)
            continue

        # Flip frame (mirror) for webcam
        frame = cv2.flip(frame, 1)

        # ตรวจจับ Pose
        landmarks, annotated_frame, sos_detected = state.pose_detector.process_frame(frame)

        person_detected = landmarks is not None
        risk_level = 'safe'
        metrics = {}
        factors = []
        alert = None

        if person_detected:
            # คำนวณ metrics
            body_angle = state.pose_detector.calculate_body_angle(landmarks)
            cog = state.pose_detector.calculate_center_of_gravity(landmarks)
            knee_angles = state.pose_detector.calculate_knee_angles(landmarks)
            stance_width = state.pose_detector.calculate_stance_width(landmarks)
            head_pos = state.pose_detector.get_head_position(landmarks)

            # วิเคราะห์ความเสี่ยง
            result = state.risk_analyzer.analyze(
                body_angle, cog, knee_angles, stance_width, head_pos, sos_detected=sos_detected
            )

            risk_level = result['risk_level']
            metrics = result['metrics']
            factors = result['factors']

            # วาด overlay
            annotated_frame = state.pose_detector.draw_risk_overlay(
                annotated_frame, risk_level, body_angle, metrics
            )

            # ตรวจสอบและสร้างแจ้งเตือน
            alert = state.alert_manager.check_and_alert(result)
        else:
            # ไม่พบคน - วาดข้อความ
            cv2.putText(annotated_frame, "No person detected",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 100, 255), 2)

        # FPS calculation
        state.fps_counter += 1
        elapsed = time.time() - state.fps_time
        if elapsed >= 1.0:
            state.current_fps = state.fps_counter / elapsed
            state.fps_counter = 0
            state.fps_time = time.time()

        # อัปเดต shared state
        with state.frame_lock:
            state.current_frame = frame
            state.current_annotated_frame = annotated_frame
            state.current_data = {
                'risk_level': risk_level,
                'metrics': metrics,
                'factors': [f for f in factors if f is not None],
                'person_detected': person_detected,
                'fps': round(state.current_fps, 1),
                'timestamp': datetime.now().isoformat(),
                'alert': alert
            }

    # Cleanup
    if state.camera:
        state.camera.release()
    print("[Camera] Stopped")


# ======================================
# FastAPI Application
# ======================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start camera thread on startup"""
    thread = threading.Thread(target=camera_processing_thread, daemon=True)
    thread.start()
    # รอให้กล้องเริ่มทำงาน
    await asyncio.sleep(2)
    yield
    state.is_running = False


app = FastAPI(
    title="ระบบตรวจจับท่าทางเสี่ยงต่อการหกล้ม",
    description="Edge AI Fall Risk Detection System",
    lifespan=lifespan
)

# Mount static files
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


# ======================================
# Routes
# ======================================

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the main dashboard page"""
    html_path = f"{FRONTEND_DIR}/index.html"
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Frontend not found</h1>", status_code=404)


@app.get("/video_feed")
async def video_feed():
    """MJPEG video stream endpoint"""
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


async def generate_frames():
    """Generator สำหรับ MJPEG stream"""
    while True:
        with state.frame_lock:
            frame = state.current_annotated_frame

        if frame is not None:
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
            _, buffer = cv2.imencode('.jpg', frame, encode_param)
            frame_bytes = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

        await asyncio.sleep(0.033)  # ~30 FPS


# ======================================
# WebSocket Endpoint
# ======================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket สำหรับส่งข้อมูล real-time"""
    await websocket.accept()
    state.websocket_clients.add(websocket)
    print(f"[WebSocket] Client connected ({len(state.websocket_clients)} total)")

    try:
        while True:
            # ส่งข้อมูลปัจจุบันไปยัง client
            with state.frame_lock:
                data = state.current_data.copy()

            # แปลง factors ให้ serializable
            clean_data = {
                'type': 'update',
                'risk_level': data.get('risk_level', 'safe'),
                'person_detected': data.get('person_detected', False),
                'fps': data.get('fps', 0),
                'timestamp': data.get('timestamp', ''),
                'metrics': data.get('metrics', {}),
                'factors': []
            }

            for f in data.get('factors', []):
                if f:
                    clean_data['factors'].append({
                        'factor': f.get('factor', ''),
                        'level': f.get('level', ''),
                        'message': f.get('message', '')
                    })

            # ส่ง alert ถ้ามี
            alert = data.get('alert')
            if alert:
                clean_data['alert'] = alert

            await websocket.send_text(json.dumps(clean_data, ensure_ascii=False))

            # รับ message จาก client (ถ้ามี)
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                await handle_ws_message(websocket, msg)
            except asyncio.TimeoutError:
                pass

            await asyncio.sleep(0.1)  # ส่งข้อมูลทุก 100ms

    except WebSocketDisconnect:
        state.websocket_clients.discard(websocket)
        print(f"[WebSocket] Client disconnected ({len(state.websocket_clients)} total)")
    except Exception as e:
        state.websocket_clients.discard(websocket)
        print(f"[WebSocket] Error: {e}")


async def handle_ws_message(websocket, message):
    """จัดการ message ที่ได้รับจาก WebSocket client"""
    try:
        data = json.loads(message)
        msg_type = data.get('type', '')

        if msg_type == 'acknowledge_alert':
            alert_id = data.get('alert_id')
            if alert_id:
                state.database.acknowledge_alert(alert_id)

        elif msg_type == 'update_thresholds':
            thresholds = data.get('thresholds', {})
            state.risk_analyzer.update_thresholds(thresholds)
            await websocket.send_text(json.dumps({
                'type': 'config_updated',
                'message': 'Thresholds updated successfully'
            }))

        elif msg_type == 'reset_analyzer':
            state.risk_analyzer.reset()
            await websocket.send_text(json.dumps({
                'type': 'info',
                'message': 'Analyzer reset successfully'
            }))

    except json.JSONDecodeError:
        pass


# ======================================
# REST API Endpoints
# ======================================

@app.get("/api/stats")
async def get_stats():
    """ดึงสถิติรวม"""
    stats = state.database.get_stats()
    return JSONResponse(content=stats)


@app.get("/api/events")
async def get_events(limit: int = 50):
    """ดึงเหตุการณ์ล่าสุด"""
    events = state.database.get_recent_events(limit)
    return JSONResponse(content=events)


@app.get("/api/events/today")
async def get_events_today():
    """ดึงเหตุการณ์ของวันนี้"""
    events = state.database.get_events_today()
    return JSONResponse(content=events)


@app.get("/api/alerts")
async def get_alerts(limit: int = 20):
    """ดึงประวัติแจ้งเตือนล่าสุด"""
    alerts = state.database.get_recent_alerts(limit)
    return JSONResponse(content=alerts)


@app.get("/api/hourly")
async def get_hourly_data():
    """ดึงข้อมูลกราฟรายชั่วโมง"""
    data = state.database.get_hourly_chart_data()
    return JSONResponse(content=data)


@app.post("/api/config")
async def update_config(request: Request):
    """อัปเดตค่า thresholds"""
    body = await request.json()
    thresholds = body.get('thresholds', {})
    state.risk_analyzer.update_thresholds(thresholds)
    return JSONResponse(content={"status": "ok", "message": "Configuration updated"})


@app.get("/api/status")
async def get_status():
    """ดึงสถานะระบบ"""
    return JSONResponse(content={
        "camera_active": state.is_running,
        "connected_clients": len(state.websocket_clients),
        "fps": state.current_fps,
        "current_risk": state.current_data.get('risk_level', 'safe'),
        "person_detected": state.current_data.get('person_detected', False)
    })


# ======================================
# Run Server
# ======================================
if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("  Fall Risk Detection System")
    print("  Edge AI Monitoring")
    print("=" * 50)
    print(f"  Dashboard: http://localhost:{SERVER_PORT}")
    print(f"  Camera: {CAMERA_SOURCE}")
    print("=" * 50)

    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)

