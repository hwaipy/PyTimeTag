<template>
  <div class="dashboard">
    <!-- Hero Section -->
    <section class="apple-section-dark hero-section">
      <h1 class="apple-display-hero">Dashboard</h1>
      <p class="apple-sub-heading" style="color: rgba(255,255,255,0.8); margin-top: 8px;">
        Real-time data acquisition monitoring
      </p>
    </section>

    <!-- Metrics Grid -->
    <section class="apple-section">
      <div class="apple-grid apple-grid-4 metrics-grid">
        <div class="metric-card">
          <span class="metric-label">Source</span>
          <span class="metric-value">{{ store.metrics?.source || store.session?.source || "-" }}</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">Blocks</span>
          <span class="metric-value">{{ formatNumber(store.metrics?.blocks ?? 0) }}</span>
        </div>
        <div class="metric-card highlight">
          <span class="metric-label">Events</span>
          <span class="metric-value accent">{{ formatNumber(store.metrics?.events_total ?? 0) }}</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">Rate</span>
          <span class="metric-value">{{ store.metrics?.events_rate_per_s ?? 0 }} <span class="unit">/s</span></span>
        </div>
      </div>
    </section>

    <!-- Chart Section -->
    <section class="apple-section">
      <div class="apple-card apple-card-dark chart-card">
        <div class="apple-chart-header">
          <span class="apple-chart-title" style="color: white;">Realtime Rate Trend</span>
          <div class="apple-chart-live" v-if="store.metrics?.running">
            <span class="apple-chart-live-dot"></span>
            <span>LIVE</span>
          </div>
        </div>
        <div ref="rateChartEl" class="chart-container"></div>
      </div>
    </section>

    <!-- Control Cards Grid -->
    <section class="apple-section">
      <div class="apple-grid apple-grid-2">
        <!-- Session Control -->
        <div class="apple-card control-card">
          <div class="apple-card-header">
            <h2 class="apple-card-title">Session Control</h2>
          </div>
          <div class="apple-card-body">
            <div class="control-buttons">
              <button
                class="apple-btn apple-btn-primary"
                @click="store.startSession"
                :disabled="store.session?.running"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M8 5v14l11-7z"/>
                </svg>
                Start
              </button>
              <button
                class="apple-btn apple-btn-danger"
                @click="store.stopSession"
                :disabled="!store.session?.running"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M6 6h12v12H6z"/>
                </svg>
                Stop
              </button>
            </div>

            <div class="status-grid">
              <div class="status-item">
                <span class="status-label">Running</span>
                <span class="status-value" :class="{ active: store.session?.running }">
                  {{ store.session?.running ? "Yes" : "No" }}
                </span>
              </div>
              <div class="status-item">
                <span class="status-label">Source</span>
                <span class="status-value">{{ store.session?.source || "-" }}</span>
              </div>
              <div class="status-item">
                <span class="status-label">Blocks</span>
                <span class="status-value">{{ formatNumber(store.session?.blocks ?? 0) }}</span>
              </div>
              <div class="status-item">
                <span class="status-label">Events</span>
                <span class="status-value">{{ formatNumber(store.session?.events_total ?? 0) }}</span>
              </div>
              <div class="status-item full-width">
                <span class="status-label">Rate</span>
                <span class="status-value">{{ store.session?.events_rate_per_s ?? 0 }} /s</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Realtime Metrics -->
        <div class="apple-card control-card">
          <div class="apple-card-header">
            <h2 class="apple-card-title">Realtime Metrics</h2>
            <span class="connection-badge" :class="{ connected: isConnected }">
              {{ isConnected ? "WS" : "Offline" }}
            </span>
          </div>
          <div class="apple-card-body">
            <div class="status-grid">
              <div class="status-item">
                <span class="status-label">Running</span>
                <span class="status-value" :class="{ active: store.metrics?.running }">
                  {{ store.metrics?.running ? "Yes" : "No" }}
                </span>
              </div>
              <div class="status-item">
                <span class="status-label">Uptime</span>
                <span class="status-value highlight">{{ formatSeconds(store.metrics?.uptime_s) }}</span>
              </div>
              <div class="status-item">
                <span class="status-label">Blocks</span>
                <span class="status-value">{{ formatNumber(store.metrics?.blocks ?? 0) }}</span>
              </div>
              <div class="status-item">
                <span class="status-label">Events</span>
                <span class="status-value">{{ formatNumber(store.metrics?.events_total ?? 0) }}</span>
              </div>
              <div class="status-item full-width">
                <span class="status-label">Rate</span>
                <span class="status-value accent">{{ store.metrics?.events_rate_per_s ?? 0 }} /s</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Analyzers Section -->
    <section class="apple-section">
      <div class="apple-card analyzers-card">
        <div class="apple-card-header" style="display: flex; align-items: center; justify-content: space-between;">
          <h2 class="apple-card-title">Analyzers</h2>
          <button class="apple-btn apple-btn-light" @click="store.fetchAnalyzers">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
            </svg>
            Refresh
          </button>
        </div>
        <div class="apple-card-body">
          <div class="analyzer-controls">
            <div class="analyzer-group">
              <span class="analyzer-label">Counter</span>
              <div class="analyzer-buttons">
                <button
                  class="apple-btn"
                  :class="store.analyzers?.CounterAnalyser?.enabled ? 'apple-btn-primary' : 'apple-btn-light'"
                  @click="store.updateAnalyzer('CounterAnalyser', true, {})"
                >
                  Enable
                </button>
                <button
                  class="apple-btn"
                  :class="!store.analyzers?.CounterAnalyser?.enabled ? 'apple-btn-dark' : 'apple-btn-light'"
                  @click="store.updateAnalyzer('CounterAnalyser', false, {})"
                >
                  Disable
                </button>
              </div>
              <span class="analyzer-status" :class="{ on: store.analyzers?.CounterAnalyser?.enabled }">
                {{ store.analyzers?.CounterAnalyser?.enabled ? "On" : "Off" }}
              </span>
            </div>

            <div class="analyzer-group">
              <span class="analyzer-label">Histogram</span>
              <div class="analyzer-buttons">
                <button
                  class="apple-btn apple-btn-outline"
                  @click="enableHistogramDefault"
                >
                  Enable Default
                </button>
                <button
                  class="apple-btn"
                  :class="!store.analyzers?.HistogramAnalyser?.enabled ? 'apple-btn-dark' : 'apple-btn-light'"
                  @click="store.updateAnalyzer('HistogramAnalyser', false, {})"
                >
                  Disable
                </button>
              </div>
              <span class="analyzer-status" :class="{ on: store.analyzers?.HistogramAnalyser?.enabled }">
                {{ store.analyzers?.HistogramAnalyser?.enabled ? "On" : "Off" }}
              </span>
            </div>
          </div>

          <div v-if="store.analyzers?.HistogramAnalyser?.last_error" class="error-alert">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/>
            </svg>
            <span>{{ store.analyzers.HistogramAnalyser.last_error }}</span>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref, watch, nextTick } from "vue";
import * as echarts from "echarts";
import { useRuntimeStore } from "../stores/runtime";

const store = useRuntimeStore();
const rateChartEl = ref(null);
let rateChart = null;
const rateHistory = [];
const rateHistoryMax = 60;
const isConnected = ref(false);

const rateTimeFormatter = new Intl.DateTimeFormat([], {
  hourCycle: "h23",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

function formatNumber(num) {
  return new Intl.NumberFormat().format(num);
}

function formatSeconds(v) {
  if (!v && v !== 0) return "-";
  const mins = Math.floor(v / 60);
  const secs = Math.floor(v % 60);
  return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
}

async function enableHistogramDefault() {
  await store.updateAnalyzer("HistogramAnalyser", true, {
    Sync: 0,
    Signals: [1, 2],
    ViewStart: -100000,
    ViewStop: 100000,
    BinCount: 512,
    Divide: 1,
  });
}

function initRateChart() {
  if (!rateChartEl.value) return;

  rateChart = echarts.init(rateChartEl.value, "dark");

  const appleTheme = {
    backgroundColor: "transparent",
    textStyle: {
      fontFamily: "-apple-system, BlinkMacSystemFont, SF Pro Text, sans-serif",
    },
    grid: {
      left: 50,
      right: 16,
      top: 24,
      bottom: 30,
    },
    xAxis: {
      type: "category",
      data: [],
      axisLine: { lineStyle: { color: "rgba(255,255,255,0.2)" } },
      axisLabel: { color: "rgba(255,255,255,0.5)", fontSize: 11 },
    },
    yAxis: {
      type: "value",
      name: "events/s",
      nameTextStyle: { color: "rgba(255,255,255,0.5)" },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: "rgba(255,255,255,0.1)" } },
      axisLabel: { color: "rgba(255,255,255,0.5)", fontSize: 11 },
    },
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(39, 39, 41, 0.95)",
      borderColor: "rgba(255,255,255,0.1)",
      textStyle: { color: "#fff" },
    },
    series: [{
      type: "line",
      smooth: true,
      data: [],
      symbol: "none",
      lineStyle: {
        color: "#0071e3",
        width: 2,
      },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: "rgba(0, 113, 227, 0.3)" },
          { offset: 1, color: "rgba(0, 113, 227, 0)" },
        ]),
      },
    }],
  };

  rateChart.setOption(appleTheme);
}

watch(
  () => store.metrics,
  (m) => {
    if (!m || !rateChart) return;

    isConnected.value = true;
    const t = rateTimeFormatter.format(new Date());
    rateHistory.push({ t, v: Number(m.events_rate_per_s || 0) });
    if (rateHistory.length > rateHistoryMax) rateHistory.shift();

    rateChart.setOption({
      xAxis: { data: rateHistory.map((x) => x.t) },
      series: [{ data: rateHistory.map((x) => x.v) }],
    });
  },
  { deep: true }
);

onMounted(async () => {
  await store.fetchSession();
  await store.fetchAnalyzers();
  store.connectMetrics();
  await nextTick();
  initRateChart();

  window.addEventListener("resize", () => {
    rateChart?.resize();
  });
});

onUnmounted(() => {
  rateChart?.dispose();
});
</script>

<style scoped>
@import "../css/apple-design.css";

.dashboard {
  padding-bottom: 48px;
}

.hero-section {
  text-align: center;
  padding: 48px 24px;
  margin-bottom: 48px;
}

.metrics-grid {
  margin-bottom: 24px;
}

.metric-card {
  background: white;
  border-radius: 12px;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.metric-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}

.metric-label {
  font-size: 12px;
  font-weight: 600;
  color: rgba(0,0,0,0.4);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.metric-value {
  font-size: 28px;
  font-weight: 600;
  color: #1d1d1f;
  letter-spacing: -0.5px;
}

.metric-value.accent {
  color: #0071e3;
}

.metric-value .unit {
  font-size: 14px;
  font-weight: 400;
  color: rgba(0,0,0,0.5);
}

.chart-card {
  padding: 24px;
}

.chart-container {
  height: 260px;
}

.control-card {
  background: white;
}

.control-buttons {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

.status-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.status-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.status-item.full-width {
  grid-column: span 2;
}

.status-label {
  font-size: 12px;
  color: rgba(0,0,0,0.5);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.status-value {
  font-size: 17px;
  font-weight: 500;
  color: #1d1d1f;
}

.status-value.active {
  color: #4caf50;
}

.status-value.highlight {
  color: #0071e3;
  font-weight: 600;
}

.status-value.accent {
  color: #0071e3;
  font-size: 21px;
  font-weight: 600;
}

.connection-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 4px;
  background: rgba(0,0,0,0.05);
  color: rgba(0,0,0,0.4);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.connection-badge.connected {
  background: rgba(76, 175, 80, 0.15);
  color: #4caf50;
}

.analyzers-card {
  background: white;
}

.analyzer-controls {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.analyzer-group {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.analyzer-label {
  font-size: 14px;
  font-weight: 600;
  color: #1d1d1f;
  min-width: 80px;
}

.analyzer-buttons {
  display: flex;
  gap: 8px;
  flex: 1;
}

.analyzer-status {
  font-size: 13px;
  font-weight: 500;
  color: rgba(0,0,0,0.4);
  padding: 4px 10px;
  background: rgba(0,0,0,0.05);
  border-radius: 4px;
}

.analyzer-status.on {
  color: #4caf50;
  background: rgba(76, 175, 80, 0.15);
}

.error-alert {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 20px;
  padding: 12px 16px;
  background: rgba(244, 67, 54, 0.08);
  border-left: 3px solid #f44336;
  border-radius: 0 8px 8px 0;
  color: #d32f2f;
  font-size: 14px;
}

@media (max-width: 1024px) {
  .apple-grid-4 {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .hero-section .apple-display-hero {
    font-size: 40px;
  }

  .apple-grid-2,
  .apple-grid-4 {
    grid-template-columns: 1fr;
  }

  .status-grid {
    grid-template-columns: 1fr;
  }

  .status-item.full-width {
    grid-column: span 1;
  }

  .analyzer-group {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
