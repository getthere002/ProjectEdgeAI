# ======================================
# Database Manager
# จัดการฐานข้อมูล SQLite สำหรับบันทึกเหตุการณ์
# ======================================

import sqlite3
import os
import json
from datetime import datetime, timedelta
from config import DATABASE_PATH


class DatabaseManager:
    """จัดการฐานข้อมูลสำหรับบันทึกเหตุการณ์การตรวจจับ"""

    def __init__(self):
        # สร้าง directory ถ้ายังไม่มี
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        self.db_path = DATABASE_PATH
        self._init_database()

    def _get_connection(self):
        """สร้าง connection ใหม่ (thread-safe)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self):
        """สร้างตารางในฐานข้อมูล"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # ตารางบันทึกเหตุการณ์
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fall_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                body_angle REAL,
                velocity REAL,
                knee_angle REAL,
                sway_value REAL,
                stance_width REAL,
                confidence REAL,
                skeleton_data TEXT,
                notes TEXT
            )
        """)

        # ตารางประวัติการแจ้งเตือน
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                message TEXT,
                acknowledged INTEGER DEFAULT 0
            )
        """)

        # สร้าง index สำหรับการค้นหาตาม timestamp
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fall_events_timestamp 
            ON fall_events(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_alert_history_timestamp 
            ON alert_history(timestamp)
        """)

        conn.commit()
        conn.close()

    def record_event(self, risk_level, body_angle=None, velocity=None,
                     knee_angle=None, sway_value=None, stance_width=None,
                     confidence=None, skeleton_data=None, notes=None):
        """บันทึกเหตุการณ์ที่ตรวจจับได้"""
        conn = self._get_connection()
        cursor = conn.cursor()

        skeleton_json = json.dumps(skeleton_data) if skeleton_data else None

        cursor.execute("""
            INSERT INTO fall_events 
            (timestamp, risk_level, body_angle, velocity, knee_angle, 
             sway_value, stance_width, confidence, skeleton_data, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            risk_level,
            body_angle,
            velocity,
            knee_angle,
            sway_value,
            stance_width,
            confidence,
            skeleton_json,
            notes
        ))

        conn.commit()
        conn.close()

    def record_alert(self, risk_level, message):
        """บันทึกการแจ้งเตือน"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO alert_history (timestamp, risk_level, message)
            VALUES (?, ?, ?)
        """, (datetime.now().isoformat(), risk_level, message))

        conn.commit()
        conn.close()

    def get_events_today(self):
        """ดึงเหตุการณ์ของวันนี้"""
        conn = self._get_connection()
        cursor = conn.cursor()

        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""
            SELECT id, timestamp, risk_level, body_angle, velocity, 
                   knee_angle, sway_value, confidence, notes
            FROM fall_events 
            WHERE timestamp LIKE ?
            ORDER BY timestamp DESC
        """, (f"{today}%",))

        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def get_recent_events(self, limit=50):
        """ดึงเหตุการณ์ล่าสุด"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, timestamp, risk_level, body_angle, velocity, 
                   knee_angle, sway_value, confidence, notes
            FROM fall_events 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (limit,))

        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def get_recent_alerts(self, limit=20):
        """ดึงประวัติแจ้งเตือนล่าสุด"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, timestamp, risk_level, message, acknowledged
            FROM alert_history 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (limit,))

        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def get_stats(self):
        """ดึงสถิติรวม"""
        conn = self._get_connection()
        cursor = conn.cursor()

        today = datetime.now().strftime("%Y-%m-%d")
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        # สถิติวันนี้
        cursor.execute("""
            SELECT risk_level, COUNT(*) as count 
            FROM fall_events 
            WHERE timestamp LIKE ?
            GROUP BY risk_level
        """, (f"{today}%",))
        today_stats = {row["risk_level"]: row["count"] for row in cursor.fetchall()}

        # สถิติ 7 วันย้อนหลัง
        cursor.execute("""
            SELECT DATE(timestamp) as date, risk_level, COUNT(*) as count 
            FROM fall_events 
            WHERE timestamp >= ?
            GROUP BY DATE(timestamp), risk_level
            ORDER BY date
        """, (week_ago,))
        weekly_raw = cursor.fetchall()

        weekly_stats = {}
        for row in weekly_raw:
            date = row["date"]
            if date not in weekly_stats:
                weekly_stats[date] = {}
            weekly_stats[date][row["risk_level"]] = row["count"]

        # สถิติรายชั่วโมงของวันนี้
        cursor.execute("""
            SELECT strftime('%H', timestamp) as hour, risk_level, COUNT(*) as count 
            FROM fall_events 
            WHERE timestamp LIKE ?
            GROUP BY strftime('%H', timestamp), risk_level
            ORDER BY hour
        """, (f"{today}%",))
        hourly_raw = cursor.fetchall()

        hourly_stats = {}
        for row in hourly_raw:
            hour = row["hour"]
            if hour not in hourly_stats:
                hourly_stats[hour] = {}
            hourly_stats[hour][row["risk_level"]] = row["count"]

        # จำนวนรวมทั้งหมด
        cursor.execute("SELECT COUNT(*) as total FROM fall_events")
        total = cursor.fetchone()["total"]

        # จำนวน fall events วันนี้
        cursor.execute("""
            SELECT COUNT(*) as falls 
            FROM fall_events 
            WHERE timestamp LIKE ? AND risk_level IN ('danger', 'fall')
        """, (f"{today}%",))
        today_critical = cursor.fetchone()["falls"]

        conn.close()

        return {
            "total_events": total,
            "today_stats": today_stats,
            "today_critical": today_critical,
            "weekly_stats": weekly_stats,
            "hourly_stats": hourly_stats
        }

    def get_hourly_chart_data(self):
        """ดึงข้อมูลสำหรับกราฟรายชั่วโมง"""
        conn = self._get_connection()
        cursor = conn.cursor()

        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""
            SELECT strftime('%H', timestamp) as hour, COUNT(*) as count 
            FROM fall_events 
            WHERE timestamp LIKE ?
            GROUP BY strftime('%H', timestamp)
            ORDER BY hour
        """, (f"{today}%",))

        data = {f"{i:02d}": 0 for i in range(24)}
        for row in cursor.fetchall():
            data[row["hour"]] = row["count"]

        conn.close()
        return data

    def acknowledge_alert(self, alert_id):
        """ยอมรับการแจ้งเตือน"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE alert_history SET acknowledged = 1 WHERE id = ?
        """, (alert_id,))

        conn.commit()
        conn.close()
