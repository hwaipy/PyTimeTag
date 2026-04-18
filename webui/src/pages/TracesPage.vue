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
            <span class="count-label">CH{{ String(ch).padStart(2, '0') }}</span>
            <span class="count-value">{{ formatCount(latestCounts[ch] ?? 0) }}</span>
            <span class="count-at">&nbsp;@&nbsp;</span>
            <input
              v-model.number="channelDelays[ch]"
              type="number"
              class="delay-input"
              step="0.001"
            />
            <span class="count-unit">ns</span>
          </div>
        </div>
      </div>

      <!-- Right: Charts placeholder + controls -->
      <div class="charts-panel">
        <div class="apple-card chart-card">
          <div class="chart-header">
            <span class="chart-title">Count Rate History</span>
            <span class="chart-subtitle">per channel · 100 s window</span>
          </div>
          <div ref="rateChartEl" class="chart-container"></div>
        </div>

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
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue';
import * as echarts from 'echarts';
import { useRuntimeStore } from '../stores/runtime';

const store = useRuntimeStore();

const latestCounts = ref({});
const rateHistory = ref([]);
const histEnabled = ref(true);
const histError = ref('');
const channelDelays = ref(Array.from({ length: 16 }, () => 0));

const histConfig = reactive({
  Sync: 0,
  Signals: [1, 2, 3],
  ViewStart: -100000,
  ViewStop: 100000,
  BinCount: 1000,
  Divide: 1,
});

const intervalStats = reactive({
  count: 0,
  mean: 0,
  std: 0,
  min: 0,
  max: 0,
  last: 0,
});

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
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(num);
}

function formatCount(num) {
  if (num === undefined || num === null) return '-';
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(num);
}

const rateTimeFormatter = new Intl.DateTimeFormat([], {
  hourCycle: 'h23',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
});

function initRateChart() {
  if (!rateChartEl.value) return;
  rateChart = echarts.init(rateChartEl.value);
  rateChart.setOption({
    backgroundColor: 'transparent',
    textStyle: { fontFamily: '-apple-system, BlinkMacSystemFont, SF Pro Text, sans-serif' },
    grid: { left: 56, right: 16, top: 24, bottom: 30 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255,255,255,0.95)',
      borderColor: 'rgba(0,0,0,0.08)',
      textStyle: { color: '#1d1d1f', fontSize: 12 },
    },
    legend: {
      type: 'scroll',
      top: 0,
      right: 8,
      icon: 'roundRect',
      itemWidth: 12,
      itemHeight: 3,
      textStyle: { color: 'rgba(0,0,0,0.6)', fontSize: 11 },
    },
    xAxis: {
      type: 'category',
      axisLine: { lineStyle: { color: 'rgba(0,0,0,0.15)' } },
      axisLabel: { color: 'rgba(0,0,0,0.5)', fontSize: 11 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      name: 'counts/s',
      nameTextStyle: { color: 'rgba(0,0,0,0.5)', fontSize: 11 },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: 'rgba(0,0,0,0.06)' } },
      axisLabel: { color: 'rgba(0,0,0,0.5)', fontSize: 11 },
    },
    series: [],
  });
}

function updateRateChart() {
  if (!rateChart || rateHistory.value.length === 0) return;
  const chCount = channelCount.value;
  const times = rateHistory.value.map((r) => rateTimeFormatter.format(new Date(r.time)));
  const series = [];
  for (let ch = 0; ch < chCount; ch++) {
    series.push({
      name: `Ch ${ch}`,
      type: 'line',
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 1.5 },
      itemStyle: { color: channelColors[ch % channelColors.length] },
      data: rateHistory.value.map((r) => r.rates[ch] ?? 0),
    });
  }
  rateChart.setOption({
    xAxis: { data: times },
    series,
  });
}

watch(rateHistory, updateRateChart, { deep: true });

watch(
  () => store.metrics?.last_analyser?.CounterAnalyser,
  (data) => {
    if (data && typeof data === 'object') {
      const { Configuration, ...counts } = data;
      latestCounts.value = counts;
      onMetricsCounter(data);
    }
  },
  { immediate: true }
);

const rateChartEl = ref(null);
let rateChart = null;

const channelColors = [
  '#0071e3', '#34c759', '#ff9500', '#ff3b30',
  '#5856d6', '#af52de', '#ff2d55', '#5ac8fa',
  '#ffcc00', '#a2845e', '#00c7be', '#007aff',
  '#34c759', '#ff9500', '#ff3b30', '#5856d6',
];

const countSnapshots = [];
const intervals = [];

function updateIntervalStats(dt) {
  intervals.push(dt);
  if (intervals.length > 200) {
    intervals.shift();
  }
  const n = intervals.length;
  if (n === 0) return;
  const sum = intervals.reduce((a, b) => a + b, 0);
  const mean = sum / n;
  const variance = intervals.reduce((a, b) => a + (b - mean) ** 2, 0) / n;
  intervalStats.count = n;
  intervalStats.mean = mean;
  intervalStats.std = Math.sqrt(variance);
  intervalStats.min = Math.min(...intervals);
  intervalStats.max = Math.max(...intervals);
  intervalStats.last = dt;
}

function logIntervalStats() {
  const n = intervalStats.count;
  if (n < 5) return;
  const cv = intervalStats.mean > 0 ? (intervalStats.std / intervalStats.mean) * 100 : 0;
  console.log(
    `[TracesPage] counts update interval | count: ${n} ` +
    `avg: ${intervalStats.mean.toFixed(1)}ms med: ${intervals[Math.floor(n / 2)].toFixed(1)}ms ` +
    `min: ${intervalStats.min.toFixed(1)}ms max: ${intervalStats.max.toFixed(1)}ms ` +
    `std: ${intervalStats.std.toFixed(1)}ms CV: ${cv.toFixed(1)}% ` +
    `last: ${intervalStats.last.toFixed(1)}ms`
  );
}

function onMetricsCounter(data) {
  if (!data || typeof data !== 'object') return;
  const now = Date.now();
  const chCount = channelCount.value;

  const counts = {};
  const rates = [];
  for (let ch = 0; ch < chCount; ch++) {
    const c = data[ch] ?? 0;
    counts[ch] = c;
    rates.push(Math.max(0, c));
  }
  countSnapshots.push({ time: now, counts });

  if (countSnapshots.length >= 2) {
    const prev = countSnapshots[countSnapshots.length - 2];
    const curr = countSnapshots[countSnapshots.length - 1];
    const dt = curr.time - prev.time;
    if (dt > 0) {
      updateIntervalStats(dt);
      rateHistory.value.push({ time: curr.time, rates });
    }
  }

  const cutoff = now - 110 * 1000;
  const csTrim = countSnapshots.findIndex((s) => s.time >= cutoff);
  if (csTrim > 0) {
    countSnapshots.splice(0, csTrim);
  }
  const rhTrim = rateHistory.value.findIndex((r) => r.time >= cutoff);
  if (rhTrim > 0) {
    rateHistory.value.splice(0, rhTrim);
  }
}

async function fetchHistogram() {
  try {
    const data = await store.storageList('HistogramAnalyser', { limit: 1 });
    const items = data.items || [];
    if (items.length > 0 && items[0].Data && items[0].Data.Histograms) {
      // histogram chart update skipped
    }
  } catch {
    // ignore
  }
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
    await fetchHistogram();
  } catch (err) {
    histError.value = err.message || 'Failed to apply config';
  }
}

async function toggleHistogram() {
  histError.value = '';
  try {
    await store.updateAnalyzer('HistogramAnalyser', !histEnabled.value, {});
    histEnabled.value = !histEnabled.value;
    await fetchHistogram();
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

onMounted(async () => {
  try {
    await store.fetchDevices();
    await loadAnalyserStatus();
    store.connectMetrics();
    await fetchHistogram();
    await nextTick();
    initRateChart();
    window.addEventListener('resize', () => rateChart?.resize());
  } catch (err) {
    console.error('TracesPage mount failed:', err);
  }
  onUnmounted(() => {
    store.disconnectMetrics();
    rateChart?.dispose();
    rateChart = null;
  });
});
</script>

<style scoped>
@import '../css/apple-design.css';

.traces-page {
  padding-bottom: 48px;
}

.traces-layout {
  display: flex;
  gap: 16px;
  align-items: start;
}

.counts-panel {
  background: white;
  padding: 16px;
  border-radius: 12px;
  width: 280px;
  flex-shrink: 0;
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
  gap: 6px;
}

.count-row {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 8px;
  background: rgba(0, 0, 0, 0.03);
  border-radius: 8px;
  font-family: 'SF Mono', Monaco, 'Courier New', monospace;
  font-variant-numeric: tabular-nums;
}

.count-label {
  font-size: 13px;
  font-weight: 700;
  color: #1d1d1f;
  width: 38px;
  flex-shrink: 0;
}

.count-value {
  font-size: 15px;
  font-weight: 600;
  color: #1d1d1f;
  width: 9ch;
  text-align: right;
  flex-shrink: 0;
}

.count-at {
  font-size: 15px;
  color: rgba(0, 0, 0, 0.4);
  flex-shrink: 0;
}

.delay-input {
  width: 6ch;
  padding: 2px 4px;
  border-radius: 4px;
  border: none;
  background: transparent;
  color: #1d1d1f;
  font-size: 12px;
  font-family: inherit;
  font-variant-numeric: tabular-nums;
  text-align: right;
  flex-shrink: 0;
  -webkit-appearance: none;
  -moz-appearance: textfield;
  appearance: textfield;
}

.delay-input::-webkit-inner-spin-button,
.delay-input::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.delay-input:focus {
  outline: none;
  border: 1px solid #0071e3;
  background: rgba(255, 255, 255, 0.6);
}

.count-unit {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.5);
  flex-shrink: 0;
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
  height: 260px;
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
    flex-direction: column;
  }

  .counts-panel {
    width: 100%;
  }
}
</style>
