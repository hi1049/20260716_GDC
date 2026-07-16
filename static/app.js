/* ====================================================================
   GridPulse Carbon-Aware UI Controller (static/app.js)
   ==================================================================== */

document.addEventListener("DOMContentLoaded", () => {
    // DOM Element References
    const liveTimeEl = document.getElementById("live-time");
    const modeBadgeEl = document.getElementById("mode-badge");
    const btnForceTick = document.getElementById("btn-force-tick");
    
    // Status column elements
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
    
    // Generation Mix & Carbon column elements
    const ciValueEl = document.getElementById("ci-value");
    const ciBadgeEl = document.getElementById("ci-badge-el");
    const ciBadgeTextEl = document.getElementById("ci-badge-text");
    const genMixListEl = document.getElementById("gen-mix-list-el");
    
    // Gemini Advisor column elements
    const aiBadgeEl = document.getElementById("ai-recommendation-badge");
    const aiSavingEl = document.getElementById("ai-estimated-saving");
    const aiDeferHintEl = document.getElementById("ai-defer-hint");
    const aiReasoningEl = document.getElementById("ai-reasoning-text");
    const aiActionsListEl = document.getElementById("ai-actions-list");

    // Constants
    const CIRCUMFERENCE = 251.2; // 2 * PI * r (r=40)
    
    // Chart References
    let donutChart = null;
    let trendChart = null;

    // 1. Clock Setup
    function updateClock() {
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const date = String(now.getDate()).padStart(2, '0');
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        const seconds = String(now.getSeconds()).padStart(2, '0');
        liveTimeEl.innerHTML = `<i class="fa-regular fa-clock"></i> ${year}-${month}-${date} ${hours}:${minutes}:${seconds} KST`;
    }
    updateClock();
    setInterval(updateClock, 1000);

    // Helper: Stroke Gauge Filler
    function setGaugeValue(element, percent, maxVal = 100) {
        if (!element) return;
        const clampedPercent = Math.max(0, Math.min(maxVal, percent));
        const fraction = clampedPercent / maxVal;
        const offset = CIRCUMFERENCE * (1 - fraction);
        element.style.strokeDashoffset = offset;
    }

    // 2. Generation Mix Donut Chart Initialization
    function initDonutChart(dataValues) {
        const ctx = document.getElementById("generationMixChart").getContext("2d");
        donutChart = new Chart(ctx, {
            type: "doughnut",
            data: {
                labels: ["수력", "유류", "유연탄", "원자력", "양수", "가스 LNG", "국내탄", "신재생", "태양광"],
                datasets: [{
                    data: dataValues,
                    backgroundColor: [
                        "#0ea5e9", // 수력: Blue
                        "#ef4444", // 유류: Red
                        "#4b5563", // 유연탄: Charcoal/Gray
                        "#6366f1", // 원자력: Indigo
                        "#3b82f6", // 양수: Light Blue
                        "#38bdf8", // 가스 LNG: Sky Blue
                        "#6b7280", // 국내탄: Gray
                        "#10b981", // 신재생: Green
                        "#f59e0b"  // 태양광: Amber/Yellow
                    ],
                    borderWidth: 1,
                    borderColor: "rgba(255,255,255,0.05)"
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `${context.label}: ${context.raw.toLocaleString()} MW`;
                            }
                        }
                    }
                },
                cutout: "70%"
            }
        });
    }

    function updateDonutChart(dataValues) {
        if (!donutChart) {
            initDonutChart(dataValues);
        } else {
            donutChart.data.datasets[0].data = dataValues;
            donutChart.update();
        }
    }

    // 3. Grid Historical Activity Trend Line Chart
    function initTrendChart(historyRows, activeHour = null) {
        const ctx = document.getElementById("gridTrendChart").getContext("2d");
        
        // Extract dimensions from history rows
        const labels = historyRows.map(r => `${String(r.hour).padStart(2, '0')}:00`);
        const reserveRates = historyRows.map(r => parseFloat(r.supply_reserve_rate));
        const loadGws = historyRows.map(r => parseFloat(r.current_load_mw) / 1000.0);
        
        // Let's pre-calculate carbon intensity for each row in history for visual consistency
        const emissionFactors = [24, 700, 820, 12, 24, 490, 820, 38, 45];
        const carbonIntensities = historyRows.map(r => {
            const mix = [
                parseFloat(r.fuelPwr1), parseFloat(r.fuelPwr2), parseFloat(r.fuelPwr3),
                parseFloat(r.fuelPwr4), parseFloat(r.fuelPwr5), parseFloat(r.fuelPwr6),
                parseFloat(r.fuelPwr7), parseFloat(r.fuelPwr8), parseFloat(r.fuelPwr9)
            ];
            const sumGen = mix.reduce((a, b) => a + b, 0);
            const sumCo2 = mix.map((val, idx) => val * emissionFactors[idx]).reduce((a, b) => a + b, 0);
            return sumGen > 0 ? sumCo2 / sumGen : 450.0;
        });

        // Set up active glowing point radius
        const pointRadii_reserve = reserveRates.map((_, i) => (activeHour !== null && i === activeHour) ? 9 : 2);
        const pointHoverRadii_reserve = reserveRates.map((_, i) => (activeHour !== null && i === activeHour) ? 12 : 5);
        
        const pointRadii_load = loadGws.map((_, i) => (activeHour !== null && i === activeHour) ? 9 : 2);
        const pointRadii_ci = carbonIntensities.map((_, i) => (activeHour !== null && i === activeHour) ? 9 : 2);

        trendChart = new Chart(ctx, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "공급 예비율 (%)",
                        data: reserveRates,
                        borderColor: "#3b82f6",
                        backgroundColor: "rgba(59, 130, 246, 0.05)",
                        borderWidth: 2.5,
                        yAxisID: "y-percent",
                        pointRadius: pointRadii_reserve,
                        pointHoverRadius: pointHoverRadii_reserve,
                        pointBackgroundColor: reserveRates.map((_, i) => (activeHour !== null && i === activeHour) ? "#3b82f6" : "transparent"),
                        pointBorderColor: reserveRates.map((_, i) => (activeHour !== null && i === activeHour) ? "#fff" : "transparent"),
                        pointBorderWidth: reserveRates.map((_, i) => (activeHour !== null && i === activeHour) ? 3 : 1),
                        tension: 0.35,
                        fill: true
                    },
                    {
                        label: "전력 부하량 (GW)",
                        data: loadGws,
                        borderColor: "#8b5cf6",
                        backgroundColor: "transparent",
                        borderWidth: 2,
                        yAxisID: "y-gw-ci",
                        pointRadius: pointRadii_load,
                        pointBackgroundColor: loadGws.map((_, i) => (activeHour !== null && i === activeHour) ? "#8b5cf6" : "transparent"),
                        pointBorderColor: loadGws.map((_, i) => (activeHour !== null && i === activeHour) ? "#fff" : "transparent"),
                        tension: 0.35
                    },
                    {
                        label: "탄소집약도 (gCO₂/kWh)",
                        data: carbonIntensities,
                        borderColor: "#10b981",
                        backgroundColor: "transparent",
                        borderWidth: 2,
                        yAxisID: "y-gw-ci",
                        pointRadius: pointRadii_ci,
                        pointBackgroundColor: carbonIntensities.map((_, i) => (activeHour !== null && i === activeHour) ? "#10b981" : "transparent"),
                        pointBorderColor: carbonIntensities.map((_, i) => (activeHour !== null && i === activeHour) ? "#fff" : "transparent"),
                        tension: 0.35
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "top",
                        labels: {
                            color: "#9ca3af",
                            font: { family: "Outfit", size: 11 }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: "rgba(255,255,255,0.03)" },
                        ticks: { color: "#9ca3af", font: { family: "Outfit" } }
                    },
                    "y-percent": {
                        type: "linear",
                        position: "left",
                        title: { display: true, text: "예비율 (%)", color: "#3b82f6" },
                        grid: { color: "rgba(255,255,255,0.03)" },
                        ticks: { color: "#9ca3af" },
                        min: 0,
                        max: 80
                    },
                    "y-gw-ci": {
                        type: "linear",
                        position: "right",
                        title: { display: true, text: "부하 (GW) / 탄소집약도", color: "#10b981" },
                        grid: { drawOnChartArea: false },
                        ticks: { color: "#9ca3af" },
                        min: 0,
                        max: 950
                    }
                }
            }
        });
    }

    function updateTrendChart(historyRows, activeHour) {
        if (!trendChart) {
            initTrendChart(historyRows, activeHour);
        } else {
            // Re-map datasets with new active hour indicator
            const reserveRates = historyRows.map(r => parseFloat(r.supply_reserve_rate));
            const loadGws = historyRows.map(r => parseFloat(r.current_load_mw) / 1000.0);
            const emissionFactors = [24, 700, 820, 12, 24, 490, 820, 38, 45];
            const carbonIntensities = historyRows.map(r => {
                const mix = [
                    parseFloat(r.fuelPwr1), parseFloat(r.fuelPwr2), parseFloat(r.fuelPwr3),
                    parseFloat(r.fuelPwr4), parseFloat(r.fuelPwr5), parseFloat(r.fuelPwr6),
                    parseFloat(r.fuelPwr7), parseFloat(r.fuelPwr8), parseFloat(r.fuelPwr9)
                ];
                const sumGen = mix.reduce((a, b) => a + b, 0);
                const sumCo2 = mix.map((val, idx) => val * emissionFactors[idx]).reduce((a, b) => a + b, 0);
                return sumGen > 0 ? sumCo2 / sumGen : 450.0;
            });

            trendChart.data.datasets[0].pointRadius = reserveRates.map((_, i) => (i === activeHour) ? 9 : 2);
            trendChart.data.datasets[0].pointBackgroundColor = reserveRates.map((_, i) => (i === activeHour) ? "#3b82f6" : "transparent");
            trendChart.data.datasets[0].pointBorderColor = reserveRates.map((_, i) => (i === activeHour) ? "#fff" : "transparent");
            trendChart.data.datasets[0].pointBorderWidth = reserveRates.map((_, i) => (i === activeHour) ? 3 : 1);

            trendChart.data.datasets[1].pointRadius = loadGws.map((_, i) => (i === activeHour) ? 9 : 2);
            trendChart.data.datasets[1].pointBackgroundColor = loadGws.map((_, i) => (i === activeHour) ? "#8b5cf6" : "transparent");
            trendChart.data.datasets[1].pointBorderColor = loadGws.map((_, i) => (i === activeHour) ? "#fff" : "transparent");

            trendChart.data.datasets[2].pointRadius = carbonIntensities.map((_, i) => (i === activeHour) ? 9 : 2);
            trendChart.data.datasets[2].pointBackgroundColor = carbonIntensities.map((_, i) => (i === activeHour) ? "#10b981" : "transparent");
            trendChart.data.datasets[2].pointBorderColor = carbonIntensities.map((_, i) => (i === activeHour) ? "#fff" : "transparent");

            trendChart.update();
        }
    }

    // 4. Update Carbon Intensity Rating & badges
    function updateCarbonIntensityUI(ci) {
        ciValueEl.textContent = ci.toFixed(1);
        
        ciBadgeEl.className = "ci-badge"; // Reset classes
        if (ci <= 380) {
            ciBadgeEl.classList.add("green");
            ciBadgeTextEl.textContent = "탄소 우수 (ECO)";
        } else if (ci <= 480) {
            ciBadgeEl.classList.add("yellow");
            ciBadgeTextEl.textContent = "보통";
        } else {
            ciBadgeEl.classList.add("red");
            ciBadgeTextEl.textContent = "탄소 고위험 (HEAVY)";
        }
    }

    // 5. Update Fuel Mix Legend List
    function updateFuelMixLegendUI(mix) {
        genMixListEl.innerHTML = "";
        
        const totalGen = Object.values(mix).reduce((a, b) => a + b, 0) || 1;
        const namesMapping = {
            hydro: "수력",
            oil: "유류",
            coal_bituminous: "유연탄",
            nuclear: "원자력",
            pumped: "양수",
            gas_lng: "가스 LNG",
            coal_domestic: "국내탄",
            renewable: "신재생",
            solar: "태양광"
        };
        const colorsMapping = {
            hydro: "#0ea5e9",
            oil: "#ef4444",
            coal_bituminous: "#4b5563",
            nuclear: "#6366f1",
            pumped: "#3b82f6",
            gas_lng: "#38bdf8",
            coal_domestic: "#6b7280",
            renewable: "#10b981",
            solar: "#f59e0b"
        };

        Object.entries(mix).forEach(([key, val]) => {
            const pct = (val / totalGen * 100).toFixed(1);
            const legendItem = document.createElement("div");
            legendItem.className = "gen-mix-item";
            legendItem.innerHTML = `
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span class="legend-dot" style="background-color: ${colorsMapping[key]}"></span>
                    <span class="legend-label">${namesMapping[key]}</span>
                </div>
                <div style="text-align: right;">
                    <span class="legend-val">${val.toLocaleString()} MW</span>
                    <span class="legend-pct">${pct}%</span>
                </div>
            `;
            genMixListEl.appendChild(legendItem);
        });
    }

    // 6. Fetch and Render Complete Grid Status
    async function loadGridStatus(forceRefresh = false) {
        try {
            const url = `/api/status?force_refresh=${forceRefresh}`;
            const response = await fetch(url);
            const res = await response.json();
            
            if (res.success) {
                // Mode config
                if (res.mode === "replay") {
                    modeBadgeEl.innerHTML = `<i class="fa-solid fa-film"></i> REPLAY SIMULATION (Hour ${String(res.hour).padStart(2, '0')})`;
                    modeBadgeEl.className = "api-source-badge simulation";
                } else {
                    modeBadgeEl.innerHTML = `<i class="fa-solid fa-server"></i> KPX LIVE API`;
                    modeBadgeEl.className = "api-source-badge live";
                }

                const data = res.data;
                const mix = res.generation_mix;
                const ci = res.carbon_intensity;
                const stressLvl = res.grid_stress_level;
                const stressCol = res.grid_stress_color;
                
                // Update Badge and Status Description
                statusDescEl.textContent = `${stressLvl}`;
                statusGlowEl.className = `live-glowing-indicator ${stressCol.toLowerCase()}`;
                
                // Customize tips based on grid status
                if (stressCol === "GREEN") {
                    statusTipTextEl.textContent = "🔋 전력 공급에 초록불이 켜졌습니다. MLOps 대용량 학습, GPU 집중 기동에 가장 최적화된 시점입니다.";
                } else if (stressCol === "BLUE") {
                    statusTipTextEl.textContent = "⚡ 전력 수급 상황이 대단히 안정적입니다. 탄소량에 큰 방해를 주지 않고 일반 모델링 작업을 소화할 수 있습니다.";
                } else if (stressCol === "YELLOW") {
                    statusTipTextEl.textContent = "⚠️ 공급 마진이 다소 타이트해지기 시작했습니다. 긴급도가 낮은 모델 가동은 다음 한산한 창으로 이전을 제안합니다.";
                } else if (stressCol === "ORANGE") {
                    statusTipTextEl.textContent = "🚨 화석연료 첨두발전기가 고속 연동 가동 중입니다. 탄소 배출이 급상승 중이니 무거운 배치는 즉각 연기하십시오.";
                } else {
                    statusTipTextEl.textContent = "🛑 전력거래 정전 위험 임계치 수준! 클러스터 운영 보호 및 사회적 저배출 기여를 위해 서버 자원 가중치를 긴급 절감하십시오.";
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
                const colorsHex = {
                    GREEN: "#10b981",
                    BLUE: "#3b82f6",
                    YELLOW: "#f59e0b",
                    ORANGE: "#f97316",
                    RED: "#ef4444"
                };
                reserveGaugeFill.style.stroke = colorsHex[stressCol] || "#10b981";

                // Populate Sub Numbers List
                operReserveRateEl.textContent = `${data.operational_reserve_rate.toFixed(2)} %`;
                operReserveMwEl.textContent = `${data.operational_reserve_mw.toLocaleString()} MW`;
                forecastLoadEl.textContent = `${data.forecast_load_mw.toLocaleString()} MW`;

                // Update Carbon intensity metrics
                updateCarbonIntensityUI(ci);

                // Update Donut Chart datasets
                const mixArray = [
                    mix.hydro, mix.oil, mix.coal_bituminous, mix.nuclear, mix.pumped,
                    mix.gas_lng, mix.coal_domestic, mix.renewable, mix.solar
                ];
                updateDonutChart(mixArray);
                updateFuelMixLegendUI(mix);

                // Update Historical Trend line chart
                if (res.all_history) {
                    updateTrendChart(res.all_history, res.hour);
                }

                // Trigger AI Advisor Refresh
                await loadAIRecommendations();

            } else {
                statusDescEl.textContent = "수집 실패";
                statusTipTextEl.textContent = "에러: " + res.error;
            }
        } catch (error) {
            statusDescEl.textContent = "통신 중단";
            statusTipTextEl.textContent = "FastAPI 서버 백엔드를 실행하십시오.";
            console.error("Error fetching status:", error);
        }
    }

    // 7. Fetch and Render Gemini AI Advice
    async function loadAIRecommendations() {
        aiActionsListEl.innerHTML = `<li><i class="fa-solid fa-spinner fa-spin"></i> Gemini 실시간 판정 스캔 중...</li>`;
        
        try {
            const response = await fetch("/api/advice");
            const res = await response.json();
            
            // Render outputs
            aiSavingEl.textContent = res.estimated_saving;
            aiDeferHintEl.textContent = res.defer_until_hint;
            aiReasoningEl.textContent = res.reasoning;
            
            // Set Badge style
            aiBadgeEl.innerHTML = ""; // Reset
            if (res.recommendation === "RUN_NOW") {
                aiBadgeEl.className = "decision-badge run-now";
                aiBadgeEl.innerHTML = `<i class="fa-solid fa-circle-check"></i> 즉시 가동 승인`;
            } else {
                aiBadgeEl.className = "decision-badge defer";
                aiBadgeEl.innerHTML = `<i class="fa-solid fa-hourglass-half"></i> 지연 대기 권고`;
            }
            
            // Build action points
            aiActionsListEl.innerHTML = "";
            res.actions.forEach(action => {
                const li = document.createElement("li");
                li.innerHTML = `<i class="fa-solid fa-circle-chevron-right" style="color: ${res.recommendation === 'RUN_NOW' ? 'var(--color-green)' : 'var(--color-yellow)'}"></i> ${action}`;
                aiActionsListEl.appendChild(li);
            });
            
        } catch (error) {
            console.error("Error reading AI advice:", error);
            aiActionsListEl.innerHTML = `<li style="color: var(--color-red)"><i class="fa-solid fa-triangle-exclamation"></i> AI 권고 패널을 리프레시할 수 없습니다.</li>`;
        }
    }

    // 8. Event listeners & tickers
    btnForceTick.addEventListener("click", async () => {
        btnForceTick.disabled = true;
        const icon = btnForceTick.querySelector("i");
        icon.className = "fa-solid fa-arrows-rotate fa-spin";
        
        await loadGridStatus(true);
        
        icon.className = "fa-solid fa-forward-step";
        btnForceTick.disabled = false;
    });

    // Initial Load
    loadGridStatus();

    // Auto-polling interval: 30 seconds for live feel
    setInterval(() => {
        loadGridStatus();
    }, 30000);
});
