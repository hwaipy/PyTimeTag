<template>
  <q-page class="q-pa-md">
    <div class="row q-col-gutter-md">
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
          </q-card-section>
        </q-card>
      </div>

      <div class="col-12 col-md-6">
        <q-card>
          <q-card-section class="row items-center">
            <div class="text-h6 col">Settings</div>
            <q-btn flat color="primary" label="Save To Backend" @click="saveAll" />
          </q-card-section>
          <q-separator />
          <q-card-section>
            <q-input v-model="defaultSource" label="Default Source" outlined dense />
            <q-input v-model="defaultSplitS" label="Default Split Seconds" outlined dense class="q-mt-sm" />
            <q-btn class="q-mt-sm" color="primary" label="Apply To Store" @click="applySettingsDraft" />
          </q-card-section>
        </q-card>
      </div>
    </div>
  </q-page>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRuntimeStore } from "../stores/runtime";

const store = useRuntimeStore();
const defaultSource = ref("");
const defaultSplitS = ref("");

function applySettingsDraft() {
  store.settings = {
    ...store.settings,
    default_source: defaultSource.value,
    default_split_s: defaultSplitS.value,
  };
}

async function saveAll() {
  applySettingsDraft();
  await store.saveSettings();
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

onMounted(async () => {
  await store.fetchAnalyzers();
  await store.fetchSettings();
  defaultSource.value = String(store.settings.default_source ?? "");
  defaultSplitS.value = String(store.settings.default_split_s ?? "");
});
</script>

