/* ====================================================================
   VoltWise Interactive Frontend Controller (static/app.js)
   ==================================================================== */

document.addEventListener("DOMContentLoaded", () => {
    // DOM Element References
    const liveTimeEl = document.getElementById("live-time");
    const statusGlowEl = document.getElementById("status-glow");
    const statusDescEl = document.getElementById("status-desc");
    const statusTipTextEl = document.getElementById("status-tip-text");
    
    const reserveRateValEl = document.getElementById("reserve-rate-val");
    const reserveGaugeFill = document.getElementById("reserve-gauge-fill");
    
    const loadValEl = document.getElementById("load-val");
    const loadGaugeFill = document.getElementById("load-gauge-fill");
    const supplyAbilityTextEl = document.getElementById("supply-ability-text");
    
    const operReserveRateEl = document.getElementById("oper-reserve-rate");
    const operReserveMwEl = document.getElementById("oper-reserve-mw");
    const forecastLoadEl = document.getElementById("forecast-load");
    
    const durationSlider = document.getElementById("duration-slider");
    const durationDisplay = document.getElementById("duration-display");
    const btnCalculate = document.getElementById("btn-calculate");
    const recommendationsList = document.getElementById("recommendations-list");
    
    // Tab Elements
    const tabBtns = document.querySelectorAll(".tab-btn");
    const tabContents = document.querySelectorAll(".tab-content");
    
    let trendChart = null;
    const CIRCUMFERENCE = 251.2; // 2 * PI * r (r=40)

    // Setup Local Time Clock
    function updateClock() {
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const date = String(now.getDate()).padStart(2, '0');
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        liveTimeEl.innerHTML = `<i class="fa-regular fa-clock"></i> ${year}-${month}-${date} ${hours}:${minutes} KST`;
    }
    updateClock();
    setInterval(updateClock, 30000);

    // Set Radial Gauge Fill Value
    function setGaugeValue(element, percent, maxVal = 100) {
        if (!element) return;
        const clampedPercent = Math.max(0, Math.min(maxVal, percent));
        const fraction = clampedPercent / maxVal;
        const offset = CIRCUMFERENCE * (1 - fraction);
        element.style.strokeDashoffset = offset;
    }

    // Fetch and Populate Live Grid Status
    async function loadLiveStatus() {
        try {
            const response = await fetch("/api/status/live");
            const res = await response.json();
            
            if (res.success) {
                const data = res.data;
                const rating = res.rating;
                
                // Update Badge and Status Description
                statusDescEl.textContent = rating.description;
                statusGlowEl.className = "live-glowing-indicator " + rating.code.toLowerCase();
                
                // Customize tips based on grid status
                if (rating.code === "GREEN") {
                    statusTipTextEl.textContent = "🔋 현재 전력 공급이 풍부하고 기저부하 비율이 높습니다. 대용량 학습, GPU 가동을 추천합니다.";
                } else if (rating.code === "YELLOW") {
                    statusTipTextEl.textContent = "⚡ 전력 수급 상황이 정상 수준입니다. 일반적인 가중치 학습을 수행하셔도 무방합니다.";
                } else if (rating.code === "ORANGE") {
                    statusTipTextEl.textContent = "⚠️ 일부 화석연료 첨두부하 발전기가 작동하기 시작했습니다. 긴급하지 않은 모델 가동은 연기를 권장합니다.";
                } else {
                    statusTipTextEl.textContent = "🚨 전력 공급 긴급 경보! 전력망 과부하 방지 및 탄소 저감을 위해 가동을 즉시 멈추고 심야로 지연하십시오.";
                }

                // Update Radial Gauge 1: Reserve Rate
                const reserveRate = data.supply_reserve_rate;
                reserveRateValEl.textContent = reserveRate.toFixed(1);
                setGaugeValue(reserveGaugeFill, reserveRate, 40); // 40%를 게이지 최대로 정의
                
                // Update Radial Gauge 2: Current Load in GW
                const currentLoadGw = data.current_load_mw / 1000.0;
                const supplyAbilityGw = data.supply_ability_mw / 1000.0;
                loadValEl.textContent = currentLoadGw.toFixed(1);
                supplyAbilityTextEl.textContent = `공급능력: ${supplyAbilityGw.toFixed(1)} GW`;
                setGaugeValue(loadGaugeFill, currentLoadGw, supplyAbilityGw);

                // Adjust Gauge Stroke color based on rating
                if (rating.code === "GREEN") {
                    reserveGaugeFill.style.stroke = "var(--color-green)";
                } else if (rating.code === "YELLOW") {
                    reserveGaugeFill.style.stroke = "var(--color-yellow)";
                } else if (rating.code === "ORANGE") {
                    reserveGaugeFill.style.stroke = "var(--color-orange)";
                } else {
                    reserveGaugeFill.style.stroke = "var(--color-red)";
                }

                // Populate Sub Numbers List
                operReserveRateEl.textContent = `${data.operational_reserve_rate.toFixed(2)} %`;
                operReserveMwEl.textContent = `${data.operational_reserve_mw.toLocaleString()} MW`;
                forecastLoadEl.textContent = `${data.forecast_load_mw.toLocaleString()} MW`;
            } else {
                statusDescEl.textContent = "API 연동 에러";
                statusTipTextEl.textContent = "에러: " + res.error;
            }
        } catch (error) {
            statusDescEl.textContent = "서버 연결 보류";
            statusTipTextEl.textContent = "백엔드 API 서버를 기동해주세요.";
            console.error("Error loading status:", error);
        }
    }

    // Fetch and Populate AI Recommendations
    async function loadRecommendations(hours) {
        recommendationsList.innerHTML = `
            <div class="loading-state">
                <i class="fa-solid fa-circle-notch fa-spin"></i> 최적의 친환경 시간대를 계산하고 있습니다...
            </div>
        `;
        
        try {
            const response = await fetch(`/api/recommend?duration_hours=${hours}`);
            const res = await response.json();
            
            if (res.success && res.recommendations.length > 0) {
                recommendationsList.innerHTML = "";
                res.recommendations.forEach((rec, index) => {
                    const rankClass = `rank-${index + 1}`;
                    const gradeClass = rec.status_code === "GREEN" ? "grade-green" : "grade-yellow";
                    
                    const recHtml = `
                        <div class="rec-item ${rankClass}">
                            <div class="rec-rank">${index + 1}</div>
                            <div class="rec-details">
                                <span class="rec-time">${rec.time_label}</span>
                                <div class="rec-stats">
                                    <span>평균 예비율: ${rec.avg_reserve_rate}%</span>
                                    <span class="stat-eco"><i class="fa-solid fa-cloud-arrow-down"></i> 탄소 절감: ${rec.carbon_saving_pct}%</span>
                                    <span class="stat-cost"><i class="fa-solid fa-coins"></i> 요금 절감: ${rec.cost_discount_pct}%</span>
                                </div>
                            </div>
                            <div class="rec-score-wrapper">
                                <div class="rec-score">${rec.esg_score}<span> / 100</span></div>
                                <span class="rec-grade ${gradeClass}">${rec.status_desc.split(" ")[0]}</span>
                            </div>
                        </div>
                    `;
                    recommendationsList.insertAdjacentHTML("beforeend", recHtml);
                });
            } else {
                recommendationsList.innerHTML = `<div class="loading-state">추천을 불러오지 못했습니다.</div>`;
            }
        } catch (error) {
            recommendationsList.innerHTML = `<div class="loading-state">서버 통신 실패</div>`;
            console.error("Error loading recommendations:", error);
        }
    }

    // Fetch and Render 24-Hour Trend Chart
    async function renderChart() {
        try {
            const response = await fetch("/api/status/history");
            const res = await response.json();
            
            if (res.success) {
                const labels = res.history.map(item => item.hour);
                const reserveData = res.history.map(item => item.reserve_rate);
                const loadData = res.history.map(item => item.current_load_gw);
                const carbonData = res.history.map(item => item.carbon_saving_pct);
                
                const ctx = document.getElementById("gridTrendChart").getContext("2d");
                
                if (trendChart) {
                    trendChart.destroy();
                }
                
                trendChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [
                            {
                                label: '전력 예비율 (%)',
                                data: reserveData,
                                borderColor: '#10b981',
                                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                                borderWidth: 3,
                                fill: true,
                                tension: 0.4,
                                yAxisID: 'y'
                            },
                            {
                                label: '실시간 부하 (GW)',
                                data: loadData,
                                borderColor: '#3b82f6',
                                backgroundColor: 'rgba(59, 130, 246, 0.05)',
                                borderWidth: 2,
                                borderDash: [4, 4],
                                fill: false,
                                tension: 0.4,
                                yAxisID: 'y1'
                            },
                            {
                                label: '탄소 절감지수 (%)',
                                data: carbonData,
                                borderColor: '#8b5cf6',
                                backgroundColor: 'rgba(139, 92, 246, 0.1)',
                                borderWidth: 1.5,
                                fill: false,
                                tension: 0.3,
                                yAxisID: 'y'
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                labels: {
                                    color: '#9ca3af',
                                    font: { family: 'Outfit, sans-serif', size: 11 }
                                }
                            },
                            tooltip: {
                                backgroundColor: '#141625',
                                titleColor: '#fff',
                                bodyColor: '#cbd5e1',
                                borderColor: 'rgba(255,255,255,0.08)',
                                borderWidth: 1
                            }
                        },
                        scales: {
                            x: {
                                grid: { color: 'rgba(255,255,255,0.03)' },
                                ticks: { color: '#6b7280', font: { family: 'Outfit' } }
                            },
                            y: {
                                position: 'left',
                                title: { display: true, text: '예비율 / 절감율 (%)', color: '#9ca3af' },
                                grid: { color: 'rgba(255,255,255,0.03)' },
                                ticks: { color: '#9ca3af' }
                            },
                            y1: {
                                position: 'right',
                                title: { display: true, text: '부하량 (GW)', color: '#9ca3af' },
                                grid: { drawOnChartArea: false },
                                ticks: { color: '#9ca3af' }
                            }
                        }
                    }
                });
            }
        } catch (error) {
            console.error("Error drawing trend chart:", error);
        }
    }

    // Input Slider Event Listener
    durationSlider.addEventListener("input", (e) => {
        durationDisplay.textContent = e.target.value;
    });

    btnCalculate.addEventListener("click", () => {
        const hours = parseInt(durationSlider.value, 10);
        loadRecommendations(hours);
    });

    // Code Tab Switchers
    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            tabBtns.forEach(b => b.classList.remove("active"));
            tabContents.forEach(c => c.classList.remove("active"));
            
            btn.classList.add("active");
            const tabId = btn.getAttribute("data-tab");
            document.getElementById(tabId).classList.add("active");
        });
    });

    // End-to-End Initial Loader
    async function initDashboard() {
        await loadLiveStatus();
        const duration = parseInt(durationSlider.value, 10);
        await loadRecommendations(duration);
        await renderChart();
    }

    initDashboard();

    // Auto Refresh every 5 minutes (300,000 ms)
    setInterval(() => {
        console.log("VoltWise Dashboard Auto-Refreshing live data...");
        loadLiveStatus();
        renderChart();
    }, 300000);
});

// Copy Code Clipboard Global Function
window.copyCode = function(button) {
    const codeBlock = button.parentElement.querySelector("code");
    if (!codeBlock) return;
    
    navigator.clipboard.writeText(codeBlock.innerText).then(() => {
        const originalText = button.innerHTML;
        button.innerHTML = `<i class="fa-solid fa-check"></i> Copied!`;
        button.style.background = "rgba(16, 185, 129, 0.15)";
        button.style.color = "var(--color-green)";
        
        setTimeout(() => {
            button.innerHTML = originalText;
            button.style.background = "";
            button.style.color = "";
        }, 2000);
    }).catch(err => {
        console.error("Failed to copy text: ", err);
    });
};
