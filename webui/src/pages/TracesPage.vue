<template>
  <div class="traces-page">
    <div class="traces-layout">
      <!-- Left: Channel Counts -->
      <div class="counts-panel apple-card">
        <div class="counts-header">Channel Count Rate</div>
        <div class="counts-list">
          <div
            v-for="ch in channelIds"
            :key="ch"
            class="count-row"
            :class="{
              'count-row-signal': signalChannels.includes(ch),
              'count-row-sync': ch === currentSyncChannel,
            }"
            @click="toggleSignalChannel(ch)"
          >
            <span class="count-label">CH{{ String(ch).padStart(2, '0') }}</span>
            <span class="count-value">{{ formatCount(latestCounts[ch] ?? 0) }}</span>
            <span class="count-at">&nbsp;@&nbsp;</span>
            <input
              v-model="channelDelays[ch]"
              type="number"
              class="delay-input"
              step="any"
              @click.stop
              @blur="channelDelays[ch] = parseFloat(channelDelays[ch]) || 0"
            />
            <span class="count-unit">ns</span>
          </div>
        </div>
      </div>

      <!-- Right: Charts placeholder + controls -->
      <div class="charts-panel">
        <div class="apple-card chart-card rate-chart-card">
          <div class="chart-header">
            <span class="chart-title">Count Rate History</span>
            <span class="chart-subtitle">per channel · ~120 s from storage stream</span>
          </div>
          <div ref="rateChartEl" class="chart-container"></div>
        </div>

        <div class="apple-card chart-card hist-chart-card">
          <div class="chart-header">
            <span class="chart-title">Histograms</span>
          </div>
          <div class="hist-controls">
            <div class="hist-controls-grid">
              <label class="hist-control-item">
                <span class="hist-control-label">Sync</span>
                <input
                  v-model.number="histDraft.Sync"
                  type="number"
                  min="0"
                  :max="Math.max(0, channelCount - 1)"
                  class="hist-control-input hist-control-input-sync"
                  @keydown.enter.prevent="applyHistogramDraft"
                  @keydown.esc.prevent="cancelHistogramField('Sync')"
                  @blur="applyHistogramDraft"
                />
              </label>
              <label class="hist-control-item">
                <span class="hist-control-label">Signals (csv)</span>
                <input
                  v-model="histSignalsText"
                  type="text"
                  class="hist-control-input"
                  placeholder="e.g. 2,3"
                  @keydown.enter.prevent="applyHistogramDraft"
                  @keydown.esc.prevent="cancelHistogramField('Signals')"
                  @blur="applyHistogramDraft"
                />
              </label>
              <label class="hist-control-item">
                <span class="hist-control-label">ViewStart</span>
                <input
                  v-model.number="histDraft.ViewStart"
                  type="number"
                  class="hist-control-input"
                  @keydown.enter.prevent="applyHistogramDraft"
                  @keydown.esc.prevent="cancelHistogramField('ViewStart')"
                  @blur="applyHistogramDraft"
                />
              </label>
              <label class="hist-control-item">
                <span class="hist-control-label">ViewStop</span>
                <input
                  v-model.number="histDraft.ViewStop"
                  type="number"
                  class="hist-control-input"
                  @keydown.enter.prevent="applyHistogramDraft"
                  @keydown.esc.prevent="cancelHistogramField('ViewStop')"
                  @blur="applyHistogramDraft"
                />
              </label>
              <label class="hist-control-item">
                <span class="hist-control-label">BinCount</span>
                <input
                  v-model.number="histDraft.BinCount"
                  type="number"
                  min="1"
                  class="hist-control-input"
                  @keydown.enter.prevent="applyHistogramDraft"
                  @keydown.esc.prevent="cancelHistogramField('BinCount')"
                  @blur="applyHistogramDraft"
                />
              </label>
              <label class="hist-control-item">
                <span class="hist-control-label">Divide</span>
                <input
                  v-model.number="histDraft.Divide"
                  type="number"
                  min="1"
                  class="hist-control-input"
                  @keydown.enter.prevent="applyHistogramDraft"
                  @keydown.esc.prevent="cancelHistogramField('Divide')"
                  @blur="applyHistogramDraft"
                />
              </label>
            </div>
          </div>
          <div ref="histChartEl" class="chart-container"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue';
import * as echarts from 'echarts';
import { useRuntimeStore } from '../stores/runtime';

const store = useRuntimeStore();

const channelDelays = ref(Array.from({ length: 16 }, () => 0));

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

const latestCounts = computed(() => store.latestCounts || {});
const rateHistory = computed(() => store.metricsHistory || []);

const histAnalyserState = computed(() => store.analyzers?.HistogramAnalyser);
const histCfg = computed(() => histAnalyserState.value?.configuration || {});
const currentSyncChannel = computed(() => {
  const maxChannel = Math.max(0, channelCount.value - 1);
  return toInt(histCfg.value.Sync, 0, 0, maxChannel);
});
const signalChannels = computed(() => {
  const maxChannel = Math.max(0, channelCount.value - 1);
  return parseSignalsText(histSignalsText.value, maxChannel);
});
const HIST_DEFAULT_CONFIG = {
  Sync: 0,
  Signals: [2, 3],
  ViewStart: 0,
  ViewStop: 40000000,
  BinCount: 1000,
  Divide: 1,
};
const histDraft = ref({ ...HIST_DEFAULT_CONFIG });
const histSignalsText = ref(HIST_DEFAULT_CONFIG.Signals.join(','));
const histAppliedDraft = ref({ ...HIST_DEFAULT_CONFIG });
const histAppliedSignalsText = ref(HIST_DEFAULT_CONFIG.Signals.join(','));

function formatNumber(num) {
  if (num === undefined || num === null) return '-';
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(num);
}

function formatCount(num) {
  if (num === undefined || num === null) return '-';
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(num);
}

function toFiniteNumber(v, fallback) {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function toInt(v, fallback, minValue = null, maxValue = null) {
  let n = Math.floor(Number(v));
  if (!Number.isFinite(n)) n = fallback;
  if (minValue !== null) n = Math.max(minValue, n);
  if (maxValue !== null) n = Math.min(maxValue, n);
  return n;
}

function parseSignalsText(value, maxChannel) {
  const text = String(value || '').trim();
  if (!text) return [];
  const items = text
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
    .map((s) => Number.parseInt(s, 10))
    .filter((n) => Number.isInteger(n) && n >= 0 && n <= maxChannel);
  return [...new Set(items)];
}

function resetHistogramDraft() {
  const state = histAnalyserState.value || {};
  const cfg = state.configuration || {};
  const maxChannel = Math.max(0, channelCount.value - 1);
  histDraft.value = {
    Sync: toInt(cfg.Sync, HIST_DEFAULT_CONFIG.Sync, 0, maxChannel),
    Signals: Array.isArray(cfg.Signals) ? cfg.Signals : [...HIST_DEFAULT_CONFIG.Signals],
    ViewStart: toFiniteNumber(cfg.ViewStart, HIST_DEFAULT_CONFIG.ViewStart),
    ViewStop: toFiniteNumber(cfg.ViewStop, HIST_DEFAULT_CONFIG.ViewStop),
    BinCount: toInt(cfg.BinCount, HIST_DEFAULT_CONFIG.BinCount, 1),
    Divide: toInt(cfg.Divide, HIST_DEFAULT_CONFIG.Divide, 1),
  };
  histSignalsText.value = histDraft.value.Signals.join(',');
  histAppliedDraft.value = { ...histDraft.value };
  histAppliedSignalsText.value = histSignalsText.value;
}

function cancelHistogramField(fieldName) {
  if (fieldName === 'Signals') {
    histSignalsText.value = histAppliedSignalsText.value;
    return;
  }
  if (Object.prototype.hasOwnProperty.call(histAppliedDraft.value, fieldName)) {
    histDraft.value[fieldName] = histAppliedDraft.value[fieldName];
  }
}

function normalizeHistogramDraft() {
  const maxChannel = Math.max(0, channelCount.value - 1);
  const sync = toInt(histDraft.value.Sync, HIST_DEFAULT_CONFIG.Sync, 0, maxChannel);
  const signals = parseSignalsText(histSignalsText.value, maxChannel);
  const viewStart = toFiniteNumber(histDraft.value.ViewStart, HIST_DEFAULT_CONFIG.ViewStart);
  const viewStop = toFiniteNumber(histDraft.value.ViewStop, HIST_DEFAULT_CONFIG.ViewStop);
  const binCount = toInt(histDraft.value.BinCount, HIST_DEFAULT_CONFIG.BinCount, 1);
  const divide = toInt(histDraft.value.Divide, HIST_DEFAULT_CONFIG.Divide, 1);
  return {
    Sync: sync,
    Signals: signals,
    ViewStart: viewStart,
    ViewStop: viewStop,
    BinCount: binCount,
    Divide: divide,
  };
}

async function applyHistogramDraft() {
  try {
    const payload = normalizeHistogramDraft();
    if (!(payload.ViewStop > payload.ViewStart)) {
      resetHistogramDraft();
      return;
    }
    const sameAsApplied = JSON.stringify(payload) === JSON.stringify(histAppliedDraft.value);
    if (sameAsApplied && histSignalsText.value === histAppliedSignalsText.value) return;
    await store.updateAnalyzer('HistogramAnalyser', true, payload);
    histDraft.value = { ...payload };
    histSignalsText.value = payload.Signals.join(',');
    histAppliedDraft.value = { ...payload };
    histAppliedSignalsText.value = histSignalsText.value;
  } catch (err) {
    console.error('Failed to apply histogram config:', err);
    resetHistogramDraft();
  }
}

async function toggleSignalChannel(channel) {
  const maxChannel = Math.max(0, channelCount.value - 1);
  const ch = toInt(channel, 0, 0, maxChannel);
  const current = parseSignalsText(histSignalsText.value, maxChannel);
  const hasChannel = current.includes(ch);
  const next = hasChannel ? current.filter((n) => n !== ch) : [...current, ch];
  next.sort((a, b) => a - b);
  histSignalsText.value = next.join(',');
  histDraft.value.Signals = [...next];
  await applyHistogramDraft();
}

const rateTimeFormatter = new Intl.DateTimeFormat([], {
  hourCycle: 'h23',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
});

const rateChartEl = ref(null);
const histChartEl = ref(null);
let rateChart = null;
let histChart = null;
/** Avoid clearing the histogram on transient empty SSE frames while the analyser stays on. */
let histChartHasValidSeries = false;
let tooltipMousePos = null;

const channelColors = [
  '#0071e3', '#34c759', '#ff9500', '#ff3b30',
  '#5856d6', '#af52de', '#ff2d55', '#5ac8fa',
  '#ffcc00', '#a2845e', '#00c7be', '#007aff',
  '#34c759', '#ff9500', '#ff3b30', '#5856d6',
];

/** Same grid as count-rate trace: adaptive width via containLabel + matching margins. */
const TRACES_CHART_GRID = { left: 8, right: 8, top: 40, bottom: 30, containLabel: true };

function initRateChart() {
  if (!rateChartEl.value) return;
  rateChart = echarts.init(rateChartEl.value);
  rateChart.getZr().on('mousemove', (e) => {
    tooltipMousePos = { x: e.offsetX, y: e.offsetY };
  });
  rateChart.getZr().on('mouseout', () => {
    tooltipMousePos = null;
  });
  rateChart.setOption({
    animation: false,
    backgroundColor: 'transparent',
    textStyle: { fontFamily: '-apple-system, BlinkMacSystemFont, SF Pro Text, sans-serif' },
    grid: { ...TRACES_CHART_GRID },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255,255,255,0.95)',
      borderColor: 'rgba(0,0,0,0.08)',
      textStyle: { color: '#1d1d1f', fontSize: 12 },
      extraCssText: 'max-width: 320px;',
      formatter: (params) => {
        if (!params || !params.length) return '';
        const sorted = [...params].sort((a, b) => a.seriesName.localeCompare(b.seriesName)).filter((p) => p.value > 0);
        const lines = sorted.map((p) => {
          const val = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(p.value);
          return `<div style="break-inside:avoid;">${p.marker} ${p.seriesName}: ${val} counts/s</div>`;
        });
        return `<div style="column-count:2;column-gap:16px;font-size:12px;">${lines.join('')}</div>`;
      },
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
      name: `CH${String(ch).padStart(2, '0')}`,
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
  if (tooltipMousePos) {
    rateChart.dispatchAction({
      type: 'showTip',
      x: tooltipMousePos.x,
      y: tooltipMousePos.y,
    });
  }
}

watch(rateHistory, updateRateChart, { deep: true });

function binCenters(viewStart, viewStop, binCount) {
  if (!Number.isFinite(viewStart) || !Number.isFinite(viewStop) || binCount < 1) return [];
  const w = viewStop - viewStart;
  return Array.from({ length: binCount }, (_, i) => viewStart + (i + 0.5) * (w / binCount));
}

function initHistChart() {
  if (!histChartEl.value) return;
  histChart = echarts.init(histChartEl.value);
  histChart.setOption({
    animation: false,
    backgroundColor: 'transparent',
    textStyle: { fontFamily: '-apple-system, BlinkMacSystemFont, SF Pro Text, sans-serif' },
    grid: { ...TRACES_CHART_GRID },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255,255,255,0.95)',
      borderColor: 'rgba(0,0,0,0.08)',
      textStyle: { color: '#1d1d1f', fontSize: 12 },
      extraCssText: 'max-width: 320px;',
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
      type: 'value',
      axisLine: { lineStyle: { color: 'rgba(0,0,0,0.15)' } },
      axisLabel: { color: 'rgba(0,0,0,0.5)', fontSize: 11 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: 'rgba(0,0,0,0.06)' } },
      axisLabel: { color: 'rgba(0,0,0,0.5)', fontSize: 11 },
    },
    series: [],
  });
}

function updateHistChart() {
  if (!histChart) return;
  const payload = store.latestHistogramAnalyser;
  const enabled = histAnalyserState.value?.enabled === true;
  const maxChannel = Math.max(0, channelCount.value - 1);
  const selectedSignals = parseSignalsText(histSignalsText.value, maxChannel);
  const vs = Number(histCfg.value.ViewStart ?? -100000);
  const ve = Number(histCfg.value.ViewStop ?? 100000);
  const bc = Math.max(1, Math.floor(Number(histCfg.value.BinCount ?? 1000)));

  if (!enabled) {
    histChartHasValidSeries = false;
    histChart.setOption({
      animation: false,
      grid: { ...TRACES_CHART_GRID },
      xAxis: { min: vs, max: ve, show: true },
      yAxis: { min: 0 },
      series: [],
      graphic: [],
    }, { replaceMerge: ['series', 'graphic'] });
    return;
  }

  if (!payload?.Histograms?.length) {
    if (histChartHasValidSeries) return;
    histChart.setOption({
      animation: false,
      grid: { ...TRACES_CHART_GRID },
      xAxis: { min: vs, max: ve, show: true },
      yAxis: { min: 0 },
      series: [],
      graphic: [],
    }, { replaceMerge: ['series', 'graphic'] });
    return;
  }

  const hists = payload.Histograms;
  const first = hists[0];
  if (Array.isArray(first) && first.length > 0 && first[0] === -1) {
    histChartHasValidSeries = false;
    histChart.setOption({
      animation: false,
      grid: { ...TRACES_CHART_GRID },
      xAxis: { min: vs, max: ve },
      yAxis: {},
      series: [],
      graphic: [
        {
          type: 'text',
          left: 'center',
          top: 'middle',
          style: {
            text: 'Invalid histogram (trigger load / overload)',
            fill: '#d32f2f',
            fontSize: 13,
          },
        },
      ],
    }, { replaceMerge: ['series', 'graphic'] });
    return;
  }

  const centers = binCenters(vs, ve, bc);
  const series = [];
  for (let si = 0; si < selectedSignals.length; si++) {
    const arr = hists[si];
    if (!Array.isArray(arr) || arr.length === 0) continue;
    const n = Math.min(arr.length, centers.length);
    const ch = selectedSignals[si];
    const data = [];
    for (let i = 0; i < n; i++) {
      data.push([centers[i], arr[i]]);
    }
    series.push({
      name: `CH${String(ch).padStart(2, '0')}`,
      type: 'line',
      step: 'middle',
      showSymbol: false,
      lineStyle: { width: 1.2 },
      itemStyle: { color: channelColors[ch % channelColors.length] },
      data,
    });
  }

  histChartHasValidSeries = series.length > 0;
  histChart.setOption({
    animation: false,
    grid: { ...TRACES_CHART_GRID },
    graphic: [],
    xAxis: { min: vs, max: ve },
    yAxis: { min: 0 },
    series,
  }, { replaceMerge: ['series', 'graphic'] });
}

watch(
  () => store.latestHistogramAnalyser,
  () => updateHistChart(),
  { deep: true }
);
watch(histSignalsText, () => updateHistChart());
watch(histCfg, () => updateHistChart(), { deep: true });
watch(histAnalyserState, () => updateHistChart(), { deep: true });
watch(histAnalyserState, () => resetHistogramDraft(), { deep: true, immediate: true });

function onResizeCharts() {
  rateChart?.resize();
  histChart?.resize();
}

onMounted(async () => {
  try {
    await store.fetchDevices();
    await store.fetchAnalyzers();
    await nextTick();
    initRateChart();
    histChartHasValidSeries = false;
    initHistChart();
    updateHistChart();
    window.addEventListener('resize', onResizeCharts);
  } catch (err) {
    console.error('TracesPage mount failed:', err);
  }
});

onUnmounted(() => {
  window.removeEventListener('resize', onResizeCharts);
  rateChart?.dispose();
  rateChart = null;
  histChart?.dispose();
  histChart = null;
  histChartHasValidSeries = false;
});
</script>

<style scoped>
@import '../css/apple-design.css';

.traces-page {
  padding-bottom: 48px;
  overflow-x: auto;
}

.traces-layout {
  display: flex;
  gap: 16px;
  align-items: start;
}

.counts-panel {
  background: #fff;
  padding: 12px;
  border-radius: 12px;
  width: auto;
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
  border: 1px solid rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  position: relative;
  overflow: hidden;
  font-family: 'SF Mono', Monaco, 'Courier New', monospace;
  font-variant-numeric: tabular-nums;
}

.count-row-sync {
  box-shadow: none;
}

.count-row-signal::before,
.count-row-sync::before {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 5px;
  border-radius: 8px 0 0 8px;
}

.count-row-signal::before {
  background: #34c759;
}

.count-row-sync::before {
  background: #ff9500;
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
  border: 1px solid transparent;
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
  border-color: #0071e3;
  background: transparent;
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
  flex: 1;
  min-width: 0;
}

.chart-card {
  padding: 16px;
  background: transparent;
  border-radius: 12px;
}

.rate-chart-card {
  background: #fff;
}

.hist-chart-card {
  background: #fff;
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
  width: 100%;
  height: 260px;
}

.hist-controls {
  margin-bottom: 10px;
  padding: 8px;
  border-radius: 10px;
  background: #fff;
}

.hist-controls-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 10px;
  align-items: center;
}

.hist-control-item {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
  width: auto;
  font-family: 'SF Mono', Monaco, 'Courier New', monospace;
  font-variant-numeric: tabular-nums;
}

.hist-control-label {
  font-size: 13px;
  font-weight: 700;
  color: #1d1d1f;
  white-space: nowrap;
}

.hist-control-input {
  width: 8ch;
  min-width: 0;
  border-radius: 6px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  background: transparent;
  padding: 2px 4px;
  font-size: 12px;
  color: #1d1d1f;
  font-family: inherit;
  font-variant-numeric: tabular-nums;
  text-align: right;
  -webkit-appearance: none;
  -moz-appearance: textfield;
  appearance: textfield;
}

.hist-control-input::-webkit-inner-spin-button,
.hist-control-input::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.hist-control-input-sync {
  width: calc(8ch * 0.6);
}

@media (max-width: 900px) {
  .traces-layout {
    flex-wrap: nowrap;
  }
}
</style>
