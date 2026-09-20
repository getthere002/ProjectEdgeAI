// ======================================
// Chart Manager
// จัดการกราฟสถิติด้วย Chart.js
// ======================================

class ChartManager {
    constructor() {
        this.mainChart = null;
        this.currentChartType = 'hourly';
        this.chartCanvas = document.getElementById('mainChart');

        this._initTabs();
    }

    /**
     * ตั้งค่า Tab buttons
     */
    _initTabs() {
        const tabs = document.querySelectorAll('.chart-tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                tabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                this.currentChartType = tab.dataset.chart;
                this.loadChart();
            });
        });
    }

    /**
     * โหลดกราฟตามประเภทที่เลือก
     */
    async loadChart() {
        try {
            const stats = await fetch('/api/stats').then(r => r.json());

            if (this.mainChart) {
                this.mainChart.destroy();
            }

            switch (this.currentChartType) {
                case 'hourly':
                    this._createHourlyChart(stats);
                    break;
                case 'risk':
                    this._createRiskPieChart(stats);
                    break;
                case 'weekly':
                    this._createWeeklyChart(stats);
                    break;
            }

            // อัปเดตสถิติ summary
            this._updateStatsSummary(stats);

        } catch (e) {
            console.warn('[Charts] Failed to load stats:', e);
        }
    }

    /**
     * กราฟเส้นรายชั่วโมง
     */
    _createHourlyChart(stats) {
        const hourlyData = stats.hourly_stats || {};
        const labels = [];
        const data = [];

        for (let i = 0; i < 24; i++) {
            const hour = i.toString().padStart(2, '0');
            labels.push(`${hour}:00`);

            const hourStats = hourlyData[hour] || {};
            const total = Object.values(hourStats).reduce((sum, v) => sum + v, 0);
            data.push(total);
        }

        this.mainChart = new Chart(this.chartCanvas, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'เหตุการณ์',
                    data: data,
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#6366f1',
                    pointBorderColor: '#6366f1',
                    pointRadius: 3,
                    pointHoverRadius: 6
                }]
            },
            options: this._getChartOptions('จำนวนเหตุการณ์รายชั่วโมง (วันนี้)')
        });
    }

    /**
     * กราฟวงกลมสัดส่วนความเสี่ยง
     */
    _createRiskPieChart(stats) {
        const todayStats = stats.today_stats || {};
        const labels = [];
        const data = [];
        const colors = [];
        const colorMap = {
            'safe': { bg: '#00e676', label: 'ปลอดภัย' },
            'warning': { bg: '#ffab00', label: 'ระวัง' },
            'danger': { bg: '#ff1744', label: 'อันตราย' },
            'fall': { bg: '#d50000', label: 'หกล้ม' }
        };

        for (const [level, info] of Object.entries(colorMap)) {
            if (todayStats[level]) {
                labels.push(info.label);
                data.push(todayStats[level]);
                colors.push(info.bg);
            }
        }

        // ถ้าไม่มีข้อมูล
        if (data.length === 0) {
            labels.push('ไม่มีข้อมูล');
            data.push(1);
            colors.push('#334155');
        }

        this.mainChart = new Chart(this.chartCanvas, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors,
                    borderColor: '#111827',
                    borderWidth: 3,
                    hoverOffset: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            color: '#94a3b8',
                            font: { family: 'Inter', size: 11 },
                            padding: 12,
                            usePointStyle: true,
                            pointStyleWidth: 12
                        }
                    },
                    title: {
                        display: true,
                        text: 'สัดส่วนระดับความเสี่ยง (วันนี้)',
                        color: '#94a3b8',
                        font: { family: 'Inter', size: 12, weight: '500' },
                        padding: { bottom: 16 }
                    }
                },
                cutout: '65%'
            }
        });
    }

    /**
     * กราฟแท่งรายสัปดาห์
     */
    _createWeeklyChart(stats) {
        const weeklyData = stats.weekly_stats || {};
        const labels = [];
        const warningData = [];
        const dangerData = [];
        const fallData = [];

        // สร้างข้อมูล 7 วันย้อนหลัง
        for (let i = 6; i >= 0; i--) {
            const date = new Date();
            date.setDate(date.getDate() - i);
            const dateStr = date.toISOString().split('T')[0];
            const dayName = date.toLocaleDateString('th-TH', { weekday: 'short', day: 'numeric' });

            labels.push(dayName);
            const dayStats = weeklyData[dateStr] || {};
            warningData.push(dayStats['warning'] || 0);
            dangerData.push(dayStats['danger'] || 0);
            fallData.push(dayStats['fall'] || 0);
        }

        this.mainChart = new Chart(this.chartCanvas, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'ระวัง',
                        data: warningData,
                        backgroundColor: 'rgba(255, 171, 0, 0.7)',
                        borderRadius: 4,
                        barPercentage: 0.7
                    },
                    {
                        label: 'อันตราย',
                        data: dangerData,
                        backgroundColor: 'rgba(255, 23, 68, 0.7)',
                        borderRadius: 4,
                        barPercentage: 0.7
                    },
                    {
                        label: 'หกล้ม',
                        data: fallData,
                        backgroundColor: 'rgba(213, 0, 0, 0.7)',
                        borderRadius: 4,
                        barPercentage: 0.7
                    }
                ]
            },
            options: {
                ...this._getChartOptions('เหตุการณ์รายวัน (7 วันย้อนหลัง)'),
                scales: {
                    ...this._getChartOptions('').scales,
                    x: {
                        stacked: true,
                        grid: { display: false },
                        ticks: { color: '#64748b', font: { family: 'Inter', size: 10 } }
                    },
                    y: {
                        stacked: true,
                        grid: { color: 'rgba(255,255,255,0.04)' },
                        ticks: {
                            color: '#64748b',
                            font: { family: 'Inter', size: 10 },
                            stepSize: 1
                        }
                    }
                }
            }
        });
    }

    /**
     * ตัวเลือกกราฟมาตรฐาน
     */
    _getChartOptions(title) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    display: false
                },
                title: {
                    display: !!title,
                    text: title,
                    color: '#94a3b8',
                    font: { family: 'Inter', size: 12, weight: '500' },
                    padding: { bottom: 16 }
                },
                tooltip: {
                    backgroundColor: 'rgba(17, 24, 39, 0.95)',
                    titleFont: { family: 'Inter' },
                    bodyFont: { family: 'Inter' },
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1,
                    cornerRadius: 8,
                    padding: 10
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: {
                        color: '#64748b',
                        font: { family: 'Inter', size: 9 },
                        maxRotation: 0,
                        autoSkip: true,
                        maxTicksLimit: 12
                    }
                },
                y: {
                    grid: { color: 'rgba(255,255,255,0.04)' },
                    ticks: {
                        color: '#64748b',
                        font: { family: 'Inter', size: 10 },
                        stepSize: 1
                    },
                    beginAtZero: true
                }
            }
        };
    }

    /**
     * อัปเดตสถิติ summary
     */
    _updateStatsSummary(stats) {
        const totalEl = document.getElementById('statTotal');
        const criticalEl = document.getElementById('statCritical');
        const warningsEl = document.getElementById('statWarnings');

        if (totalEl) totalEl.textContent = stats.total_events || 0;
        if (criticalEl) criticalEl.textContent = stats.today_critical || 0;

        const todayStats = stats.today_stats || {};
        const warningCount = (todayStats['warning'] || 0) +
                            (todayStats['danger'] || 0) +
                            (todayStats['fall'] || 0);
        if (warningsEl) warningsEl.textContent = warningCount;
    }

    /**
     * Refresh กราฟ
     */
    refresh() {
        this.loadChart();
    }
}

// Export global instance
window.chartManager = new ChartManager();
