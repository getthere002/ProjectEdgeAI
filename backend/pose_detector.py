# ======================================
# Pose Detector Module
# ใช้ MediaPipe Tasks API (PoseLandmarker) สกัด Body Landmarks
# ======================================

import os
import cv2
import numpy as np
import math
import mediapipe as mp

from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision import drawing_utils, PoseLandmarksConnections, HandLandmarksConnections
import time

from config import (
    POSE_MIN_DETECTION_CONFIDENCE,
    POSE_MIN_TRACKING_CONFIDENCE,
    POSE_MODEL_COMPLEXITY
)


class PoseDetector:
    """ตรวจจับท่าทางร่างกายโดยใช้ MediaPipe PoseLandmarker (Tasks API)"""

    # PoseLandmark enum indices
    NOSE = vision.PoseLandmark.NOSE
    LEFT_SHOULDER = vision.PoseLandmark.LEFT_SHOULDER
    RIGHT_SHOULDER = vision.PoseLandmark.RIGHT_SHOULDER
    LEFT_HIP = vision.PoseLandmark.LEFT_HIP
    RIGHT_HIP = vision.PoseLandmark.RIGHT_HIP
    LEFT_KNEE = vision.PoseLandmark.LEFT_KNEE
    RIGHT_KNEE = vision.PoseLandmark.RIGHT_KNEE
    LEFT_ANKLE = vision.PoseLandmark.LEFT_ANKLE
    RIGHT_ANKLE = vision.PoseLandmark.RIGHT_ANKLE
    LEFT_EAR = vision.PoseLandmark.LEFT_EAR
    RIGHT_EAR = vision.PoseLandmark.RIGHT_EAR

    def __init__(self):
        model_path = os.path.join(os.path.dirname(__file__), 'pose_landmarker.task')

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"ไม่พบไฟล์ model: {model_path}\n"
                "กรุณาดาวน์โหลดจาก: https://storage.googleapis.com/mediapipe-models/"
                "pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task"
            )

        # อ่าน model เป็น bytes เพื่อหลีกเลี่ยงปัญหา Unicode path
        with open(model_path, 'rb') as f:
            model_data = f.read()

        base_options = python.BaseOptions(model_asset_buffer=model_data)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            min_pose_detection_confidence=POSE_MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=POSE_MIN_TRACKING_CONFIDENCE,
            num_poses=1
        )
        self.landmarker = vision.PoseLandmarker.create_from_options(options)

        # Hand Landmarker Initialization
        hand_model_path = os.path.join(os.path.dirname(__file__), 'hand_landmarker.task')
        if not os.path.exists(hand_model_path):
            raise FileNotFoundError(f"ไม่พบไฟล์ model: {hand_model_path}")
            
        with open(hand_model_path, 'rb') as f:
            hand_model_data = f.read()

        hand_base_options = python.BaseOptions(model_asset_buffer=hand_model_data)
        hand_options = vision.HandLandmarkerOptions(
            base_options=hand_base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_hands=1,
            min_hand_detection_confidence=0.2,
            min_hand_presence_confidence=0.2
        )
        self.hand_landmarker = vision.HandLandmarker.create_from_options(hand_options)

        # Connections for drawing
        self.pose_connections = PoseLandmarksConnections.POSE_LANDMARKS
        self.hand_connections = HandLandmarksConnections.HAND_CONNECTIONS

        # Custom drawing specs
        self.landmark_style = drawing_utils.DrawingSpec(
            color=(0, 255, 136), thickness=2, circle_radius=3
        )
        self.connection_style = drawing_utils.DrawingSpec(
            color=(0, 200, 255), thickness=2
        )

        # Frame counter for VIDEO mode timestamps
        self._frame_count = 0

        # State Machine for SOS Gesture
        # 0: None, 1: Thumb Tucked (Palm open), 2: Fist (SOS!)
        self.sos_state = 0
        self.sos_state_1_time = 0

    def process_frame(self, frame):
        """
        ประมวลผลเฟรมเพื่อตรวจจับ pose landmarks
        
        Returns:
            landmarks: list of dict{'x','y','z','visibility'} หรือ None ถ้าตรวจไม่พบ
            annotated_frame: เฟรมที่วาด skeleton overlay แล้ว
            sos_detected: boolean ว่าตรวจพบ SOS Signal หรือไม่
        """
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        # VIDEO mode requires monotonically increasing timestamp in ms
        self._frame_count += 1
        timestamp_ms = int(self._frame_count * (1000 / 30))  # assume ~30fps

        result = self.landmarker.detect_for_video(mp_image, timestamp_ms)

        annotated_frame = frame.copy()
        landmarks = None

        if result.pose_landmarks and len(result.pose_landmarks) > 0:
            pose_lms = result.pose_landmarks[0]  # first detected person

            # วาด skeleton overlay
            self._draw_landmarks(annotated_frame, pose_lms)

            # แปลง landmarks เป็น list of dict
            landmarks = []
            for lm in pose_lms:
                landmarks.append({
                    'x': lm.x,
                    'y': lm.y,
                    'z': lm.z,
                    'visibility': lm.visibility if hasattr(lm, 'visibility') else 1.0
                })

        # Process Hand Landmarks for SOS Gesture (using ROI based on wrists)
        sos_detected = False
        h, w = frame.shape[:2]

        if result.pose_landmarks and len(result.pose_landmarks) > 0:
            pose_lms = result.pose_landmarks[0]
            
            # Calculate dynamic scale based on shoulder width
            ls = pose_lms[11] # LEFT_SHOULDER
            rs = pose_lms[12] # RIGHT_SHOULDER
            shoulder_width = math.hypot((ls.x - rs.x) * w, (ls.y - rs.y) * h)
            # Box size = 2x shoulder width, but at least 60 pixels
            box_size = max(int(shoulder_width * 2.5), 60)
            half_box = box_size // 2
            
            # Check wrists for ROI cropping
            wrist_indices = [15, 16] # LEFT_WRIST, RIGHT_WRIST
            for idx in wrist_indices:
                wrist = pose_lms[idx]
                # If wrist is visible enough
                if hasattr(wrist, 'visibility') and wrist.visibility > 0.1:
                    cx, cy = int(wrist.x * w), int(wrist.y * h)
                    
                    x1, y1 = max(0, cx - half_box), max(0, cy - half_box)
                    x2, y2 = min(w, cx + half_box), min(h, cy + half_box)
                    
                    if x2 - x1 < 20 or y2 - y1 < 20:
                        continue
                        
                    # Copy to ensure contiguous array for mediapipe
                    crop = rgb_frame[y1:y2, x1:x2].copy()
                    mp_crop = mp.Image(image_format=mp.ImageFormat.SRGB, data=crop)
                    
                    # Process crop in IMAGE mode
                    hand_result = self.hand_landmarker.detect(mp_crop)
                    
                    if hand_result.hand_landmarks:
                        for hand_lms in hand_result.hand_landmarks:
                            # Map normalized coordinates in crop back to normalized in full frame
                            for lm in hand_lms:
                                lm.x = ((lm.x * (x2 - x1)) + x1) / w
                                lm.y = ((lm.y * (y2 - y1)) + y1) / h
                                
                            self._draw_hand_landmarks(annotated_frame, hand_lms)
                            if self._detect_sos_gesture(hand_lms):
                                sos_detected = True

        return landmarks, annotated_frame, sos_detected

    def _detect_sos_gesture(self, hand_landmarks):
        """
        ตรวจจับ Universal Signal for Help (Thumb tucked -> Fist)
        """
        if not hand_landmarks:
            return False

        # Helper: Calculate distance between two landmarks
        def dist(lm1, lm2):
            return math.hypot(lm1.x - lm2.x, lm1.y - lm2.y)

        # Landmarks
        wrist = hand_landmarks[0]
        thumb_tip = hand_landmarks[4]
        index_mcp = hand_landmarks[5]
        pinky_mcp = hand_landmarks[17]
        
        finger_tips = [hand_landmarks[8], hand_landmarks[12], hand_landmarks[16], hand_landmarks[20]]
        finger_pips = [hand_landmarks[6], hand_landmarks[10], hand_landmarks[14], hand_landmarks[18]]
        finger_mcps = [hand_landmarks[5], hand_landmarks[9], hand_landmarks[13], hand_landmarks[17]]

        # Check if thumb is tucked in
        # Thumb tip is closer to pinky MCP than index MCP is to pinky MCP (crossed the palm)
        thumb_tucked = dist(thumb_tip, pinky_mcp) < dist(index_mcp, pinky_mcp)

        # Check if 4 fingers are straight (Palm open)
        # Finger tips are further from wrist than their corresponding PIPs
        fingers_straight = all(dist(tip, wrist) > dist(pip, wrist) for tip, pip in zip(finger_tips, finger_pips))

        # Check if 4 fingers are folded (Fist)
        # Finger tips are closer to wrist than their MCPs (or close to palm)
        fingers_folded = all(dist(tip, wrist) < dist(mcp, wrist) * 1.2 for tip, mcp in zip(finger_tips, finger_mcps))

        current_time = time.time()

        if thumb_tucked and fingers_straight:
            self.sos_state = 1
            self.sos_state_1_time = current_time
        elif fingers_folded and self.sos_state == 1:
            # If transitioned from State 1 to State 2 within 3 seconds
            if current_time - self.sos_state_1_time < 3.0:
                self.sos_state = 2 # Trigger!
                # Reset state after trigger to avoid spam, but keep returning true for a moment
                # For simplicity, we just return True
                return True
        elif not fingers_folded and not (thumb_tucked and fingers_straight):
            # Reset state if hand is in a different shape for a while
            if current_time - self.sos_state_1_time > 3.0:
                self.sos_state = 0

        return False

    def _draw_hand_landmarks(self, frame, hand_landmarks):
        """วาด hand connections บนเฟรม"""
        h, w = frame.shape[:2]
        for connection in self.hand_connections:
            start_idx = connection.start
            end_idx = connection.end
            
            if start_idx < len(hand_landmarks) and end_idx < len(hand_landmarks):
                start_lm = hand_landmarks[start_idx]
                end_lm = hand_landmarks[end_idx]
                
                start_point = (int(start_lm.x * w), int(start_lm.y * h))
                end_point = (int(end_lm.x * w), int(end_lm.y * h))
                
                if (0 <= start_point[0] < w and 0 <= start_point[1] < h and
                    0 <= end_point[0] < w and 0 <= end_point[1] < h):
                    cv2.line(frame, start_point, end_point, (255, 100, 0), 2)
                    
        for lm in hand_landmarks:
            cx, cy = int(lm.x * w), int(lm.y * h)
            if 0 <= cx < w and 0 <= cy < h:
                cv2.circle(frame, (cx, cy), 2, (0, 100, 255), -1)

    def _draw_landmarks(self, frame, pose_landmarks):
        """วาด skeleton overlay บนเฟรม"""
        h, w = frame.shape[:2]

        # วาด connections
        for connection in self.pose_connections:
            start_idx = connection.start
            end_idx = connection.end

            if start_idx < len(pose_landmarks) and end_idx < len(pose_landmarks):
                start_lm = pose_landmarks[start_idx]
                end_lm = pose_landmarks[end_idx]

                start_point = (int(start_lm.x * w), int(start_lm.y * h))
                end_point = (int(end_lm.x * w), int(end_lm.y * h))

                # ตรวจสอบว่าอยู่ในภาพ
                if (0 <= start_point[0] < w and 0 <= start_point[1] < h and
                    0 <= end_point[0] < w and 0 <= end_point[1] < h):
                    cv2.line(frame, start_point, end_point,
                             self.connection_style.color, self.connection_style.thickness)

        # วาด landmarks (points)
        for lm in pose_landmarks:
            cx, cy = int(lm.x * w), int(lm.y * h)
            if 0 <= cx < w and 0 <= cy < h:
                cv2.circle(frame, (cx, cy),
                           self.landmark_style.circle_radius,
                           self.landmark_style.color, -1)

    def calculate_body_angle(self, landmarks):
        """
        คำนวณมุมของลำตัวเทียบกับแนวตั้ง
        ใช้เส้นจาก midpoint ของ hip ไปยัง midpoint ของ shoulder
        
        Returns:
            angle: มุม (องศา) จากแนวตั้ง (0° = ตั้งตรง, 90° = นอน)
        """
        if not landmarks:
            return None

        ls = int(self.LEFT_SHOULDER)
        rs = int(self.RIGHT_SHOULDER)
        lh = int(self.LEFT_HIP)
        rh = int(self.RIGHT_HIP)

        # คำนวณ midpoint ของไหล่
        mid_shoulder_x = (landmarks[ls]['x'] + landmarks[rs]['x']) / 2
        mid_shoulder_y = (landmarks[ls]['y'] + landmarks[rs]['y']) / 2

        # คำนวณ midpoint ของสะโพก
        mid_hip_x = (landmarks[lh]['x'] + landmarks[rh]['x']) / 2
        mid_hip_y = (landmarks[lh]['y'] + landmarks[rh]['y']) / 2

        # คำนวณมุมจากแนวตั้ง
        dx = mid_shoulder_x - mid_hip_x
        dy = mid_shoulder_y - mid_hip_y

        # มุมจากแนวตั้ง (0 = ตั้งตรง)
        angle = abs(math.degrees(math.atan2(dx, -dy)))

        return round(angle, 1)

    def calculate_center_of_gravity(self, landmarks):
        """
        คำนวณจุดศูนย์กลางมวลโดยประมาณ
        ใช้ค่าเฉลี่ยถ่วงน้ำหนักของ key landmarks
        
        Returns:
            (x, y): พิกัด normalized ของจุดศูนย์กลางมวล
        """
        if not landmarks:
            return None

        # Weighted average ของ key body points
        weights = {
            int(self.NOSE): 0.1,
            int(self.LEFT_SHOULDER): 0.15,
            int(self.RIGHT_SHOULDER): 0.15,
            int(self.LEFT_HIP): 0.2,
            int(self.RIGHT_HIP): 0.2,
            int(self.LEFT_KNEE): 0.1,
            int(self.RIGHT_KNEE): 0.1
        }

        total_weight = sum(weights.values())
        cog_x = sum(landmarks[idx]['x'] * w for idx, w in weights.items()) / total_weight
        cog_y = sum(landmarks[idx]['y'] * w for idx, w in weights.items()) / total_weight

        return (round(cog_x, 4), round(cog_y, 4))

    def calculate_knee_angles(self, landmarks):
        """
        คำนวณมุมข้อเข่าทั้งสองข้าง
        
        Returns:
            (left_angle, right_angle): มุมเข่า (องศา) - 180° = ตรง, < 90° = งอมาก
        """
        if not landmarks:
            return None, None

        left_angle = self._calculate_angle(
            landmarks[int(self.LEFT_HIP)],
            landmarks[int(self.LEFT_KNEE)],
            landmarks[int(self.LEFT_ANKLE)]
        )

        right_angle = self._calculate_angle(
            landmarks[int(self.RIGHT_HIP)],
            landmarks[int(self.RIGHT_KNEE)],
            landmarks[int(self.RIGHT_ANKLE)]
        )

        return round(left_angle, 1), round(right_angle, 1)

    def calculate_stance_width(self, landmarks):
        """
        คำนวณความกว้างฐานยืน (ระยะห่างระหว่างข้อเท้า)
        
        Returns:
            width: ความกว้าง (normalized)
        """
        if not landmarks:
            return None

        la = int(self.LEFT_ANKLE)
        ra = int(self.RIGHT_ANKLE)

        width = abs(landmarks[la]['x'] - landmarks[ra]['x'])
        return round(width, 4)

    def get_head_position(self, landmarks):
        """ดึงตำแหน่ง head (nose)"""
        if not landmarks:
            return None
        nose = int(self.NOSE)
        return (landmarks[nose]['x'], landmarks[nose]['y'])

    def _calculate_angle(self, point_a, point_b, point_c):
        """
        คำนวณมุมที่จุด B ระหว่าง A-B-C
        """
        a = np.array([point_a['x'], point_a['y']])
        b = np.array([point_b['x'], point_b['y']])
        c = np.array([point_c['x'], point_c['y']])

        ba = a - b
        bc = c - b

        cosine = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
        cosine = np.clip(cosine, -1.0, 1.0)
        angle = np.degrees(np.arccos(cosine))

        return angle

    def draw_risk_overlay(self, frame, risk_level, body_angle, metrics=None):
        """
        วาด overlay แสดงข้อมูลบนเฟรม
        """
        h, w = frame.shape[:2]

        # สีตาม risk level
        colors = {
            'safe': (0, 230, 118),       # เขียว
            'warning': (0, 171, 255),     # เหลือง/ส้ม (BGR)
            'danger': (23, 23, 255),      # แดง
            'fall': (0, 0, 213)           # แดงเข้ม
        }
        color = colors.get(risk_level, (200, 200, 200))

        # วาดกรอบสถานะ
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (250, 120), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        # แสดง Risk Level
        risk_text = {
            'safe': 'SAFE',
            'warning': 'WARNING',
            'danger': 'DANGER',
            'fall': 'FALL DETECTED!'
        }
        cv2.putText(frame, risk_text.get(risk_level, 'N/A'),
                     (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        # แสดง Body Angle
        if body_angle is not None:
            cv2.putText(frame, f"Body Angle: {body_angle:.1f} deg",
                         (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # แสดง Metrics เพิ่มเติม
        if metrics:
            y_pos = 100
            if 'velocity' in metrics and metrics['velocity'] is not None:
                cv2.putText(frame, f"Velocity: {metrics['velocity']:.4f}",
                             (20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

        # วาดกรอบสีรอบเฟรมตาม risk level
        if risk_level in ('danger', 'fall'):
            cv2.rectangle(frame, (0, 0), (w - 1, h - 1), color, 4)

        return frame

    def close(self):
        """ปิด MediaPipe resources"""
        self.landmarker.close()
        self.hand_landmarker.close()
