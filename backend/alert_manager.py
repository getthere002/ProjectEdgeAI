# ======================================
# Alert Manager
# จัดการระบบแจ้งเตือน
# ======================================

import time
import json
from datetime import datetime
from config import ALERT_COOLDOWN_SECONDS


class AlertManager:
    """จัดการการแจ้งเตือนเมื่อตรวจพบความเสี่ยง"""

    def __init__(self, database):
        self.database = database
        self.last_alert_time = {}  # track cooldown per risk level
        self.connected_clients = set()  # WebSocket clients
        self.alert_queue = []  # Queue สำหรับส่งไปยัง frontend

    def check_and_alert(self, analysis_result):
        """
        ตรวจสอบผลวิเคราะห์และสร้างการแจ้งเตือนถ้าจำเป็น
        
        Args:
            analysis_result: dict จาก FallRiskAnalyzer.analyze()
            
        Returns:
            alert: dict ข้อมูลแจ้งเตือน หรือ None
        """
        risk_level = analysis_result['risk_level']

        # ไม่แจ้งเตือนถ้าสถานะ safe
        if risk_level == 'safe':
            return None

        # ตรวจสอบ cooldown
        now = time.time()
        last_time = self.last_alert_time.get(risk_level, 0)

        if now - last_time < ALERT_COOLDOWN_SECONDS:
            return None

        # สร้าง alert message
        messages = {
            'warning': '⚠️ ตรวจพบท่าทางเสี่ยง - กรุณาเฝ้าระวัง',
            'danger': '🚨 อันตราย! ตรวจพบท่าทางเสี่ยงสูง',
            'fall': '🆘 ตรวจพบการหกล้ม! ต้องการความช่วยเหลือทันที'
        }

        factors_text = []
        for factor in analysis_result.get('factors', []):
            if factor and factor.get('message'):
                factors_text.append(factor['message'])

        alert = {
            'type': 'alert',
            'risk_level': risk_level,
            'message': messages.get(risk_level, 'Unknown risk'),
            'details': factors_text,
            'metrics': analysis_result.get('metrics', {}),
            'confidence': analysis_result.get('confidence', 0),
            'timestamp': datetime.now().isoformat(),
            'timestamp_display': datetime.now().strftime('%H:%M:%S'),
        }

        # บันทึกลง database
        self.database.record_alert(risk_level, alert['message'])

        # บันทึก event
        metrics = analysis_result.get('metrics', {})
        self.database.record_event(
            risk_level=risk_level,
            body_angle=metrics.get('body_angle'),
            velocity=metrics.get('velocity'),
            knee_angle=metrics.get('left_knee_angle'),
            sway_value=metrics.get('sway'),
            stance_width=metrics.get('stance_width'),
            confidence=metrics.get('confidence'),
            notes='; '.join(factors_text) if factors_text else None
        )

        # อัปเดต cooldown
        self.last_alert_time[risk_level] = now

        # เพิ่มเข้า queue
        self.alert_queue.append(alert)

        return alert

    def get_pending_alerts(self):
        """ดึง alerts ที่ยังไม่ได้ส่ง"""
        alerts = self.alert_queue.copy()
        self.alert_queue.clear()
        return alerts

    def get_alert_data_json(self, alert):
        """แปลง alert เป็น JSON string"""
        return json.dumps(alert, ensure_ascii=False)

    def update_cooldown(self, seconds):
        """อัปเดตค่า cooldown"""
        global ALERT_COOLDOWN_SECONDS
        ALERT_COOLDOWN_SECONDS = seconds
