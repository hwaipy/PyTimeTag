<template>
  <div class="traces-page">
    <div class="traces-layout">
      <!-- Left: Channel Counts -->
      <div class="counts-panel apple-card">
        <div class="counts-header">Channel Counts</div>
        <div class="counts-list">
          <div
            v-for="ch in channelIds"
            :key="ch"
            class="count-row"
          >
            <span class="count-label">Ch {{ ch }}</span>
            <span class="count-value">{{ formatNumber(latestCounts[ch] ?? 0) }}</span>
          </div>
        </div>
      </div>

      <!-- Right: Charts -->
      <div class="charts-panel">
        <!-- Rate History Chart -->
        <div class="apple-card chart-card">
          <div class="chart-header">
            <span class="chart-title">Count Rate History</span>
            <span class="chart-subtitle">per channel · 100 s window</span>
          </div>
          <div ref="rateChartEl" class="chart-container"></div>
        </div>

        <!-- Histogram Controls + Chart -->
        <div class="apple-card chart-card">
          <div class="chart-header">
            <span class="chart-title">Histogram</span>
          </div>
          <div class="analyser-controls">
            <div class="control-row">
              <div class="control-group">
                <label>Trigger</label>
                <input v-model.number="histConfig.Sync" type="number" min="0" max="7" class="apple-input small" />
              </div>
              <div class="control-group signals-group">
                <label>Signals</label>
                <div class="signal-checkboxes">
                  <label v-for="n in channelCount" :key="n - 1" class="signal-checkbox">
                    <input type="checkbox" :value="n - 1" v-model="histConfig.Signals" />
                    <span>{{ n - 1 }}</span>
                  </label>
                </div>
              </div>
              <div class="control-group">
                <label>ViewStart</label>
                <input v-model.number="histConfig.ViewStart" type="number" class="apple-input" />
              </div>
              <div class="control-group">
                <label>ViewStop</label>
                <input v-model.number="histConfig.ViewStop" type="number" class="apple-input" />
              </div>
              <div class="control-group">
                <label>BinCount</label>
                <input v-model.number="histConfig.BinCount" type="number" min="1" max="10000" class="apple-input small" />
              </div>
              <div class="control-group">
                <label>Divide</label>
                <input v-model.number="histConfig.Divide" type="number" min="1" class="apple-input small" />
              </div>
              <button class="apple-btn apple-btn-primary" @click="applyHistogramConfig">Apply</button>
              <button
                class="apple-btn"
                :class="histEnabled ? 'apple-btn-danger' : 'apple-btn-primary'"
                @click="toggleHistogram"
              >
                {{ histEnabled ? 'Disable' : 'Enable' }}
              </button>
            </div>
            <div v-if="histError" class="hist-error">{{ histError }}</div>
          </div>
          <div ref="histChartEl" class="chart-container hist-chart"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue';
import * as echarts from 'echarts';
import { useRuntimeStore } from '../stores/runtime';

const store = useRuntimeStore();

const rateChartEl = ref(null);
const histChartEl = ref(null);
let rateChart = null;
let histChart = null;

const latestCounts = ref({});
const rateHistory = ref([]);
const histEnabled = ref(true);
const histError = ref('');

const histConfig = reactive({
  Sync: 0,
  Signals: [1, 2, 3],
  ViewStart: -100000,
  ViewStop: 100000,
  BinCount: 1000,
  Divide: 1,
});

let pollInterval = null;
let isMounted = false;

const channelColors = [
  '#0071e3', '#34c759', '#ff9500', '#ff3b30',
  '#af52de', '#5856d6', '#ff2d55', '#5ac8fa',
];

const channelCount = computed(() => {
  const device = store.devices?.[0];
  if (device && typeof device.channel_count === 'number') {
    return device.channel_count;
  }
  const keys = Object.keys(latestCounts.value).filter((k) => k !== 'Configuration');
  if (keys.length > 0) {
    return Math.max(...keys.map((k) => parseInt(k, 10))) + 1;
  }
  return 8;
});

const channelIds = computed(() => Array.from({ length: channelCount.value }, (_, i) => i));

function formatNumber(num) {
  if (num === undefined || num === null) return '-';
  return new Intl.NumberFormat().format(num);
}

async function fetchLatestCounts() {
  try {
    const data = await store.storageList('CounterAnalyser', { limit: 1 });
    const items = data.items || [];
    if (items.length > 0 && items[0].Data) {
      latestCounts.value = items[0].Data;
    }
  } catch {
    // ignore
  }
}

async function fetchRateHistory() {
  try {
    const data = await store.storageList('CounterAnalyser', { limit: 200 });
    const items = (data.items || []).slice().reverse();
    const points = [];
    let prevTime = null;
    for (const item of items) {
      const t = new Date(item.FetchTime);
      if (prevTime === null) {
        prevTime = t;
        continue;
      }
      const dt = (t - prevTime) / 1000;
      const counts = item.Data || {};
      const rates = [];
      for (let ch = 0; ch < channelCount.value; ch++) {
        const c = counts[String(ch)] || 0;
        rates.push(dt > 0 ? Math.round(c / dt) : 0);
      }
      points.push({ time: t.getTime(), rates });
      prevTime = t;
    }
    rateHistory.value = points;
  } catch {
    // ignore
  }
}

async function fetchHistogram() {
  try {
    const data = await store.storageList('HistogramAnalyser', { limit: 1 });
    const items = data.items || [];
    if (items.length > 0 && items[0].Data && items[0].Data.Histograms) {
      updateHistogramChart(items[0].Data.Histograms);
    }
  } catch {
    // ignore
  }
}

function initRateChart() {
  if (!rateChartEl.value) return;
  rateChart = echarts.init(rateChartEl.value, null, { renderer: 'svg' });
  rateChart.setOption({
    backgroundColor: 'transparent',
    textStyle: { fontFamily: '-apple-system, BlinkMacSystemFont, SF Pro Text, sans-serif' },
    grid: { left: 50, right: 16, top: 32, bottom: 30 },
    legend: { type: 'scroll', top: 0, textStyle: { color: 'rgba(0,0,0,0.7)' } },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: 'rgba(0,0,0,0.1)',
      textStyle: { color: '#1d1d1f' },
    },
    xAxis: {
      type: 'time',
      axisLine: { lineStyle: { color: 'rgba(0,0,0,0.2)' } },
      axisLabel: { color: 'rgba(0,0,0,0.6)', fontSize: 11 },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      name: 'cps',
      nameTextStyle: { color: 'rgba(0,0,0,0.6)' },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: 'rgba(0,0,0,0.06)' } },
      axisLabel: { color: 'rgba(0,0,0,0.6)', fontSize: 11 },
    },
    series: [],
  });
}

function initHistChart() {
  if (!histChartEl.value) return;
  histChart = echarts.init(histChartEl.value, null, { renderer: 'svg' });
  histChart.setOption({
    backgroundColor: 'transparent',
    textStyle: { fontFamily: '-apple-system, BlinkMacSystemFont, SF Pro Text, sans-serif' },
    grid: { left: 50, right: 16, top: 32, bottom: 30 },
    legend: { type: 'scroll', top: 0, textStyle: { color: 'rgba(0,0,0,0.7)' } },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: 'rgba(0,0,0,0.1)',
      textStyle: { color: '#1d1d1f' },
    },
    xAxis: {
      type: 'category',
      axisLine: { lineStyle: { color: 'rgba(0,0,0,0.2)' } },
      axisLabel: { color: 'rgba(0,0,0,0.6)', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      name: 'counts',
      nameTextStyle: { color: 'rgba(0,0,0,0.6)' },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: 'rgba(0,0,0,0.06)' } },
      axisLabel: { color: 'rgba(0,0,0,0.6)', fontSize: 11 },
    },
    series: [],
  });
}

function updateRateChart() {
  if (!rateChart || rateHistory.value.length === 0) return;
  const latestTime = rateHistory.value[rateHistory.value.length - 1]?.time || Date.now();
  const cutoff = latestTime - 100 * 1000;
  const visible = rateHistory.value.filter((p) => p.time >= cutoff);
  const series = [];
  for (let ch = 0; ch < channelCount.value; ch++) {
    series.push({
      name: `Ch ${ch}`,
      type: 'line',
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 1.5, color: channelColors[ch % channelColors.length] },
      itemStyle: { color: channelColors[ch % channelColors.length] },
      data: visible.map((p) => [p.time, p.rates[ch] || 0]),
    });
  }
  rateChart.setOption({ series }, { notMerge: true });
}

function updateHistogramChart(histograms) {
  if (!histChart) return;
  const series = histograms.map((bins, idx) => ({
    name: `Sig ${idx}`,
    type: 'bar',
    barGap: '0%',
    barCategoryGap: '20%',
    itemStyle: { color: channelColors[(idx + 1) % channelColors.length] },
    data: bins,
  }));
  histChart.setOption({ series }, { notMerge: true });
}

async function applyHistogramConfig() {
  histError.value = '';
  try {
    await store.updateAnalyzer('HistogramAnalyser', true, {
      Sync: histConfig.Sync,
      Signals: Array.from(histConfig.Signals).sort((a, b) => a - b),
      ViewStart: histConfig.ViewStart,
      ViewStop: histConfig.ViewStop,
      BinCount: histConfig.BinCount,
      Divide: histConfig.Divide,
    });
    histEnabled.value = true;
  } catch (err) {
    histError.value = err.message || 'Failed to apply config';
  }
}

async function toggleHistogram() {
  histError.value = '';
  try {
    await store.updateAnalyzer('HistogramAnalyser', !histEnabled.value, {});
    histEnabled.value = !histEnabled.value;
  } catch (err) {
    histError.value = err.message || 'Failed to toggle';
  }
}

async function loadAnalyserStatus() {
  await store.fetchAnalyzers();
  const cfg = store.analyzers?.HistogramAnalyser?.configuration || {};
  histEnabled.value = store.analyzers?.HistogramAnalyser?.enabled || false;
  if (cfg.Sync !== undefined) histConfig.Sync = cfg.Sync;
  if (cfg.Signals !== undefined) histConfig.Signals = cfg.Signals;
  if (cfg.ViewStart !== undefined) histConfig.ViewStart = cfg.ViewStart;
  if (cfg.ViewStop !== undefined) histConfig.ViewStop = cfg.ViewStop;
  if (cfg.BinCount !== undefined) histConfig.BinCount = cfg.BinCount;
  if (cfg.Divide !== undefined) histConfig.Divide = cfg.Divide;
}

async function poll() {
  if (!isMounted) return;
  await fetchLatestCounts();
  await fetchRateHistory();
  await fetchHistogram();
  updateRateChart();
}

onMounted(async () => {
  isMounted = true;
  await store.fetchDevices();
  await loadAnalyserStatus();
  await nextTick();
  initRateChart();
  initHistChart();
  await poll();
  pollInterval = setInterval(poll, 1000);
  const onResize = () => {
    rateChart?.resize();
    histChart?.resize();
  };
  window.addEventListener('resize', onResize);
  onUnmounted(() => {
    window.removeEventListener('resize', onResize);
  });
});

onUnmounted(() => {
  isMounted = false;
  clearInterval(pollInterval);
  rateChart?.dispose();
  histChart?.dispose();
});
</script>

<style scoped>
@import '../css/apple-design.css';

.traces-page {
  padding-bottom: 48px;
}

.traces-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 16px;
  align-items: start;
}

.counts-panel {
  background: white;
  padding: 16px;
  border-radius: 12px;
}

.counts-header {
  font-size: 14px;
  font-weight: 600;
  color: #1d1d1f;
  margin-bottom: 12px;
}

.counts-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.count-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  background: rgba(0, 0, 0, 0.03);
  border-radius: 8px;
}

.count-label {
  font-size: 13px;
  font-weight: 500;
  color: rgba(0, 0, 0, 0.6);
}

.count-value {
  font-size: 14px;
  font-weight: 600;
  color: #1d1d1f;
}

.charts-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.chart-card {
  padding: 16px;
  background: transparent;
  border-radius: 12px;
}

.chart-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: #1d1d1f;
}

.chart-subtitle {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.5);
}

.chart-container {
  height: 240px;
}

.hist-chart {
  height: 200px;
}

.analyser-controls {
  margin-bottom: 12px;
}

.control-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 14px;
}

.control-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.control-group label {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.7);
  font-weight: 500;
}

.apple-input {
  width: 90px;
  padding: 5px 8px;
  border-radius: 6px;
  border: 1px solid rgba(0, 0, 0, 0.15);
  background: rgba(255, 255, 255, 0.6);
  color: #1d1d1f;
  font-size: 13px;
}

.apple-input.small {
  width: 56px;
}

.apple-input:focus {
  outline: none;
  border-color: #0071e3;
}

.signals-group {
  align-items: flex-start;
}

.signal-checkboxes {
  display: flex;
  gap: 6px;
}

.signal-checkbox {
  display: flex;
  align-items: center;
  gap: 3px;
  cursor: pointer;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.85);
  padding: 4px 6px;
  background: rgba(0, 0, 0, 0.04);
  border-radius: 6px;
  border: 1px solid rgba(0, 0, 0, 0.1);
}

.signal-checkbox input {
  accent-color: #0071e3;
}

.hist-error {
  margin-top: 8px;
  font-size: 12px;
  color: #d32f2f;
}

@media (max-width: 900px) {
  .traces-layout {
    grid-template-columns: 1fr;
  }
}
</style>
