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
          >
            <span class="count-label">CH{{ String(ch).padStart(2, '0') }}</span>
            <span class="count-value">{{ formatCount(latestCounts[ch] ?? 0) }}</span>
            <span class="count-at">&nbsp;@&nbsp;</span>
            <input
              v-model="channelDelays[ch]"
              type="number"
              class="delay-input"
              step="any"
              @blur="channelDelays[ch] = parseFloat(channelDelays[ch]) || 0"
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
            <span class="chart-subtitle">per channel · ~120 s from storage stream</span>
          </div>
          <div ref="rateChartEl" class="chart-container"></div>
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

const rateChartEl = ref(null);
let rateChart = null;
let tooltipMousePos = null;

const channelColors = [
  '#0071e3', '#34c759', '#ff9500', '#ff3b30',
  '#5856d6', '#af52de', '#ff2d55', '#5ac8fa',
  '#ffcc00', '#a2845e', '#00c7be', '#007aff',
  '#34c759', '#ff9500', '#ff3b30', '#5856d6',
];

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
    backgroundColor: 'transparent',
    textStyle: { fontFamily: '-apple-system, BlinkMacSystemFont, SF Pro Text, sans-serif' },
    grid: { left: 8, right: 8, top: 40, bottom: 30, containLabel: true },
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

onMounted(async () => {
  try {
    await store.fetchDevices();
    await nextTick();
    initRateChart();
    window.addEventListener('resize', () => rateChart?.resize());
  } catch (err) {
    console.error('TracesPage mount failed:', err);
  }
});

onUnmounted(() => {
  rateChart?.dispose();
  rateChart = null;
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
  background: white;
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
  flex: 1;
  min-width: 0;
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
  width: 100%;
  height: 260px;
}

@media (max-width: 900px) {
  .traces-layout {
    flex-wrap: nowrap;
  }
}
</style>
