<template>
  <div class="offline-page">
    <!-- Header Section -->
    <section class="apple-section-dark hero-section">
      <h1 class="apple-display-hero">Offline</h1>
      <p class="apple-sub-heading" style="color: rgba(255,255,255,0.8); margin-top: 8px;">
        Process stored data blocks and manage jobs
      </p>
    </section>

    <!-- DataBlocks Section -->
    <section class="apple-section">
      <div class="apple-card">
        <div class="apple-card-header" style="display: flex; align-items: center; justify-content: space-between;">
          <div>
            <h2 class="apple-card-title">Data Blocks</h2>
            <p class="apple-caption" style="margin-top: 4px; color: rgba(0,0,0,0.5);">
              {{ store.datablocks.length }} blocks available
            </p>
          </div>
          <div style="display: flex; gap: 8px;">
            <button class="apple-btn apple-btn-light" @click="store.fetchDatablocks">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
              </svg>
              Refresh
            </button>
            <button class="apple-btn apple-btn-outline" @click="store.loadMoreDatablocks">
              Load More
            </button>
          </div>
        </div>

        <div class="table-container">
          <table class="apple-table">
            <thead>
              <tr>
                <th>Path</th>
                <th style="text-align: right;">Size</th>
                <th style="text-align: right;">Modified</th>
                <th style="text-align: center;">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in store.datablocks" :key="row.path">
                <td class="cell-path">{{ row.path }}</td>
                <td class="cell-size" style="text-align: right;">{{ formatSize(row.size) }}</td>
                <td class="cell-time" style="text-align: right;">{{ formatTime(row.mtime) }}</td>
                <td style="text-align: center;">
                  <button
                    class="apple-btn apple-btn-primary"
                    style="padding: 4px 12px; font-size: 13px;"
                    @click="runOffline(row.path)"
                  >
                    Process
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="store.datablocks.length === 0" class="apple-empty" style="padding: 48px;">
          <svg class="apple-empty-icon" viewBox="0 0 24 24" fill="currentColor">
            <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>
          </svg>
          <p class="apple-caption">No data blocks available</p>
        </div>
      </div>
    </section>

    <!-- Jobs Section -->
    <section class="apple-section">
      <div class="apple-card">
        <div class="apple-card-header" style="display: flex; align-items: center; justify-content: space-between;">
          <div>
            <h2 class="apple-card-title">Jobs</h2>
            <p class="apple-caption" style="margin-top: 4px; color: rgba(0,0,0,0.5);">
              {{ store.jobs.length }} jobs in queue
            </p>
          </div>
          <div style="display: flex; gap: 8px;">
            <button class="apple-btn apple-btn-light" @click="store.fetchJobs">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
              </svg>
              Refresh
            </button>
            <button class="apple-btn apple-btn-outline" @click="store.loadMoreJobs">
              Load More
            </button>
          </div>
        </div>

        <div class="table-container">
          <table class="apple-table">
            <thead>
              <tr>
                <th>Job ID</th>
                <th>Kind</th>
                <th>Status</th>
                <th style="text-align: right;">Updated</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="job in store.jobs" :key="job.id">
                <td class="cell-id">{{ job.id }}</td>
                <td>
                  <span class="tag">{{ job.kind }}</span>
                </td>
                <td>
                  <span class="status-badge" :class="getStatusClass(job.status)">
                    {{ job.status }}
                  </span>
                </td>
                <td class="cell-time" style="text-align: right;">{{ formatTime(job.updated_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="store.jobs.length === 0" class="apple-empty" style="padding: 48px;">
          <svg class="apple-empty-icon" viewBox="0 0 24 24" fill="currentColor">
            <path d="M19 3h-4.18C14.4 1.84 13.3 1 12 1c-1.3 0-2.4.84-2.82 2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 0c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1zm2 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/>
          </svg>
          <p class="apple-caption">No jobs in queue</p>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted } from "vue";
import { useRuntimeStore } from "../stores/runtime";

const store = useRuntimeStore();

function formatSize(bytes) {
  if (!bytes) return "-";
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit++;
  }
  return `${size.toFixed(1)} ${units[unit]}`;
}

function formatTime(ts) {
  if (!ts) return "-";
  return new Date(ts * 1000).toLocaleString();
}

function getStatusClass(status) {
  switch (status?.toLowerCase()) {
    case "completed":
    case "success":
      return "status-success";
    case "failed":
    case "error":
      return "status-error";
    case "running":
    case "processing":
      return "status-running";
    case "pending":
    case "queued":
      return "status-pending";
    default:
      return "status-default";
  }
}

async function runOffline(path) {
  await store.processDatablock(path);
  await store.fetchJobs();
}

onMounted(async () => {
  await store.fetchDatablocks();
  await store.fetchJobs();
});
</script>

<style scoped>
@import "../css/apple-design.css";

.offline-page {
  padding-bottom: 48px;
}

.hero-section {
  text-align: center;
  padding: 48px 24px;
  margin-bottom: 48px;
}

.table-container {
  overflow-x: auto;
}

.cell-path {
  font-family: "SF Mono", Monaco, monospace;
  font-size: 13px;
  color: #1d1d1f;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cell-size {
  font-family: "SF Mono", Monaco, monospace;
  font-size: 13px;
  color: rgba(0,0,0,0.7);
}

.cell-time {
  font-size: 13px;
  color: rgba(0,0,0,0.5);
}

.cell-id {
  font-family: "SF Mono", Monaco, monospace;
  font-size: 12px;
  color: rgba(0,0,0,0.6);
}

.tag {
  display: inline-block;
  padding: 2px 8px;
  background: rgba(0,0,0,0.05);
  border-radius: 4px;
  font-size: 12px;
  color: rgba(0,0,0,0.7);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.status-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.status-success {
  background: rgba(76, 175, 80, 0.15);
  color: #4caf50;
}

.status-error {
  background: rgba(244, 67, 54, 0.15);
  color: #f44336;
}

.status-running {
  background: rgba(0, 113, 227, 0.15);
  color: #0071e3;
}

.status-pending {
  background: rgba(255, 152, 0, 0.15);
  color: #ff9800;
}

.status-default {
  background: rgba(0,0,0,0.05);
  color: rgba(0,0,0,0.5);
}

@media (max-width: 768px) {
  .hero-section .apple-display-hero {
    font-size: 40px;
  }

  .cell-path {
    max-width: 150px;
  }
}
</style>
