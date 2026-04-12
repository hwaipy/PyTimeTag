<template>
  <div class="settings-page">
    <!-- Header Section -->
    <section class="apple-section-dark hero-section">
      <h1 class="apple-display-hero">Settings</h1>
      <p class="apple-sub-heading" style="color: rgba(255,255,255,0.8); margin-top: 8px;">
        Configure analyzers and system preferences
      </p>
    </section>

    <!-- Settings Grid -->
    <section class="apple-section">
      <div class="apple-grid apple-grid-2">
        <!-- Analyzers Card -->
        <div class="apple-card">
          <div class="apple-card-header" style="display: flex; align-items: center; justify-content: space-between;">
            <h2 class="apple-card-title">Analyzers</h2>
            <button class="apple-btn apple-btn-light" @click="store.fetchAnalyzers">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
              </svg>
            </button>
          </div>
          <div class="apple-card-body">
            <div class="analyzer-row">
              <div class="analyzer-info">
                <span class="analyzer-name">Counter</span>
                <span class="analyzer-status" :class="{ on: store.analyzers?.CounterAnalyser?.enabled }">
                  {{ store.analyzers?.CounterAnalyser?.enabled ? "On" : "Off" }}
                </span>
              </div>
              <div class="analyzer-actions">
                <button
                  class="apple-btn apple-btn-primary"
                  style="padding: 6px 14px; font-size: 14px;"
                  @click="store.updateAnalyzer('CounterAnalyser', true, {})"
                >
                  Enable
                </button>
                <button
                  class="apple-btn apple-btn-light"
                  style="padding: 6px 14px; font-size: 14px;"
                  @click="store.updateAnalyzer('CounterAnalyser', false, {})"
                >
                  Disable
                </button>
              </div>
            </div>

            <div class="analyzer-row">
              <div class="analyzer-info">
                <span class="analyzer-name">Histogram</span>
                <span class="analyzer-status" :class="{ on: store.analyzers?.HistogramAnalyser?.enabled }">
                  {{ store.analyzers?.HistogramAnalyser?.enabled ? "On" : "Off" }}
                </span>
              </div>
              <div class="analyzer-actions">
                <button
                  class="apple-btn apple-btn-outline"
                  style="padding: 6px 14px; font-size: 14px;"
                  @click="enableHistogramDefault"
                >
                  Enable Default
                </button>
                <button
                  class="apple-btn apple-btn-light"
                  style="padding: 6px 14px; font-size: 14px;"
                  @click="store.updateAnalyzer('HistogramAnalyser', false, {})"
                >
                  Disable
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- General Settings Card -->
        <div class="apple-card">
          <div class="apple-card-header" style="display: flex; align-items: center; justify-content: space-between;">
            <h2 class="apple-card-title">General</h2>
            <button class="apple-btn apple-btn-primary" @click="saveAll">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" style="margin-right: 6px;">
                <path d="M17 3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V7l-4-4zm-5 16c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3zm3-10H5V5h10v4z"/>
              </svg>
              Save
            </button>
          </div>
          <div class="apple-card-body">
            <div class="form-group">
              <label class="form-label">Default Source</label>
              <input
                v-model="defaultSource"
                type="text"
                class="apple-input"
                placeholder="Enter default source"
              />
            </div>
            <div class="form-group">
              <label class="form-label">Default Split Seconds</label>
              <input
                v-model="defaultSplitS"
                type="text"
                class="apple-input"
                placeholder="Enter split interval"
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
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
  showToast("Settings saved", "success");
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

function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.className = `apple-toast apple-toast-${type}`;
  toast.innerHTML = `
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
      ${type === "success"
        ? '<path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>'
        : '<path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/>'}
    </svg>
    <span>${message}</span>
  `;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

onMounted(async () => {
  await store.fetchAnalyzers();
  await store.fetchSettings();
  defaultSource.value = String(store.settings.default_source ?? "");
  defaultSplitS.value = String(store.settings.default_split_s ?? "");
});
</script>

<style scoped>
@import "../css/apple-design.css";

.settings-page {
  padding-bottom: 48px;
}

.hero-section {
  text-align: center;
  padding: 48px 24px;
  margin-bottom: 48px;
}

.analyzer-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 0;
  border-bottom: 1px solid rgba(0,0,0,0.06);
}

.analyzer-row:last-child {
  border-bottom: none;
}

.analyzer-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.analyzer-name {
  font-size: 16px;
  font-weight: 500;
  color: #1d1d1f;
}

.analyzer-status {
  font-size: 13px;
  color: rgba(0,0,0,0.5);
}

.analyzer-status.on {
  color: #4caf50;
}

.analyzer-actions {
  display: flex;
  gap: 8px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: rgba(0,0,0,0.7);
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

@media (max-width: 768px) {
  .hero-section .apple-display-hero {
    font-size: 40px;
  }

  .apple-grid-2 {
    grid-template-columns: 1fr;
  }

  .analyzer-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
}
</style>
