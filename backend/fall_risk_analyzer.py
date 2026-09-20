# ======================================
# Fall Risk Analyzer
# วิเคราะห์ความเสี่ยงต่อการหกล้มจาก Pose Data
# ======================================

import time
import numpy as np
from collections import deque
from config import (
    FRAME_BUFFER_SIZE,
    FALL_CONFIRM_FRAMES,
    BODY_ANGLE_WARNING,
    BODY_ANGLE_DANGER,
    BODY_ANGLE_FALL,
    VELOCITY_WARNING,
    VELOCITY_DANGER,
    VELOCITY_FALL,
    KNEE_ANGLE_WARNING,
    KNEE_ANGLE_DANGER,
    STANCE_WIDTH_WARNING,
    SWAY_WARNING,
    SWAY_DANGER
)


class FallRiskAnalyzer:
    """วิเคราะห์ความเสี่ยงต่อการหกล้มจากข้อมูล Pose"""

    RISK_LEVELS = ['safe', 'warning', 'danger', 'fall']
    RISK_SCORES = {'safe': 0, 'warning': 1, 'danger': 2, 'fall': 3}

    def __init__(self):
        # Sliding window buffers
        self.cog_buffer = deque(maxlen=FRAME_BUFFER_SIZE)
        self.angle_buffer = deque(maxlen=FRAME_BUFFER_SIZE)
        self.head_y_buffer = deque(maxlen=FRAME_BUFFER_SIZE)
        self.risk_buffer = deque(maxlen=FALL_CONFIRM_FRAMES)

        # Current state
        self.current_risk = 'safe'
        self.current_metrics = {}
        self.prev_cog = None
        self.velocity = 0.0
        self.sway = 0.0

        # Timestamps
        self.last_analysis_time = time.time()

        # Thresholds (can be updated dynamically)
        self.thresholds = {
            'body_angle_warning': BODY_ANGLE_WARNING,
            'body_angle_danger': BODY_ANGLE_DANGER,
            'body_angle_fall': BODY_ANGLE_FALL,
            'velocity_warning': VELOCITY_WARNING,
            'velocity_danger': VELOCITY_DANGER,
            'velocity_fall': VELOCITY_FALL,
            'knee_angle_warning': KNEE_ANGLE_WARNING,
            'knee_angle_danger': KNEE_ANGLE_DANGER,
            'stance_width_warning': STANCE_WIDTH_WARNING,
            'sway_warning': SWAY_WARNING,
            'sway_danger': SWAY_DANGER,
        }

    def analyze(self, body_angle, cog, knee_angles, stance_width, head_pos, sos_detected=False):
        """
        วิเคราะห์ปัจจัยเสี่ยงทั้งหมด
        
        Args:
            body_angle: มุมลำตัวจากแนวตั้ง
            cog: (x, y) จุดศูนย์กลางมวล
            knee_angles: (left, right) มุมข้อเข่า
            stance_width: ความกว้างฐานยืน
            head_pos: (x, y) ตำแหน่ง head
            sos_detected: bool ว่าพบสัญลักษณ์ขอความช่วยเหลือหรือไม่
            
        Returns:
            dict: ผลวิเคราะห์ประกอบด้วย risk_level, metrics, factors
        """
        risk_factors = []
        risk_scores = []

        # === Factor 1: Body Angle (มุมลำตัว) ===
        angle_risk = self._analyze_body_angle(body_angle)
        if angle_risk:
            risk_factors.append(angle_risk)
            risk_scores.append(self.RISK_SCORES[angle_risk['level']])

        # === Factor 2: Velocity (ความเร็วการตกลง) ===
        velocity_risk = self._analyze_velocity(cog)
        if velocity_risk:
            risk_factors.append(velocity_risk)
            risk_scores.append(self.RISK_SCORES[velocity_risk['level']])

        # === Factor 3: Knee Angles (มุมเข่า) ===
        knee_risk = self._analyze_knee_angles(knee_angles)
        if knee_risk:
            risk_factors.append(knee_risk)
            risk_scores.append(self.RISK_SCORES[knee_risk['level']])

        # === Factor 4: Stance Width (ฐานยืน) ===
        stance_risk = self._analyze_stance_width(stance_width)
        if stance_risk:
            risk_factors.append(stance_risk)
            risk_scores.append(self.RISK_SCORES[stance_risk['level']])

        # === Factor 5: Sway (การแกว่งตัว) ===
        sway_risk = self._analyze_sway(cog)
        if sway_risk:
            risk_factors.append(sway_risk)
            risk_scores.append(self.RISK_SCORES[sway_risk['level']])

        # === Factor 6: Rapid Head Drop ===
        head_risk = self._analyze_head_drop(head_pos)
        if head_risk:
            risk_factors.append(head_risk)
            risk_scores.append(self.RISK_SCORES[head_risk['level']])

        # === Factor 7: SOS Gesture ===
        if sos_detected:
            risk_factors.append({'factor': 'sos', 'level': 'fall', 'message': 'ตรวจพบสัญลักษณ์ขอความช่วยเหลือ (SOS)'})
            risk_scores.append(self.RISK_SCORES['fall'])

        # === คำนวณ Overall Risk Level ===
        if risk_scores:
            max_score = max(risk_scores)
            avg_score = sum(risk_scores) / len(risk_scores)

            # ใช้ weighted approach: ถ้ามี factor ใดเป็น fall ให้เป็น fall
            # ถ้า avg สูง ให้ยกระดับ
            if max_score >= 3 or sos_detected:
                overall_risk = 'fall'
            elif max_score >= 2 and avg_score >= 1.5:
                overall_risk = 'danger'
            elif max_score >= 2 or avg_score >= 1.0:
                overall_risk = 'warning' if avg_score < 1.5 else 'danger'
            elif max_score >= 1:
                overall_risk = 'warning'
            else:
                overall_risk = 'safe'
        else:
            overall_risk = 'safe'

        # Temporal smoothing: ใช้ buffer เพื่อลด false positive (แต่ถ้า SOS ให้ผ่านเลย)
        self.risk_buffer.append(self.RISK_SCORES[overall_risk])
        smoothed_risk = 'fall' if sos_detected else self._smooth_risk()

        # Calculate confidence
        confidence = self._calculate_confidence(risk_scores)

        # Prepare metrics
        left_knee, right_knee = knee_angles if knee_angles else (None, None)
        self.current_metrics = {
            'body_angle': body_angle,
            'velocity': round(self.velocity, 4),
            'left_knee_angle': left_knee,
            'right_knee_angle': right_knee,
            'stance_width': stance_width,
            'sway': round(self.sway, 4),
            'confidence': confidence
        }
        self.current_risk = smoothed_risk

        return {
            'risk_level': smoothed_risk,
            'metrics': self.current_metrics,
            'factors': risk_factors,
            'confidence': confidence,
            'timestamp': time.time()
        }

    def _analyze_body_angle(self, angle):
        """วิเคราะห์มุมลำตัว"""
        if angle is None:
            return None

        self.angle_buffer.append(angle)

        if angle >= self.thresholds['body_angle_fall']:
            return {'factor': 'body_angle', 'level': 'fall',
                    'value': angle, 'message': f'ลำตัวเอียง {angle:.1f}° (หกล้ม)'}
        elif angle >= self.thresholds['body_angle_danger']:
            return {'factor': 'body_angle', 'level': 'danger',
                    'value': angle, 'message': f'ลำตัวเอียง {angle:.1f}° (อันตราย)'}
        elif angle >= self.thresholds['body_angle_warning']:
            return {'factor': 'body_angle', 'level': 'warning',
                    'value': angle, 'message': f'ลำตัวเอียง {angle:.1f}° (ระวัง)'}
        return None

    def _analyze_velocity(self, cog):
        """วิเคราะห์ความเร็วการเคลื่อนที่ของ center of gravity"""
        if cog is None:
            return None

        self.cog_buffer.append(cog)

        if self.prev_cog is not None:
            # คำนวณความเร็วแนวดิ่ง (y-axis, ลงเป็นบวก)
            dy = cog[1] - self.prev_cog[1]
            dx = cog[0] - self.prev_cog[0]
            self.velocity = max(dy, 0)  # สนใจเฉพาะการเคลื่อนที่ลง

            if self.velocity >= self.thresholds['velocity_fall']:
                self.prev_cog = cog
                return {'factor': 'velocity', 'level': 'fall',
                        'value': self.velocity, 'message': 'ตกลงเร็วมาก (หกล้ม)'}
            elif self.velocity >= self.thresholds['velocity_danger']:
                self.prev_cog = cog
                return {'factor': 'velocity', 'level': 'danger',
                        'value': self.velocity, 'message': 'ตกลงเร็ว (อันตราย)'}
            elif self.velocity >= self.thresholds['velocity_warning']:
                self.prev_cog = cog
                return {'factor': 'velocity', 'level': 'warning',
                        'value': self.velocity, 'message': 'เคลื่อนที่ลงเร็ว (ระวัง)'}

        self.prev_cog = cog
        return None

    def _analyze_knee_angles(self, knee_angles):
        """วิเคราะห์มุมเข่า"""
        if knee_angles is None:
            return None

        left_knee, right_knee = knee_angles
        if left_knee is None or right_knee is None:
            return None

        min_knee = min(left_knee, right_knee)

        if min_knee < self.thresholds['knee_angle_danger']:
            return {'factor': 'knee_angle', 'level': 'danger',
                    'value': min_knee, 'message': f'เข่างอมาก {min_knee:.1f}° (อันตราย)'}
        elif min_knee < self.thresholds['knee_angle_warning']:
            return {'factor': 'knee_angle', 'level': 'warning',
                    'value': min_knee, 'message': f'เข่างอ {min_knee:.1f}° (ระวัง)'}
        return None

    def _analyze_stance_width(self, stance_width):
        """วิเคราะห์ความกว้างฐานยืน"""
        if stance_width is None:
            return None

        if stance_width < self.thresholds['stance_width_warning']:
            return {'factor': 'stance_width', 'level': 'warning',
                    'value': stance_width, 'message': 'ฐานยืนแคบ (เสี่ยงเสียสมดุล)'}
        return None

    def _analyze_sway(self, cog):
        """วิเคราะห์การแกว่งตัว (ค่าเบี่ยงเบนมาตรฐานของ CoG)"""
        if cog is None or len(self.cog_buffer) < 10:
            return None

        # คำนวณ standard deviation ของ x-coordinate ของ CoG
        recent_x = [c[0] for c in list(self.cog_buffer)[-15:]]
        self.sway = float(np.std(recent_x))

        if self.sway >= self.thresholds['sway_danger']:
            return {'factor': 'sway', 'level': 'danger',
                    'value': self.sway, 'message': f'แกว่งตัวมาก (อันตราย)'}
        elif self.sway >= self.thresholds['sway_warning']:
            return {'factor': 'sway', 'level': 'warning',
                    'value': self.sway, 'message': f'แกว่งตัว (ระวัง)'}
        return None

    def _analyze_head_drop(self, head_pos):
        """วิเคราะห์การตกลงของศีรษะอย่างรวดเร็ว"""
        if head_pos is None:
            return None

        self.head_y_buffer.append(head_pos[1])

        if len(self.head_y_buffer) < 5:
            return None

        # เปรียบเทียบตำแหน่ง head ระหว่าง 5 เฟรมก่อนกับปัจจุบัน
        recent = list(self.head_y_buffer)
        head_drop = recent[-1] - recent[-5]

        if head_drop > 0.15:  # ศีรษะตกลงมาก (y เพิ่มขึ้น = ลงล่าง)
            return {'factor': 'head_drop', 'level': 'fall',
                    'value': head_drop, 'message': 'ศีรษะตกลงเร็วมาก (หกล้ม)'}
        elif head_drop > 0.08:
            return {'factor': 'head_drop', 'level': 'danger',
                    'value': head_drop, 'message': 'ศีรษะตกลง (อันตราย)'}
        return None

    def _smooth_risk(self):
        """ทำ temporal smoothing เพื่อลด false positive"""
        if not self.risk_buffer:
            return 'safe'

        buffer_list = list(self.risk_buffer)

        # ถ้า buffer ส่วนใหญ่เป็น fall → ยืนยัน fall
        fall_count = sum(1 for r in buffer_list if r >= 3)
        if fall_count >= FALL_CONFIRM_FRAMES * 0.6:
            return 'fall'

        # ถ้า buffer ส่วนใหญ่เป็น danger
        danger_count = sum(1 for r in buffer_list if r >= 2)
        if danger_count >= FALL_CONFIRM_FRAMES * 0.6:
            return 'danger'

        # ใช้ค่ามากสุดที่เกิดขึ้นบ่อย
        avg = sum(buffer_list) / len(buffer_list)
        if avg >= 2.0:
            return 'danger'
        elif avg >= 1.0:
            return 'warning'
        return 'safe'

    def _calculate_confidence(self, risk_scores):
        """คำนวณ confidence score"""
        if not risk_scores:
            return 1.0

        # ยิ่ง risk factors เห็นตรงกันมากยิ่ง confidence สูง
        if len(risk_scores) <= 1:
            return 0.5

        max_score = max(risk_scores)
        agreeing = sum(1 for s in risk_scores if s >= max_score - 1)
        confidence = agreeing / len(risk_scores)

        return round(confidence, 2)

    def update_thresholds(self, new_thresholds):
        """อัปเดต threshold values"""
        for key, value in new_thresholds.items():
            if key in self.thresholds:
                self.thresholds[key] = value

    def reset(self):
        """รีเซ็ต buffers ทั้งหมด"""
        self.cog_buffer.clear()
        self.angle_buffer.clear()
        self.head_y_buffer.clear()
        self.risk_buffer.clear()
        self.prev_cog = None
        self.velocity = 0.0
        self.sway = 0.0
        self.current_risk = 'safe'
