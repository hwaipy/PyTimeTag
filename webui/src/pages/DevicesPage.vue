<template>
  <div class="config-page">
    <q-table
      class="config-qtable config-qtable-b"
      flat
      bordered
      :rows="tableRows"
      :columns="tableColumns"
      row-key="channel_id"
      hide-pagination
      :rows-per-page-options="[0]"
      no-data-label="No channel data"
    >
      <template #body-cell-channel="props">
        <q-td :props="props">
          <span class="channel-id">{{ formatChannelLabel(props.row.channel) }}</span>
        </q-td>
      </template>

      <template #body-cell-count_rate="props">
        <q-td :props="props">
          <span class="channel-value">{{ props.row.count_rate }}</span>
        </q-td>
      </template>

      <template #body-cell-threshold="props">
        <q-td :props="props">
          <div class="cell-editor-shell">
            <q-input
              v-if="editingCell === cellKey(props.row.channel_id, 'threshold_voltage')"
              v-model.number="editValues[props.row.channel_id].threshold_voltage"
              class="cell-input"
              dense
              outlined
              hide-bottom-space
              type="number"
              step="0.01"
              :min="thresholdRange[0]"
              :max="thresholdRange[1]"
              autofocus
              :data-edit-key="cellKey(props.row.channel_id, 'threshold_voltage')"
              :loading="isCellSaving(props.row.channel_id, 'threshold_voltage')"
              @blur="finishEdit(props.row.channel_id, 'threshold_voltage')"
              @keyup.enter="finishEdit(props.row.channel_id, 'threshold_voltage')"
              @keyup.esc.stop.prevent="cancelEdit(props.row.channel_id, 'threshold_voltage')"
              @keydown.tab.stop.prevent="handleTabNavigate(props.row.channel_id, 'threshold_voltage', $event)"
            />
            <span
              v-else
              class="channel-value editable-cell cell-display-value"
              @click.stop="beginEdit(props.row.channel_id, 'threshold_voltage')"
            >
              {{ formatThresholdDisplay(editValues[props.row.channel_id]?.threshold_voltage) }}
            </span>
          </div>
        </q-td>
      </template>

      <template #body-cell-dead_time="props">
        <q-td :props="props">
          <div class="cell-editor-shell">
            <q-input
              v-if="editingCell === cellKey(props.row.channel_id, 'dead_time_ns')"
              v-model.number="editValues[props.row.channel_id].dead_time_ns"
              class="cell-input"
              dense
              outlined
              hide-bottom-space
              type="number"
              step="0.1"
              :min="deadTimeRangeNs[0]"
              :max="deadTimeRangeNs[1]"
              suffix="ns"
              autofocus
              :data-edit-key="cellKey(props.row.channel_id, 'dead_time_ns')"
              :loading="isCellSaving(props.row.channel_id, 'dead_time_ns')"
              @blur="finishEdit(props.row.channel_id, 'dead_time_ns')"
              @keyup.enter="finishEdit(props.row.channel_id, 'dead_time_ns')"
              @keyup.esc.stop.prevent="cancelEdit(props.row.channel_id, 'dead_time_ns')"
              @keydown.tab.stop.prevent="handleTabNavigate(props.row.channel_id, 'dead_time_ns', $event)"
            />
            <span
              v-else
              class="channel-value editable-cell cell-display-value"
              @click.stop="beginEdit(props.row.channel_id, 'dead_time_ns')"
            >
              {{ formatDeadTimeDisplay(editValues[props.row.channel_id]?.dead_time_ns) }}
            </span>
          </div>
        </q-td>
      </template>
    </q-table>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from "vue";
import { useRuntimeStore } from "../stores/runtime";

const store = useRuntimeStore();
const channels = ref([]);
const editValues = ref({});
const savingCells = ref({});
const editingCell = ref("");
const thresholdRange = ref([-2.0, 2.0]);
const deadTimeRangeNs = ref([0.0, 1e6]);
const tableColumns = [
  { name: "channel", label: "Channel", field: "channel", align: "left" },
  { name: "count_rate", label: "Count Rate", field: "count_rate", align: "right" },
  { name: "threshold", label: "Threshold", field: "threshold", align: "right" },
  { name: "dead_time", label: "Dead Time", field: "dead_time", align: "right" },
];

function truncateTo(value, digits) {
  const factor = 10 ** digits;
  return Math.trunc(value * factor) / factor;
}

function clampToRange(value, low, high) {
  return Math.min(Math.max(value, low), high);
}

function pickDefaultDevice(devices) {
  if (!Array.isArray(devices) || devices.length === 0) return null;
  return devices.find((device) => device.device_type === "simulator") || devices[0];
}

const selectedDevice = computed(() => store.currentDevice || pickDefaultDevice(store.devices));
let refreshInterval = null;

function formatCountRate(channel) {
  if ("count_rate" in channel && Number.isFinite(channel.count_rate)) {
    return `${Math.round(channel.count_rate)} cps`;
  }
  if (channel.mode === "Period" && Number.isFinite(channel.period_count)) {
    return `${channel.period_count} cps`;
  }
  if (channel.mode === "Random" && Number.isFinite(channel.random_count)) {
    return `${channel.random_count} cps`;
  }
  return "-";
}

function formatThresholdDisplay(voltage) {
  if (!Number.isFinite(voltage)) return "-";
  const truncated = truncateTo(Number(voltage), 3);
  return `${truncated > 0 ? "+" : ""}${truncated.toFixed(3)} V`;
}

function formatDeadTimeDisplay(deadTimeNs) {
  if (!Number.isFinite(deadTimeNs)) return "-";
  return `${Number(deadTimeNs).toFixed(1)} ns`;
}

function formatChannelLabel(channel) {
  return `CH ${String(channel).padStart(2, "0")}`;
}

const tableRows = computed(() =>
  channels.value.map((ch) => ({
    channel_id: ch.channel_id,
    channel: ch.channel_id,
    count_rate: formatCountRate(ch),
    threshold: ch.threshold_voltage,
    dead_time: ch.dead_time_s,
  }))
);

function cellKey(channelId, field) {
  return `${channelId}:${field}`;
}

const editableFieldOrder = ["threshold_voltage", "dead_time_ns"];

function getEditableCellSequence() {
  const sequence = [];
  for (const row of tableRows.value) {
    for (const field of editableFieldOrder) {
      sequence.push(cellKey(row.channel_id, field));
    }
  }
  return sequence;
}

function findAdjacentEditableCell(currentKey, isBackward) {
  const sequence = getEditableCellSequence();
  const index = sequence.indexOf(currentKey);
  if (index < 0) return "";
  const nextIndex = isBackward ? index - 1 : index + 1;
  if (nextIndex < 0 || nextIndex >= sequence.length) return "";
  return sequence[nextIndex];
}

async function focusEditableCell(targetKey) {
  await nextTick();
  const escaped = window.CSS?.escape ? window.CSS.escape(targetKey) : targetKey.replace(/"/g, '\\"');
  const input = document.querySelector(`[data-edit-key="${escaped}"] input`);
  if (input instanceof HTMLInputElement) {
    input.focus();
    input.select();
  }
}

function isCellSaving(channelId, field) {
  return Boolean(savingCells.value[cellKey(channelId, field)]);
}

function beginEdit(channelId, field) {
  editingCell.value = cellKey(channelId, field);
}

async function finishEdit(channelId, field) {
  const key = cellKey(channelId, field);
  if (editingCell.value !== key) return;
  editingCell.value = "";
  await saveChannelValue(channelId, field);
}

function cancelEdit(channelId, field) {
  const key = cellKey(channelId, field);
  if (editingCell.value !== key) return;
  editingCell.value = "";
  syncEditValuesFromChannels();
}

async function handleTabNavigate(channelId, field, event) {
  const currentKey = cellKey(channelId, field);
  if (editingCell.value !== currentKey) return;

  const targetKey = findAdjacentEditableCell(currentKey, Boolean(event.shiftKey));
  editingCell.value = "";
  await saveChannelValue(channelId, field);

  if (!targetKey) return;
  editingCell.value = targetKey;
  await focusEditableCell(targetKey);
}

function syncEditValuesFromChannels() {
  const next = {};
  let thresholdBounds = thresholdRange.value;
  let deadTimeBoundsNs = deadTimeRangeNs.value;
  for (const ch of channels.value) {
    next[ch.channel_id] = {
      threshold_voltage: truncateTo(Number(ch.threshold_voltage ?? 0), 3),
      dead_time_ns: Number(((ch.dead_time_s ?? 0) * 1e9).toFixed(3)),
    };
    if (Array.isArray(ch.threshold_voltage_range) && ch.threshold_voltage_range.length === 2) {
      thresholdBounds = [Number(ch.threshold_voltage_range[0]), Number(ch.threshold_voltage_range[1])];
    }
    if (Array.isArray(ch.dead_time_s_range) && ch.dead_time_s_range.length === 2) {
      deadTimeBoundsNs = [Number(ch.dead_time_s_range[0]) * 1e9, Number(ch.dead_time_s_range[1]) * 1e9];
    }
  }
  editValues.value = next;
  thresholdRange.value = thresholdBounds;
  deadTimeRangeNs.value = deadTimeBoundsNs;
}

async function saveChannelValue(channelId, field) {
  if (!selectedDevice.value) return;
  if (isCellSaving(channelId, field)) return;

  const row = editValues.value[channelId];
  if (!row) return;

  const payload = {};
  if (field === "threshold_voltage") {
    const value = Number(row.threshold_voltage);
    if (!Number.isFinite(value)) {
      syncEditValuesFromChannels();
      return;
    }
    const [low, high] = thresholdRange.value;
    const clampedValue = clampToRange(value, low, high);
    const truncatedValue = truncateTo(clampedValue, 3);
    row.threshold_voltage = truncatedValue;
    payload.threshold_voltage = truncatedValue;
  } else if (field === "dead_time_ns") {
    const value = Number(row.dead_time_ns);
    if (!Number.isFinite(value)) {
      syncEditValuesFromChannels();
      return;
    }
    const [lowNs, highNs] = deadTimeRangeNs.value;
    const clampedValueNs = clampToRange(value, lowNs, highNs);
    row.dead_time_ns = clampedValueNs;
    payload.dead_time_s = clampedValueNs * 1e-9;
  } else {
    return;
  }

  const key = cellKey(channelId, field);
  savingCells.value = { ...savingCells.value, [key]: true };
  try {
    const result = await store.updateDeviceChannel(
      selectedDevice.value.device_type,
      selectedDevice.value.serial_number,
      channelId,
      payload
    );
    const channel = channels.value.find((ch) => ch.channel_id === channelId);
    if (channel) {
      const config = result?.config || payload;
      if (config.threshold_voltage !== undefined) {
        channel.threshold_voltage = config.threshold_voltage;
      }
      if (config.dead_time_s !== undefined) {
        channel.dead_time_s = config.dead_time_s;
      }
    }
    syncEditValuesFromChannels();
  } catch (err) {
    console.error("Failed to save channel config:", err);
    syncEditValuesFromChannels();
  } finally {
    const next = { ...savingCells.value };
    delete next[key];
    savingCells.value = next;
  }
}

let loadChannelsVersion = 0;

async function loadChannels() {
  if (!selectedDevice.value) {
    channels.value = [];
    return;
  }
  const device = selectedDevice.value;
  const version = ++loadChannelsVersion;
  try {
    const result = await store.fetchDeviceChannels(
      device.device_type,
      device.serial_number
    );
    if (version !== loadChannelsVersion) return;
    channels.value = result.channels || [];
    syncEditValuesFromChannels();
  } catch (err) {
    if (version === loadChannelsVersion) {
      console.error("Failed to load channels:", err);
    }
  }
}

watch(
  selectedDevice,
  async () => {
    await loadChannels();
  }
);

onMounted(async () => {
  await store.fetchDevices();
  if (!store.currentDevice) {
    store.currentDevice = pickDefaultDevice(store.devices);
  }
  await loadChannels();
  refreshInterval = window.setInterval(() => {
    loadChannels();
  }, 1000);
});

onUnmounted(() => {
  if (refreshInterval !== null) {
    window.clearInterval(refreshInterval);
    refreshInterval = null;
  }
});
</script>

<style scoped>
@import "../css/apple-design.css";

.config-page {
  padding-top: 8px;
}

.config-qtable {
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.06);
}

.config-qtable :deep(.q-table thead th) {
  padding: 12px 18px;
  font-size: 13px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.7);
}

.config-qtable :deep(.q-table tbody td) {
  padding: 14px 18px;
}

.config-qtable :deep(.q-table tbody tr) {
  height: 47px;
}

.config-qtable-b {
  border-color: rgba(0, 0, 0, 0.14);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.09);
}

.config-qtable-b :deep(.q-table thead tr) {
  background: #f3f4f8;
}

.config-qtable-b :deep(.q-table thead th) {
  color: rgba(0, 0, 0, 0.82);
}

.config-qtable-b :deep(.q-table tbody td) {
  border-bottom: 1px solid rgba(0, 0, 0, 0.14);
}

.config-qtable-b :deep(.q-table tbody tr:hover) {
  background: #eef3ff;
}

.channel-id {
  font-family: "SF Mono", Monaco, monospace;
  font-size: 16px;
  font-weight: 700;
  color: #1d1d1f;
  white-space: pre;
}

.channel-value {
  font-family: "SF Mono", Monaco, monospace;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.72);
}

.cell-input {
  width: 100%;
}

.cell-editor-shell {
  width: 132px;
  height: 38px;
  margin-left: auto;
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.cell-input :deep(.q-field__control) {
  height: 38px;
  min-height: 38px;
}

.cell-input :deep(input) {
  font-family: "SF Mono", Monaco, monospace;
  font-size: 13px;
  text-align: right;
  -moz-appearance: textfield;
  appearance: textfield;
}

.cell-input :deep(input::-webkit-outer-spin-button),
.cell-input :deep(input::-webkit-inner-spin-button) {
  -webkit-appearance: none;
  margin: 0;
}

.cell-input :deep(.q-field__native),
.cell-input :deep(.q-field__prefix),
.cell-input :deep(.q-field__suffix),
.cell-input :deep(.q-field__append),
.cell-input :deep(.q-field__prepend) {
  height: 38px;
  min-height: 38px;
  align-items: center;
}

.cell-input :deep(.q-field__bottom) {
  display: none;
}

.editable-cell {
  cursor: text;
  user-select: none;
}

.cell-display-value {
  height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  text-align: right;
}
</style>
