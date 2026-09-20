// ======================================
// WebSocket Connection Manager
// จัดการการเชื่อมต่อ WebSocket กับ Backend
// ======================================

class WebSocketManager {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 50;
        this.reconnectDelay = 2000;
        this.onDataCallback = null;
        this.onAlertCallback = null;
        this.onConnectionChange = null;
    }

    /**
     * เชื่อมต่อ WebSocket
     */
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        console.log(`[WS] กำลังเชื่อมต่อ: ${wsUrl}`);

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                console.log('[WS] ✅ เชื่อมต่อสำเร็จ');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                if (this.onConnectionChange) {
                    this.onConnectionChange(true);
                }
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this._handleMessage(data);
                } catch (e) {
                    console.warn('[WS] Parse error:', e);
                }
            };

            this.ws.onclose = (event) => {
                console.log(`[WS] ❌ ตัดการเชื่อมต่อ (code: ${event.code})`);
                this.isConnected = false;
                if (this.onConnectionChange) {
                    this.onConnectionChange(false);
                }
                this._scheduleReconnect();
            };

            this.ws.onerror = (error) => {
                console.error('[WS] Error:', error);
            };

        } catch (e) {
            console.error('[WS] Connection error:', e);
            this._scheduleReconnect();
        }
    }

    /**
     * จัดการ message ที่ได้รับ
     */
    _handleMessage(data) {
        if (data.type === 'update') {
            if (this.onDataCallback) {
                this.onDataCallback(data);
            }
            // ส่ง alert แยก
            if (data.alert && this.onAlertCallback) {
                this.onAlertCallback(data.alert);
            }
        } else if (data.type === 'config_updated' || data.type === 'info') {
            console.log(`[WS] ${data.message}`);
        }
    }

    /**
     * ตั้งเวลา reconnect
     */
    _scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('[WS] ⛔ เกินจำนวนครั้งที่พยายามเชื่อมต่อ');
            return;
        }

        this.reconnectAttempts++;
        const delay = Math.min(this.reconnectDelay * this.reconnectAttempts, 10000);
        console.log(`[WS] 🔄 พยายามเชื่อมต่อใหม่ครั้งที่ ${this.reconnectAttempts} ใน ${delay}ms`);

        setTimeout(() => {
            this.connect();
        }, delay);
    }

    /**
     * ส่ง message ไปยัง server
     */
    send(data) {
        if (this.isConnected && this.ws) {
            this.ws.send(JSON.stringify(data));
        }
    }

    /**
     * ส่งคำสั่ง acknowledge alert
     */
    acknowledgeAlert(alertId) {
        this.send({
            type: 'acknowledge_alert',
            alert_id: alertId
        });
    }

    /**
     * ส่งคำสั่งอัปเดต thresholds
     */
    updateThresholds(thresholds) {
        this.send({
            type: 'update_thresholds',
            thresholds: thresholds
        });
    }

    /**
     * ส่งคำสั่ง reset analyzer
     */
    resetAnalyzer() {
        this.send({
            type: 'reset_analyzer'
        });
    }

    /**
     * ตัดการเชื่อมต่อ
     */
    disconnect() {
        if (this.ws) {
            this.ws.close();
        }
    }
}

// Export global instance
window.wsManager = new WebSocketManager();
