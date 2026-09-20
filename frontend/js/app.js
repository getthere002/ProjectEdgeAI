// ======================================
// Main Application Controller
// จัดการ UI state ทั้งหมด
// ======================================

(function () {
    'use strict';

    // === DOM Elements ===
    const elements = {
        // Header
        connectionStatus: document.getElementById('connectionStatus'),
        headerClock: document.getElementById('headerClock'),
        headerDate: document.getElementById('headerDate'),

        // Video
        fpsBadge: document.getElementById('fpsBadge'),
        personText: document.getElementById('personText'),

        // Risk Meter
        riskCircle: document.getElementById('riskCircle'),
        riskRing: document.getElementById('riskRing'),
        riskLevelText: document.getElementById('riskLevelText'),
        riskLevelThai: document.getElementById('riskLevelThai'),
        riskFactors: document.getElementById('riskFactors'),

        // Metrics
        bodyAngleValue: document.getElementById('bodyAngleValue'),
        bodyAngleBar: document.getElementById('bodyAngleBar'),
        velocityValue: document.getElementById('velocityValue'),
        velocityBar: document.getElementById('velocityBar'),
        kneeLeftValue: document.getElementById('kneeLeftValue'),
        kneeLeftBar: document.getElementById('kneeLeftBar'),
        kneeRightValue: document.getElementById('kneeRightValue'),
        kneeRightBar: document.getElementById('kneeRightBar'),
        swayValue: document.getElementById('swayValue'),
        swayBar: document.getElementById('swayBar'),
        stanceValue: document.getElementById('stanceValue'),
        stanceBar: document.getElementById('stanceBar'),

        // Stats
        statUptime: document.getElementById('statUptime'),

        // Buttons
        btnClearAlerts: document.getElementById('btnClearAlerts'),
        btnSaveSettings: document.getElementById('btnSaveSettings'),
    };

    // === State ===
    const appStartTime = Date.now();
    let lastRiskLevel = 'safe';
    let chartRefreshInterval = null;

    // === Risk Level Config ===
    const riskConfig = {
        safe: {
            text: 'SAFE',
            thai: 'ปลอดภัย',
            ringOffset: 534,    // full circle hidden
            progressPercent: 0.15
        },
        warning: {
            text: 'WARNING',
            thai: 'ระวัง',
            ringOffset: 400,
            progressPercent: 0.5
        },
        danger: {
            text: 'DANGER',
            thai: 'อันตราย',
            ringOffset: 200,
            progressPercent: 0.75
        },
        fall: {
            text: 'FALL!',
            thai: 'หกล้ม!',
            ringOffset: 40,
            progressPercent: 1.0
        }
    };

    // ======================================
    // Clock & Date
    // ======================================
    function updateClock() {
        const now = new Date();
        if (elements.headerClock) {
            elements.headerClock.textContent = now.toLocaleTimeString('th-TH', {
                hour: '2-digit', minute: '2-digit', second: '2-digit'
            });
        }
        if (elements.headerDate) {
            elements.headerDate.textContent = now.toLocaleDateString('th-TH', {
                year: 'numeric', month: 'long', day: 'numeric', weekday: 'long'
            });
        }
    }

    function updateUptime() {
        const elapsed = Math.floor((Date.now() - appStartTime) / 1000);
        const hours = Math.floor(elapsed / 3600);
        const minutes = Math.floor((elapsed % 3600) / 60);

        if (elements.statUptime) {
            if (hours > 0) {
                elements.statUptime.textContent = `${hours}h ${minutes}m`;
            } else {
                elements.statUptime.textContent = `${minutes}m`;
            }
        }
    }

    // ======================================
    // Connection Status
    // ======================================
    function updateConnectionStatus(connected) {
        if (!elements.connectionStatus) return;

        if (connected) {
            elements.connectionStatus.className = 'status-badge connected';
            elements.connectionStatus.querySelector('.status-text').textContent = 'เชื่อมต่อแล้ว';
        } else {
            elements.connectionStatus.className = 'status-badge disconnected';
            elements.connectionStatus.querySelector('.status-text').textContent = 'ขาดการเชื่อมต่อ';
        }
    }

    // ======================================
    // Risk Meter Update
    // ======================================
    function updateRiskMeter(riskLevel) {
        const config = riskConfig[riskLevel] || riskConfig.safe;

        if (elements.riskCircle) {
            elements.riskCircle.className = `risk-circle ${riskLevel}`;
        }

        if (elements.riskRing) {
            const circumference = 534;
            const offset = circumference * (1 - config.progressPercent);
            elements.riskRing.style.strokeDashoffset = offset;
        }

        if (elements.riskLevelText) {
            elements.riskLevelText.textContent = config.text;
        }

        if (elements.riskLevelThai) {
            elements.riskLevelThai.textContent = config.thai;
        }

        // Visual feedback on risk card
        const riskCard = document.getElementById('riskCard');
        if (riskCard) {
            riskCard.className = `card card-risk`;
            if (riskLevel === 'danger' || riskLevel === 'fall') {
                riskCard.style.borderColor = `var(--${riskLevel})`;
                riskCard.style.boxShadow = `0 0 20px var(--${riskLevel}-glow)`;
            } else if (riskLevel === 'warning') {
                riskCard.style.borderColor = `var(--warning)`;
                riskCard.style.boxShadow = '';
            } else {
                riskCard.style.borderColor = '';
                riskCard.style.boxShadow = '';
            }
        }

        lastRiskLevel = riskLevel;
    }

    // ======================================
    // Risk Factors Update
    // ======================================
    function updateRiskFactors(factors) {
        if (!elements.riskFactors) return;

        if (!factors || factors.length === 0) {
            elements.riskFactors.innerHTML = '<div class="factor-empty">ไม่พบปัจจัยเสี่ยง</div>';
            return;
        }

        const html = factors.map(f => {
            if (!f) return '';
            const level = f.level || 'warning';
            return `<div class="factor-item ${level}">
                <span>•</span>
                <span>${f.message || ''}</span>
            </div>`;
        }).join('');

        elements.riskFactors.innerHTML = html;
    }

    // ======================================
    // Body Metrics Update
    // ======================================
    function updateMetrics(metrics) {
        if (!metrics) return;

        // Body Angle
        if (metrics.body_angle !== undefined && metrics.body_angle !== null) {
            const angle = metrics.body_angle;
            updateMetricItem(
                elements.bodyAngleValue, elements.bodyAngleBar,
                `${angle.toFixed(1)}°`,
                Math.min(angle / 90, 1) * 100,
                getBarClass(angle, 30, 45, 60)
            );
        }

        // Velocity
        if (metrics.velocity !== undefined && metrics.velocity !== null) {
            const vel = metrics.velocity;
            updateMetricItem(
                elements.velocityValue, elements.velocityBar,
                vel.toFixed(4),
                Math.min(vel / 0.1, 1) * 100,
                getBarClass(vel, 0.02, 0.04, 0.08)
            );
        }

        // Left Knee Angle
        if (metrics.left_knee_angle !== undefined && metrics.left_knee_angle !== null) {
            const knee = metrics.left_knee_angle;
            updateMetricItem(
                elements.kneeLeftValue, elements.kneeLeftBar,
                `${knee.toFixed(1)}°`,
                Math.min(knee / 180, 1) * 100,
                getBarClassInverse(knee, 120, 90)
            );
        }

        // Right Knee Angle
        if (metrics.right_knee_angle !== undefined && metrics.right_knee_angle !== null) {
            const knee = metrics.right_knee_angle;
            updateMetricItem(
                elements.kneeRightValue, elements.kneeRightBar,
                `${knee.toFixed(1)}°`,
                Math.min(knee / 180, 1) * 100,
                getBarClassInverse(knee, 120, 90)
            );
        }

        // Sway
        if (metrics.sway !== undefined && metrics.sway !== null) {
            const sway = metrics.sway;
            updateMetricItem(
                elements.swayValue, elements.swayBar,
                sway.toFixed(4),
                Math.min(sway / 0.05, 1) * 100,
                getBarClass(sway, 0.015, 0.03, 0.05)
            );
        }

        // Stance Width
        if (metrics.stance_width !== undefined && metrics.stance_width !== null) {
            const stance = metrics.stance_width;
            updateMetricItem(
                elements.stanceValue, elements.stanceBar,
                stance.toFixed(4),
                Math.min(stance / 0.3, 1) * 100,
                stance < 0.05 ? 'warning' : ''
            );
        }
    }

    function updateMetricItem(valueEl, barEl, text, percent, barClass) {
        if (valueEl) valueEl.textContent = text;
        if (barEl) {
            barEl.style.width = `${percent}%`;
            barEl.className = `metric-bar ${barClass}`;
        }
    }

    function getBarClass(value, warnThreshold, dangerThreshold, fallThreshold) {
        if (fallThreshold && value >= fallThreshold) return 'fall';
        if (value >= dangerThreshold) return 'danger';
        if (value >= warnThreshold) return 'warning';
        return '';
    }

    function getBarClassInverse(value, warnThreshold, dangerThreshold) {
        if (value < dangerThreshold) return 'danger';
        if (value < warnThreshold) return 'warning';
        return '';
    }

    // ======================================
    // Person Detection Status
    // ======================================
    function updatePersonStatus(detected) {
        if (elements.personText) {
            elements.personText.textContent = detected ? 'ตรวจพบบุคคล' : 'ไม่พบบุคคลในภาพ';
        }
    }

    // ======================================
    // FPS Display
    // ======================================
    function updateFPS(fps) {
        if (elements.fpsBadge) {
            elements.fpsBadge.textContent = `${fps} FPS`;
        }
    }

    // ======================================
    // WebSocket Data Handler
    // ======================================
    function handleData(data) {
        // อัปเดต Risk Meter
        updateRiskMeter(data.risk_level || 'safe');

        // อัปเดต Risk Factors
        updateRiskFactors(data.factors);

        // อัปเดต Body Metrics
        updateMetrics(data.metrics);

        // อัปเดต Person Detection
        updatePersonStatus(data.person_detected);

        // อัปเดต FPS
        updateFPS(data.fps || 0);

        // จัดการ fall state
        if (data.risk_level === 'fall') {
            document.body.classList.add('fall-state');
        } else {
            document.body.classList.remove('fall-state');
        }
    }

    // ======================================
    // Alert Handler
    // ======================================
    function handleAlert(alertData) {
        if (window.alertSystem) {
            window.alertSystem.showAlert(alertData);
        }
    }

    // ======================================
    // Settings
    // ======================================
    function saveSettings() {
        const thresholds = {
            body_angle_warning: parseFloat(document.getElementById('threshAngleWarn')?.value || 30),
            body_angle_danger: parseFloat(document.getElementById('threshAngleDanger')?.value || 45),
            body_angle_fall: parseFloat(document.getElementById('threshAngleFall')?.value || 60),
            velocity_warning: parseFloat(document.getElementById('threshVelWarn')?.value || 0.02),
            velocity_danger: parseFloat(document.getElementById('threshVelDanger')?.value || 0.04),
            velocity_fall: parseFloat(document.getElementById('threshVelFall')?.value || 0.08),
            knee_angle_warning: parseFloat(document.getElementById('threshKneeWarn')?.value || 120),
            knee_angle_danger: parseFloat(document.getElementById('threshKneeDanger')?.value || 90),
            stance_width_warning: parseFloat(document.getElementById('threshStance')?.value || 0.05),
            sway_warning: parseFloat(document.getElementById('threshSwayWarn')?.value || 0.015),
        };

        // ส่งผ่าน REST API
        fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ thresholds })
        })
            .then(r => r.json())
            .then(data => {
                // แสดง toast สำเร็จ
                if (window.alertSystem) {
                    window.alertSystem.showToast({
                        risk_level: 'info',
                        message: '✅ บันทึกการตั้งค่าสำเร็จ',
                        timestamp_display: new Date().toLocaleTimeString('th-TH')
                    });
                }
            })
            .catch(e => {
                console.error('Failed to save settings:', e);
            });

        // ส่งผ่าน WebSocket ด้วย
        if (window.wsManager) {
            window.wsManager.updateThresholds(thresholds);
        }
    }

    // ======================================
    // Load Historical Alerts
    // ======================================
    async function loadHistoricalAlerts() {
        try {
            const alerts = await fetch('/api/alerts').then(r => r.json());
            if (alerts && alerts.length > 0 && window.alertSystem) {
                alerts.reverse().forEach(alert => {
                    window.alertSystem.addAlertEntry({
                        risk_level: alert.risk_level,
                        message: alert.message,
                        details: [],
                        timestamp_display: new Date(alert.timestamp).toLocaleTimeString('th-TH')
                    });
                });
            }
        } catch (e) {
            console.warn('Failed to load historical alerts:', e);
        }
    }

    // ======================================
    // Initialize Application
    // ======================================
    function init() {
        console.log('[App] 🚀 Initializing Fall Risk Detection Dashboard...');

        // นาฬิกา
        updateClock();
        setInterval(updateClock, 1000);
        setInterval(updateUptime, 60000);

        // WebSocket
        if (window.wsManager) {
            window.wsManager.onDataCallback = handleData;
            window.wsManager.onAlertCallback = handleAlert;
            window.wsManager.onConnectionChange = updateConnectionStatus;
            window.wsManager.connect();
        }

        // Charts - โหลดครั้งแรก
        setTimeout(() => {
            if (window.chartManager) {
                window.chartManager.loadChart();
            }
        }, 2000);

        // Refresh charts ทุก 30 วินาที
        chartRefreshInterval = setInterval(() => {
            if (window.chartManager) {
                window.chartManager.refresh();
            }
        }, 30000);

        // โหลดประวัติ alerts
        loadHistoricalAlerts();

        // Event Listeners
        if (elements.btnClearAlerts) {
            elements.btnClearAlerts.addEventListener('click', () => {
                if (window.alertSystem) {
                    window.alertSystem.clearAlerts();
                }
            });
        }

        if (elements.btnSaveSettings) {
            elements.btnSaveSettings.addEventListener('click', saveSettings);
        }

        // Initial state
        updateConnectionStatus(false);
        updateRiskMeter('safe');
        updateUptime();

        console.log('[App] ✅ Dashboard initialized');
    }

    // Start the app
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
