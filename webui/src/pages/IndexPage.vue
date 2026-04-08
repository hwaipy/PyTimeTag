<template>
  <q-page class="q-pa-md">
    <div class="row q-col-gutter-md">
      <div class="col-12" id="section-session">
        <q-card>
          <q-card-section class="row q-col-gutter-md">
            <div class="col-12 col-md-3"><b>Source:</b> {{ store.metrics?.source || store.session?.source || "-" }}</div>
            <div class="col-12 col-md-3"><b>Blocks:</b> {{ store.metrics?.blocks ?? 0 }}</div>
            <div class="col-12 col-md-3"><b>Events:</b> {{ store.metrics?.events_total ?? 0 }}</div>
            <div class="col-12 col-md-3"><b>Rate:</b> {{ store.metrics?.events_rate_per_s ?? 0 }} /s</div>
          </q-card-section>
        </q-card>
      </div>

      <div class="col-12">
        <q-card>
          <q-card-section>
            <div class="text-h6">Realtime Rate Trend</div>
          </q-card-section>
          <q-separator />
          <q-card-section>
            <div ref="rateChartEl" style="height: 260px"></div>
          </q-card-section>
        </q-card>
      </div>

      <div class="col-12 col-md-6">
        <q-card>
          <q-card-section><div class="text-h6">Session Control</div></q-card-section>
          <q-separator />
          <q-card-section>
            <q-btn color="primary" label="Start" class="q-mr-sm" @click="store.startSession" />
            <q-btn color="negative" label="Stop" @click="store.stopSession" />
          </q-card-section>
          <q-card-section class="row q-col-gutter-sm">
            <div class="col-6"><b>Running:</b> {{ store.session?.running ? "Yes" : "No" }}</div>
            <div class="col-6"><b>Source:</b> {{ store.session?.source || "-" }}</div>
            <div class="col-6"><b>Blocks:</b> {{ store.session?.blocks ?? 0 }}</div>
            <div class="col-6"><b>Events:</b> {{ store.session?.events_total ?? 0 }}</div>
            <div class="col-12"><b>Rate:</b> {{ store.session?.events_rate_per_s ?? 0 }} /s</div>
          </q-card-section>
        </q-card>
      </div>

      <div class="col-12 col-md-6">
        <q-card>
          <q-card-section><div class="text-h6">Realtime Metrics (WS)</div></q-card-section>
          <q-separator />
          <q-card-section class="row q-col-gutter-sm">
            <div class="col-6"><b>Running:</b> {{ store.metrics?.running ? "Yes" : "No" }}</div>
            <div class="col-6"><b>Uptime:</b> {{ formatSeconds(store.metrics?.uptime_s) }}</div>
            <div class="col-6"><b>Blocks:</b> {{ store.metrics?.blocks ?? 0 }}</div>
            <div class="col-6"><b>Events:</b> {{ store.metrics?.events_total ?? 0 }}</div>
            <div class="col-12"><b>Rate:</b> {{ store.metrics?.events_rate_per_s ?? 0 }} /s</div>
          </q-card-section>
        </q-card>
      </div>

      <div class="col-12 col-md-6">
        <q-card>
          <q-card-section class="row items-center">
            <div class="text-h6 col">Analyzers</div>
            <q-btn flat color="primary" label="Refresh" @click="store.fetchAnalyzers" />
          </q-card-section>
          <q-separator />
          <q-card-section>
            <div class="q-gutter-sm">
              <q-btn color="primary" label="Enable Counter" @click="store.updateAnalyzer('CounterAnalyser', true, {})" />
              <q-btn color="grey-8" label="Disable Counter" @click="store.updateAnalyzer('CounterAnalyser', false, {})" />
              <q-btn color="secondary" label="Enable Histogram(Default)" @click="enableHistogramDefault" />
            </div>
            <div class="q-mt-sm"><b>Counter:</b> {{ store.analyzers?.CounterAnalyser?.enabled ? "On" : "Off" }}</div>
            <div><b>Histogram:</b> {{ store.analyzers?.HistogramAnalyser?.enabled ? "On" : "Off" }}</div>
            <div class="text-negative" v-if="store.analyzers?.HistogramAnalyser?.last_error">
              {{ store.analyzers.HistogramAnalyser.last_error }}
            </div>
          </q-card-section>
        </q-card>
      </div>
    </div>
  </q-page>
</template>

<script setup>
import { onMounted, onUnmounted, ref, watch, nextTick } from "vue";
import * as echarts from "echarts";
import { useRuntimeStore } from "../stores/runtime";

const store = useRuntimeStore();
let ws = null;
const rateChartEl = ref(null);
let rateChart = null;
const rateHistory = [];
const rateHistoryMax = 60;
const rateTimeFormatter = new Intl.DateTimeFormat([], {
  hourCycle: "h23",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

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

onMounted(async () => {
  await store.fetchSession();
  await store.fetchAnalyzers();
  ws = store.connectMetrics();
  await nextTick();
  initRateChart();
});

onUnmounted(() => {
  if (ws) ws.close();
  if (rateChart) rateChart.dispose();
});

function formatSeconds(v) {
  if (!v && v !== 0) return "-";
  return `${Number(v).toFixed(1)} s`;
}

function initRateChart() {
  if (!rateChartEl.value) return;
  rateChart = echarts.init(rateChartEl.value);
  rateChart.setOption({
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: [] },
    yAxis: { type: "value", name: "events/s" },
    series: [{ type: "line", smooth: true, data: [] }],
    grid: { left: 50, right: 16, top: 24, bottom: 30 },
  });
}

watch(
  () => store.metrics,
  (m) => {
    if (!m || !rateChart) return;
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
</script>

