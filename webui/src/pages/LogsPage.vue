<template>
  <q-page class="q-pa-md">
    <q-card>
      <q-card-section class="row items-center">
        <div class="text-h6 col">Logs</div>
        <q-btn flat color="primary" label="Refresh" @click="store.fetchLogs" />
        <q-btn flat color="secondary" label="Load More" class="q-ml-sm" @click="store.loadMoreLogs" />
      </q-card-section>
      <q-separator />
      <q-card-section>
        <q-list dense bordered>
          <q-item v-for="(row, idx) in store.logs.slice().reverse().slice(0, 200)" :key="idx">
            <q-item-section side>{{ row.level || "-" }}</q-item-section>
            <q-item-section>{{ row.message || "-" }}</q-item-section>
            <q-item-section side>{{ formatTs(row.ts) }}</q-item-section>
          </q-item>
        </q-list>
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup>
import { onMounted, onUnmounted } from "vue";
import { useRuntimeStore } from "../stores/runtime";

const store = useRuntimeStore();
let wsLogs = null;

function formatTs(ts) {
  if (!ts) return "-";
  return new Date(ts * 1000).toLocaleTimeString([], { hour12: false });
}

onMounted(async () => {
  await store.fetchLogs();
  wsLogs = store.connectLogs();
});

onUnmounted(() => {
  if (wsLogs) wsLogs.close();
});
</script>

