<template>
  <div class="logs-page">
    <!-- Header Section -->
    <section class="apple-section-dark hero-section">
      <h1 class="apple-display-hero">Logs</h1>
      <p class="apple-sub-heading" style="color: rgba(255,255,255,0.8); margin-top: 8px;">
        Real-time system and application logs
      </p>
    </section>

    <!-- Logs Table -->
    <section class="apple-section">
      <div class="apple-card">
        <div class="apple-card-header" style="display: flex; align-items: center; justify-content: space-between;">
          <div>
            <h2 class="apple-card-title">Log Entries</h2>
            <p class="apple-caption" style="margin-top: 4px; color: rgba(0,0,0,0.5);">
              Showing latest 200 entries
            </p>
          </div>
          <div style="display: flex; gap: 8px;">
            <button class="apple-btn apple-btn-light" @click="store.fetchLogs">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
              </svg>
              Refresh
            </button>
            <button class="apple-btn apple-btn-outline" @click="store.loadMoreLogs">
              Load More
            </button>
          </div>
        </div>

        <div class="logs-container">
          <div
            v-for="(row, idx) in displayedLogs"
            :key="idx"
            class="log-entry"
            :class="getLevelClass(row.level)"
          >
            <span class="log-time">{{ formatTs(row.ts) }}</span>
            <span class="log-level">{{ row.level || "INFO" }}</span>
            <span class="log-message">{{ row.message || "-" }}</span>
          </div>

          <div v-if="displayedLogs.length === 0" class="apple-empty" style="padding: 48px;">
            <svg class="apple-empty-icon" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/>
            </svg>
            <p class="apple-caption">No logs available</p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, computed } from "vue";
import { useRuntimeStore } from "../stores/runtime";

const store = useRuntimeStore();
let wsLogs = null;

const displayedLogs = computed(() => {
  return store.logs.slice().reverse().slice(0, 200);
});

function formatTs(ts) {
  if (!ts) return "-";
  return new Date(ts * 1000).toLocaleTimeString([], { hour12: false });
}

function getLevelClass(level) {
  switch (level?.toUpperCase()) {
    case "ERROR":
    case "CRITICAL":
      return "level-error";
    case "WARN":
    case "WARNING":
      return "level-warn";
    case "DEBUG":
      return "level-debug";
    default:
      return "level-info";
  }
}

onMounted(async () => {
  await store.fetchLogs();
  wsLogs = store.connectLogs();
});

onUnmounted(() => {
  if (wsLogs) wsLogs.close();
});
</script>

<style scoped>
@import "../css/apple-design.css";

.logs-page {
  padding-bottom: 48px;
}

.hero-section {
  text-align: center;
  padding: 48px 24px;
  margin-bottom: 48px;
}

.logs-container {
  max-height: 600px;
  overflow-y: auto;
  font-family: "SF Mono", Monaco, "Cascadia Code", Consolas, monospace;
  font-size: 13px;
}

.log-entry {
  display: grid;
  grid-template-columns: 80px 60px 1fr;
  gap: 16px;
  padding: 10px 20px;
  border-bottom: 1px solid rgba(0,0,0,0.04);
  align-items: start;
}

.log-entry:hover {
  background-color: rgba(0,0,0,0.02);
}

.log-time {
  color: rgba(0,0,0,0.4);
  font-size: 12px;
  white-space: nowrap;
}

.log-level {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: 4px;
  text-align: center;
  letter-spacing: 0.5px;
}

.level-info .log-level {
  background: rgba(0, 113, 227, 0.1);
  color: #0071e3;
}

.level-warn .log-level {
  background: rgba(255, 152, 0, 0.1);
  color: #f90;
}

.level-error .log-level {
  background: rgba(244, 67, 54, 0.1);
  color: #f44336;
}

.level-debug .log-level {
  background: rgba(0,0,0,0.05);
  color: rgba(0,0,0,0.5);
}

.log-message {
  color: #1d1d1f;
  line-height: 1.5;
  word-break: break-word;
}

@media (max-width: 768px) {
  .hero-section .apple-display-hero {
    font-size: 40px;
  }

  .log-entry {
    grid-template-columns: 70px 50px 1fr;
    gap: 8px;
    padding: 10px 16px;
  }

  .log-level {
    font-size: 9px;
  }
}
</style>
