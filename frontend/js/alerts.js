// ======================================
// Alert Notification System
// จัดการ Popup และ Toast Notifications
// ======================================

class AlertSystem {
    constructor() {
        this.overlay = document.getElementById('alertOverlay');
        this.popup = document.getElementById('alertPopup');
        this.popupIcon = document.getElementById('alertPopupIcon');
        this.popupTitle = document.getElementById('alertPopupTitle');
        this.popupMessage = document.getElementById('alertPopupMessage');
        this.popupDetails = document.getElementById('alertPopupDetails');
        this.popupTime = document.getElementById('alertPopupTime');
        this.popupBtn = document.getElementById('alertPopupBtn');
        this.toastContainer = document.getElementById('toastContainer');
        this.alertList = document.getElementById('alertList');

        this.alertSound = null;
        this.isPopupVisible = false;
        this.maxAlerts = 50;

        this._initSound();
        this._initEvents();
    }

    /**
     * สร้างเสียงแจ้งเตือนด้วย Web Audio API
     */
    _initSound() {
        this.audioContext = null;
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        } catch (e) {
            console.warn('[Alert] Web Audio API not available');
        }
    }

    /**
     * เล่นเสียงแจ้งเตือน
     */
    _playAlertSound(level) {
        if (!this.audioContext) return;

        // Resume context ถ้า suspended
        if (this.audioContext.state === 'suspended') {
            this.audioContext.resume();
        }

        const frequencies = {
            'warning': [440, 550],
            'danger': [660, 880],
            'fall': [880, 1100, 880, 1100]
        };

        const freqs = frequencies[level] || frequencies['warning'];
        const duration = level === 'fall' ? 0.15 : 0.2;

        freqs.forEach((freq, i) => {
            setTimeout(() => {
                const oscillator = this.audioContext.createOscillator();
                const gainNode = this.audioContext.createGain();

                oscillator.connect(gainNode);
                gainNode.connect(this.audioContext.destination);

                oscillator.frequency.value = freq;
                oscillator.type = level === 'fall' ? 'square' : 'sine';

                gainNode.gain.setValueAtTime(0.15, this.audioContext.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.001, this.audioContext.currentTime + duration);

                oscillator.start(this.audioContext.currentTime);
                oscillator.stop(this.audioContext.currentTime + duration);
            }, i * (duration * 1000 + 50));
        });
    }

    /**
     * ตั้งค่า event listeners
     */
    _initEvents() {
        if (this.popupBtn) {
            this.popupBtn.addEventListener('click', () => {
                this.hidePopup();
            });
        }

        // คลิกที่ overlay เพื่อปิด (เฉพาะ warning)
        if (this.overlay) {
            this.overlay.addEventListener('click', (e) => {
                if (e.target === this.overlay) {
                    this.hidePopup();
                }
            });
        }
    }

    /**
     * แสดง alert ทั้ง popup และ toast
     */
    showAlert(alertData) {
        const level = alertData.risk_level;

        // เล่นเสียง
        this._playAlertSound(level);

        // แสดง popup สำหรับ danger/fall
        if (level === 'danger' || level === 'fall') {
            this.showPopup(alertData);
        }

        // แสดง toast สำหรับทุกระดับ
        this.showToast(alertData);

        // เพิ่มเข้า alert history
        this.addAlertEntry(alertData);

        // เปลี่ยนสถานะ body ถ้า fall
        if (level === 'fall') {
            document.body.classList.add('fall-state');
        }
    }

    /**
     * แสดง popup แจ้งเตือน
     */
    showPopup(alertData) {
        if (!this.overlay || !this.popup) return;

        const icons = {
            'warning': '⚠️',
            'danger': '🚨',
            'fall': '🆘'
        };

        const titles = {
            'warning': 'ตรวจพบท่าทางเสี่ยง',
            'danger': 'อันตราย! ท่าทางเสี่ยงสูง',
            'fall': 'ตรวจพบการหกล้ม!'
        };

        this.popup.className = `alert-popup ${alertData.risk_level}`;
        this.popupIcon.textContent = icons[alertData.risk_level] || '⚠️';
        this.popupTitle.textContent = titles[alertData.risk_level] || alertData.message;
        this.popupMessage.textContent = alertData.message;
        this.popupTime.textContent = alertData.timestamp_display || new Date().toLocaleTimeString('th-TH');

        // แสดงรายละเอียด
        if (alertData.details && alertData.details.length > 0) {
            this.popupDetails.innerHTML = alertData.details
                .map(d => `<div>• ${d}</div>`)
                .join('');
        } else {
            this.popupDetails.innerHTML = '';
        }

        this.overlay.style.display = 'flex';
        this.isPopupVisible = true;
    }

    /**
     * ซ่อน popup
     */
    hidePopup() {
        if (this.overlay) {
            this.overlay.style.display = 'none';
        }
        this.isPopupVisible = false;
        document.body.classList.remove('fall-state');
    }

    /**
     * แสดง toast notification
     */
    showToast(alertData) {
        if (!this.toastContainer) return;

        const icons = {
            'warning': '⚠️',
            'danger': '🚨',
            'fall': '🆘'
        };

        const toast = document.createElement('div');
        toast.className = `toast ${alertData.risk_level}`;
        toast.innerHTML = `
            <span class="toast-icon">${icons[alertData.risk_level] || '⚠️'}</span>
            <div class="toast-content">
                <div class="toast-title">${alertData.message}</div>
                <div class="toast-message">${alertData.timestamp_display || ''}</div>
            </div>
            <button class="toast-close" onclick="this.closest('.toast').remove()">✕</button>
        `;

        this.toastContainer.appendChild(toast);

        // Auto-remove after 6 seconds
        setTimeout(() => {
            if (toast.parentNode) {
                toast.classList.add('removing');
                setTimeout(() => toast.remove(), 300);
            }
        }, 6000);

        // จำกัดจำนวน toast
        const toasts = this.toastContainer.querySelectorAll('.toast');
        if (toasts.length > 5) {
            toasts[0].remove();
        }
    }

    /**
     * เพิ่ม alert entry ในประวัติ
     */
    addAlertEntry(alertData) {
        if (!this.alertList) return;

        // ลบ empty message
        const emptyMsg = this.alertList.querySelector('.alert-empty');
        if (emptyMsg) {
            emptyMsg.remove();
        }

        const icons = {
            'warning': '⚠️',
            'danger': '🚨',
            'fall': '🆘'
        };

        const entry = document.createElement('div');
        entry.className = `alert-entry ${alertData.risk_level}`;
        entry.innerHTML = `
            <span class="alert-entry-icon">${icons[alertData.risk_level] || '⚠️'}</span>
            <div class="alert-entry-content">
                <div class="alert-entry-message">${alertData.message}</div>
                <div class="alert-entry-details">${(alertData.details || []).join(' | ') || '-'}</div>
            </div>
            <span class="alert-entry-time">${alertData.timestamp_display || new Date().toLocaleTimeString('th-TH')}</span>
        `;

        // เพิ่มที่บนสุด
        this.alertList.insertBefore(entry, this.alertList.firstChild);

        // จำกัดจำนวน
        const entries = this.alertList.querySelectorAll('.alert-entry');
        if (entries.length > this.maxAlerts) {
            entries[entries.length - 1].remove();
        }
    }

    /**
     * ล้างประวัติ alerts
     */
    clearAlerts() {
        if (this.alertList) {
            this.alertList.innerHTML = `
                <div class="alert-empty">
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3">
                        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                        <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                    </svg>
                    <p>ยังไม่มีการแจ้งเตือน</p>
                </div>
            `;
        }
    }
}

// Export global instance
window.alertSystem = new AlertSystem();
