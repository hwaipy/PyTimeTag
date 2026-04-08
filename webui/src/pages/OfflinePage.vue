<template>
  <q-page class="q-pa-md">
    <div class="row q-col-gutter-md">
      <div class="col-12">
        <q-card>
          <q-card-section class="row items-center">
            <div class="text-h6 col">DataBlocks</div>
            <q-btn flat color="primary" label="Refresh" @click="store.fetchDatablocks" />
          </q-card-section>
          <q-separator />
          <q-card-section>
            <q-table :rows="store.datablocks" :columns="columns" row-key="path" dense flat>
              <template #body-cell-actions="props">
                <q-td :props="props">
                  <q-btn size="sm" color="secondary" label="Offline Process" @click="runOffline(props.row.path)" />
                </q-td>
              </template>
            </q-table>
          </q-card-section>
        </q-card>
      </div>

      <div class="col-12">
        <q-card>
          <q-card-section class="row items-center">
            <div class="text-h6 col">Jobs</div>
            <q-btn flat color="primary" label="Refresh" @click="store.fetchJobs" />
          </q-card-section>
          <q-separator />
          <q-card-section>
            <q-table :rows="store.jobs" :columns="jobColumns" row-key="id" dense flat />
          </q-card-section>
        </q-card>
      </div>
    </div>
  </q-page>
</template>

<script setup>
import { onMounted } from "vue";
import { useRuntimeStore } from "../stores/runtime";

const store = useRuntimeStore();

const columns = [
  { name: "path", label: "Path", field: "path", align: "left" },
  { name: "size", label: "Size", field: "size", align: "right" },
  { name: "mtime", label: "MTime", field: "mtime", align: "right" },
  { name: "actions", label: "Actions", field: "actions", align: "left" },
];
const jobColumns = [
  { name: "id", label: "Job ID", field: "id", align: "left" },
  { name: "kind", label: "Kind", field: "kind", align: "left" },
  { name: "status", label: "Status", field: "status", align: "left" },
  { name: "updated_at", label: "Updated", field: "updated_at", align: "right" },
];

async function runOffline(path) {
  await store.processDatablock(path);
  await store.fetchJobs();
}

onMounted(async () => {
  await store.fetchDatablocks();
  await store.fetchJobs();
});
</script>

