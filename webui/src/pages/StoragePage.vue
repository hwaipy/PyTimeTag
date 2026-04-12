<template>
  <q-page class="q-pa-md">
    <div class="row q-col-gutter-md">
      <div class="col-12 col-md-4">
        <q-card>
          <q-card-section class="row items-center">
            <div class="text-h6 col">Collections</div>
            <q-btn flat color="primary" label="Refresh" @click="loadCollections" />
          </q-card-section>
          <q-separator />
          <q-card-section>
            <q-list bordered separator>
              <q-item
                v-for="col in collections"
                :key="col"
                clickable
                :active="selectedCollection === col"
                active-class="bg-primary text-white"
                @click="selectCollection(col)"
              >
                <q-item-section>
                  <q-item-label>{{ col }}</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-btn
                    flat
                    round
                    size="sm"
                    icon="delete"
                    :color="selectedCollection === col ? 'white' : 'negative'"
                    @click.stop="deleteCollection(col)"
                  />
                </q-item-section>
              </q-item>
            </q-list>
            <div v-if="collections.length === 0" class="text-grey q-pa-md text-center">
              No collections found
            </div>
          </q-card-section>
        </q-card>
      </div>

      <div class="col-12 col-md-8">
        <q-card v-if="selectedCollection">
          <q-card-section class="row items-center">
            <div class="text-h6 col">{{ selectedCollection }}</div>
            <q-btn flat color="primary" label="Refresh" @click="loadItems" />
            <q-btn flat color="secondary" label="Load More" class="q-ml-sm" @click="loadMore" />
          </q-card-section>
          <q-separator />
          <q-card-section>
            <q-table
              :rows="items"
              :columns="columns"
              row-key="_id"
              dense
              flat
              :loading="isLoading"
            >
              <template #body-cell-data="props">
                <q-td :props="props">
                  <q-btn
                    flat
                    size="sm"
                    color="primary"
                    label="View"
                    @click="showData(props.row)"
                  />
                </q-td>
              </template>
              <template #body-cell-actions="props">
                <q-td :props="props">
                  <q-btn
                    flat
                    size="sm"
                    color="negative"
                    icon="delete"
                    @click="deleteItem(props.row._id)"
                  />
                </q-td>
              </template>
            </q-table>
            <div v-if="items.length === 0 && !isLoading" class="text-grey q-pa-md text-center">
              No items in this collection
            </div>
          </q-card-section>
        </q-card>
        <q-card v-else class="flex flex-center" style="min-height: 300px">
          <q-card-section class="text-grey text-center">
            <div class="text-h6">Select a collection to view data</div>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <!-- Data Detail Dialog -->
    <q-dialog v-model="dataDialogOpen" maximized>
      <q-card>
        <q-card-section class="row items-center">
          <div class="text-h6">Data Detail</div>
          <q-space />
          <q-btn flat round icon="close" @click="dataDialogOpen = false" />
        </q-card-section>
        <q-separator />
        <q-card-section>
          <pre>{{ JSON.stringify(selectedData, null, 2) }}</pre>
        </q-card-section>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useQuasar } from "quasar";
import { useRuntimeStore } from "../stores/runtime";

const $q = useQuasar();
const store = useRuntimeStore();

const collections = ref([]);
const selectedCollection = ref("");
const items = ref([]);
const limit = ref(50);
const isLoading = ref(false);
const dataDialogOpen = ref(false);
const selectedData = ref({});

const columns = [
  { name: "_id", label: "ID", field: "_id", align: "left", style: "max-width: 200px", classes: "ellipsis" },
  { name: "FetchTime", label: "Fetch Time", field: "FetchTime", align: "left" },
  { name: "RecordTime", label: "Record Time", field: "RecordTime", align: "left" },
  { name: "data", label: "Data", field: "Data", align: "center" },
  { name: "actions", label: "Actions", field: "actions", align: "center" },
];

async function loadCollections() {
  try {
    collections.value = await store.fetchStorageCollections();
  } catch (err) {
    $q.notify({ type: "negative", message: `Failed to load collections: ${err.message}` });
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
    $q.notify({ type: "negative", message: `Failed to load items: ${err.message}` });
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
  $q.dialog({
    title: "Confirm Delete",
    message: `Delete item ${itemId.slice(0, 8)}...?`,
    cancel: true,
    persistent: true,
  }).onOk(async () => {
    try {
      await store.deleteStorageItem(selectedCollection.value, itemId);
      $q.notify({ type: "positive", message: "Item deleted" });
      await loadItems();
    } catch (err) {
      $q.notify({ type: "negative", message: `Failed to delete: ${err.message}` });
    }
  });
}

async function deleteCollection(col) {
  $q.dialog({
    title: "Confirm Delete",
    message: `Delete entire collection "${col}"? This cannot be undone.`,
    cancel: true,
    persistent: true,
    color: "negative",
  }).onOk(async () => {
    $q.notify({ type: "warning", message: "Collection delete not implemented yet" });
  });
}

onMounted(() => {
  loadCollections();
});
</script>

<style scoped>
pre {
  background: #f5f5f5;
  padding: 16px;
  border-radius: 4px;
  overflow: auto;
  max-height: 80vh;
}
</style>
