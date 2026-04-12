<template>
  <div class="storage-page">
    <!-- Header Section -->
    <section class="apple-section-dark hero-section">
      <h1 class="apple-display-hero">Storage</h1>
      <p class="apple-sub-heading" style="color: rgba(255,255,255,0.8); margin-top: 8px;">
        Manage your data collections
      </p>
    </section>

    <!-- Main Content -->
    <section class="apple-section">
      <div class="storage-layout">
        <!-- Collections Sidebar -->
        <div class="apple-card collections-panel">
          <div class="apple-card-header" style="display: flex; align-items: center; justify-content: space-between;">
            <h2 class="apple-card-title">Collections</h2>
            <button class="apple-btn apple-btn-light" @click="loadCollections">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
              </svg>
            </button>
          </div>

          <div class="panel-search">
            <input
              v-model="searchQuery"
              type="text"
              class="apple-input"
              placeholder="Search collections..."
            />
          </div>

          <div class="collections-list">
            <div
              v-for="col in filteredCollections"
              :key="col"
              class="collection-item"
              :class="{ active: selectedCollection === col }"
              @click="selectCollection(col)"
            >
              <div class="collection-info">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M20 6h-8l-2-2H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm0 12H4V8h16v10z"/>
                </svg>
                <span class="collection-name">{{ col }}</span>
              </div>
              <button
                class="collection-delete"
                @click.stop="deleteCollection(col)"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
                </svg>
              </button>
            </div>

            <div v-if="filteredCollections.length === 0" class="apple-empty">
              <svg class="apple-empty-icon" viewBox="0 0 24 24" fill="currentColor">
                <path d="M20 6h-8l-2-2H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm0 12H4V8h16v10z"/>
              </svg>
              <p class="apple-caption">No collections found</p>
            </div>
          </div>
        </div>

        <!-- Data Table Panel -->
        <div class="apple-card data-panel">
          <template v-if="selectedCollection">
            <div class="apple-card-header" style="display: flex; align-items: center; justify-content: space-between;">
              <div>
                <h2 class="apple-card-title">{{ selectedCollection }}</h2>
                <p class="apple-caption" style="margin-top: 4px; color: rgba(0,0,0,0.5);">
                  {{ items.length }} items
                </p>
              </div>
              <div style="display: flex; gap: 8px;">
                <button class="apple-btn apple-btn-light" @click="loadItems">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
                  </svg>
                  Refresh
                </button>
              </div>
            </div>

            <div class="apple-card-body" style="padding: 0;">
              <div class="table-container">
                <table class="apple-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Fetch Time</th>
                      <th>Record Time</th>
                      <th style="text-align: center;">Data</th>
                      <th style="text-align: center;">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="item in items" :key="item._id">
                      <td class="cell-id">{{ item._id }}</td>
                      <td class="cell-time">{{ formatTime(item.FetchTime) }}</td>
                      <td class="cell-time">{{ formatTime(item.RecordTime) }}</td>
                      <td style="text-align: center;">
                        <button class="apple-btn apple-btn-outline" style="padding: 4px 12px; font-size: 13px;" @click="showData(item)">
                          View
                        </button>
                      </td>
                      <td style="text-align: center;">
                        <button class="apple-btn apple-btn-light" style="padding: 4px 12px; font-size: 13px; color: #dc4446;" @click="deleteItem(item._id)">
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
                          </svg>
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div v-if="items.length === 0 && !isLoading" class="apple-empty" style="padding: 48px;">
                <svg class="apple-empty-icon" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>
                </svg>
                <p class="apple-caption">No items in this collection</p>
              </div>

              <div v-if="hasMore" class="load-more">
                <button class="apple-btn apple-btn-primary apple-btn-pill" @click="loadMore" :disabled="isLoading">
                  {{ isLoading ? 'Loading...' : 'Load More' }}
                </button>
              </div>
            </div>
          </template>

          <template v-else>
            <div class="apple-empty" style="min-height: 400px;">
              <svg class="apple-empty-icon" viewBox="0 0 24 24" fill="currentColor">
                <path d="M20 6h-8l-2-2H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm0 12H4V8h16v10z"/>
              </svg>
              <p class="apple-sub-heading" style="color: #1d1d1f; margin-bottom: 8px;">Select a Collection</p>
              <p class="apple-caption">Choose a collection from the sidebar to view its data</p>
            </div>
          </template>
        </div>
      </div>
    </section>

    <!-- Data Detail Modal -->
    <transition name="fade">
      <div v-if="dataDialogOpen" class="apple-modal-overlay" @click="dataDialogOpen = false">
        <div class="apple-modal" @click.stop>
          <div class="apple-modal-header">
            <div>
              <h3 class="apple-card-title">Data Detail</h3>
              <p class="apple-micro" style="color: rgba(0,0,0,0.5); margin-top: 2px;">{{ selectedData._id }}</p>
            </div>
            <button class="apple-modal-close" @click="dataDialogOpen = false">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
              </svg>
            </button>
          </div>
          <div class="apple-modal-body">
            <pre class="apple-code">{{ JSON.stringify(selectedData, null, 2) }}</pre>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from "vue";
import { useRuntimeStore } from "../stores/runtime";

const store = useRuntimeStore();

const collections = ref([]);
const selectedCollection = ref("");
const items = ref([]);
const limit = ref(50);
const isLoading = ref(false);
const dataDialogOpen = ref(false);
const selectedData = ref({});
const searchQuery = ref("");

const filteredCollections = computed(() => {
  if (!searchQuery.value) return collections.value;
  return collections.value.filter(c =>
    c.toLowerCase().includes(searchQuery.value.toLowerCase())
  );
});

const hasMore = computed(() => items.value.length >= limit.value);

function formatTime(ts) {
  if (!ts) return "-";
  const date = new Date(ts * 1000);
  return date.toLocaleString();
}

async function loadCollections() {
  try {
    isLoading.value = true;
    collections.value = await store.fetchStorageCollections();
  } catch (err) {
    showToast("Failed to load collections: " + err.message, "error");
  } finally {
    isLoading.value = false;
  }
}

function selectCollection(col) {
  selectedCollection.value = col;
  limit.value = 50;
  loadItems();
}

async function loadItems() {
  if (!selectedCollection.value) return;
  isLoading.value = true;
  try {
    const result = await store.fetchStorageCollection(selectedCollection.value, {
      limit: limit.value,
      order_by: "FetchTime",
      order_desc: true,
    });
    items.value = result.items || [];
  } catch (err) {
    showToast("Failed to load items: " + err.message, "error");
  } finally {
    isLoading.value = false;
  }
}

async function loadMore() {
  limit.value += 50;
  await loadItems();
}

function showData(row) {
  selectedData.value = row;
  dataDialogOpen.value = true;
}

async function deleteItem(itemId) {
  if (!confirm(`Delete item ${itemId.slice(0, 8)}...?`)) return;
  try {
    await store.deleteStorageItem(selectedCollection.value, itemId);
    showToast("Item deleted", "success");
    await loadItems();
  } catch (err) {
    showToast("Failed to delete: " + err.message, "error");
  }
}

async function deleteCollection(col) {
  if (!confirm(`Delete entire collection "${col}"? This cannot be undone.`)) return;
  try {
    // TODO: Implement collection delete API
    showToast("Collection delete not implemented yet", "warning");
  } catch (err) {
    showToast("Failed to delete collection: " + err.message, "error");
  }
}

function showToast(message, type = "info") {
  // Simple toast implementation
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
  setTimeout(() => {
    toast.remove();
  }, 3000);
}

onMounted(() => {
  loadCollections();
});
</script>

<style scoped>
@import "../css/apple-design.css";

.storage-page {
  padding-bottom: 48px;
}

.hero-section {
  text-align: center;
  padding: 48px 24px;
  margin-bottom: 48px;
}

.storage-layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 24px;
}

.collections-panel {
  background: white;
  height: fit-content;
  max-height: calc(100vh - 200px);
  display: flex;
  flex-direction: column;
}

.panel-search {
  padding: 12px 16px;
  border-bottom: 1px solid rgba(0,0,0,0.06);
}

.panel-search .apple-input {
  width: 100%;
}

.collections-list {
  overflow-y: auto;
  flex: 1;
}

.collection-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  cursor: pointer;
  transition: background-color 0.15s ease;
  border-left: 3px solid transparent;
}

.collection-item:hover {
  background-color: rgba(0,0,0,0.02);
}

.collection-item.active {
  background-color: rgba(0, 113, 227, 0.08);
  border-left-color: #0071e3;
}

.collection-info {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.collection-info svg {
  flex-shrink: 0;
  color: rgba(0,0,0,0.4);
}

.collection-item.active .collection-info svg {
  color: #0071e3;
}

.collection-name {
  font-size: 14px;
  color: #1d1d1f;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.collection-item.active .collection-name {
  font-weight: 500;
  color: #0071e3;
}

.collection-delete {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: rgba(0,0,0,0.3);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: all 0.15s ease;
}

.collection-item:hover .collection-delete {
  opacity: 1;
}

.collection-delete:hover {
  background-color: rgba(220, 68, 70, 0.1);
  color: #dc4446;
}

.data-panel {
  background: white;
  min-height: 500px;
}

.table-container {
  overflow-x: auto;
}

.cell-id {
  font-family: "SF Mono", Monaco, monospace;
  font-size: 12px;
  color: rgba(0,0,0,0.6);
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cell-time {
  font-size: 13px;
  color: rgba(0,0,0,0.7);
}

.load-more {
  padding: 24px;
  text-align: center;
  border-top: 1px solid rgba(0,0,0,0.06);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 1024px) {
  .storage-layout {
    grid-template-columns: 280px 1fr;
  }
}

@media (max-width: 768px) {
  .hero-section .apple-display-hero {
    font-size: 40px;
  }

  .storage-layout {
    grid-template-columns: 1fr;
  }

  .collections-panel {
    max-height: 300px;
  }

  .table-container {
    font-size: 13px;
  }

  .cell-id {
    max-width: 100px;
  }
}
</style>
