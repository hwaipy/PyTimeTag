<template>
  <div class="config-page">
    <div class="page-header">
      <h2 class="page-title">Device Configuration</h2>
      <button
        v-if="selectedDevice?.device_type === 'simulator'"
        class="settings-btn"
        title="Channel Settings"
        @click="openSettingsDialog"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
          <path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58a.49.49 0 0 0 .12-.61l-1.92-3.32a.488.488 0 0 0-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.484.484 0 0 0-.48-.41h-3.84a.484.484 0 0 0-.48.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96a.488.488 0 0 0-.59.22L2.74 8.87a.49.49 0 0 0 .12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58a.49.49 0 0 0-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.27.41.48.41h3.84c.24 0 .44-.17.48-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6A3.6 3.6 0 1 1 15.6 12 3.6 3.6 0 0 1 12 15.6z"/>
        </svg>
      </button>
    </div>
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

    <q-dialog v-model="settingsDialogOpen" @keydown.esc="closeSettingsDialog">
      <q-card class="settings-dialog">
        <q-card-section class="dialog-header">
          <div class="dialog-title">Channel Settings</div>
          <div class="dialog-subtitle">{{ selectedDevice?.serial_number }}</div>
        </q-card-section>

        <q-card-section class="dialog-body">
          <q-table
            class="settings-qtable"
            flat
            bordered
            dense
            :rows="dialogRows"
            :columns="dialogColumns"
            row-key="channel_id"
            hide-pagination
            :rows-per-page-options="[0]"
          >
            <template #body-cell-enabled="props">
              <q-td :props="props">
                <q-toggle v-model="dialogChannels[props.row.channel_id].enabled" dense color="green" />
              </q-td>
            </template>

            <template #body-cell-mode="props">
              <q-td :props="props">
                <q-select
                  v-model="dialogChannels[props.row.channel_id].mode"
                  :options="modeOptions"
                  dense
                  outlined
                  emit-value
                  map-options
                  options-dense
                  style="min-width: 100px"
                />
              </q-td>
            </template>

            <template #body-cell-rate="props">
              <q-td :props="props">
                <q-input
                  v-if="['Period','Random'].includes(dialogChannels[props.row.channel_id].mode)"
                  v-model.number="dialogChannels[props.row.channel_id].rate"
                  type="number"
                  dense
                  outlined
                  hide-bottom-space
                  suffix="cps"
                  style="width: 110px"
                />
                <q-input
                  v-else-if="dialogChannels[props.row.channel_id].mode === 'Pulse'"
                  v-model.number="dialogChannels[props.row.channel_id].pulse_count"
                  type="number"
                  dense
                  outlined
                  hide-bottom-space
                  label="Slots"
                  style="width: 80px"
                  class="q-mr-xs"
                />
                <span v-else class="text-grey-6">—</span>
              </q-td>
            </template>

            <template #body-cell-pulse_events="props">
              <q-td :props="props">
                <q-input
                  v-if="dialogChannels[props.row.channel_id].mode === 'Pulse'"
                  v-model.number="dialogChannels[props.row.channel_id].pulse_events"
                  type="number"
                  dense
                  outlined
                  hide-bottom-space
                  label="Events"
                  style="width: 80px"
                />
                <span v-else class="text-grey-6">—</span>
              </q-td>
            </template>

            <template #body-cell-threshold="props">
              <q-td :props="props">
                <q-input
                  v-model.number="dialogChannels[props.row.channel_id].threshold_voltage"
                  type="number"
                  dense
                  outlined
                  hide-bottom-space
                  step="0.1"
                  style="width: 90px"
                />
              </q-td>
            </template>

            <template #body-cell-dead_time="props">
              <q-td :props="props">
                <q-input
                  v-model.number="dialogChannels[props.row.channel_id].dead_time_ns"
                  type="number"
                  dense
                  outlined
                  hide-bottom-space
                  step="0.1"
                  suffix="ns"
                  style="width: 100px"
                />
              </q-td>
            </template>
          </q-table>
        </q-card-section>

        <q-card-actions align="right" class="dialog-actions">
          <q-btn flat label="Cancel" color="primary" @click="closeSettingsDialog" />
          <q-btn flat label="Save" color="primary" :loading="settingsSaving" @click="saveSettingsDialog" />
        </q-card-actions>
      </q-card>
    </q-dialog>
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

const settingsDialogOpen = ref(false);
const settingsSaving = ref(false);
const dialogChannels = ref([]);
const modeOptions = [
  { label: "Off", value: null },
  { label: "Period", value: "Period" },
  { label: "Random", value: "Random" },
  { label: "Pulse", value: "Pulse" },
];
const dialogColumns = [
  { name: "channel", label: "CH", field: "channel_id", align: "center", style: "width: 50px" },
  { name: "enabled", label: "On", field: "enabled", align: "center" },
  { name: "mode", label: "Mode", field: "mode", align: "center" },
  { name: "rate", label: "Rate / Slots", field: "rate", align: "center" },
  { name: "pulse_events", label: "Events", field: "pulse_events", align: "center" },
  { name: "threshold", label: "Thr (V)", field: "threshold_voltage", align: "center" },
  { name: "dead_time", label: "DT (ns)", field: "dead_time_ns", align: "center" },
];

const dialogRows = computed(() =>
  dialogChannels.value.map((ch) => ({
    channel_id: ch.channel_id,
  }))
);

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

function openSettingsDialog() {
  dialogChannels.value = channels.value.map((ch) => ({
    channel_id: ch.channel_id,
    enabled: ch.enabled !== false,
    mode: ch.mode || null,
    rate:
      ch.mode === "Period"
        ? Number(ch.period_count || 0)
        : Number(ch.random_count || 0),
    pulse_count: Number(ch.pulse_count || 0),
    pulse_events: Number(ch.pulse_events || 0),
    threshold_voltage: truncateTo(Number(ch.threshold_voltage || 0), 3),
    dead_time_ns: Number(((ch.dead_time_s || 0) * 1e9).toFixed(3)),
  }));
  settingsDialogOpen.value = true;
}

function closeSettingsDialog() {
  settingsDialogOpen.value = false;
}

async function saveSettingsDialog() {
  if (!selectedDevice.value) return;
  settingsSaving.value = true;
  try {
    const deviceType = selectedDevice.value.device_type;
    const serialNumber = selectedDevice.value.serial_number;
    await Promise.all(
      dialogChannels.value.map((ch) => {
        const payload = {
          enabled: ch.enabled,
          threshold_voltage: ch.threshold_voltage,
          dead_time_s: ch.dead_time_ns * 1e-9,
        };
        if (ch.mode) {
          payload.mode = ch.mode;
          if (ch.mode === "Period") {
            payload.period_count = Math.max(0, Math.round(ch.rate));
          } else if (ch.mode === "Random") {
            payload.random_count = Math.max(0, Math.round(ch.rate));
          } else if (ch.mode === "Pulse") {
            payload.pulse_count = Math.max(0, Math.round(ch.pulse_count));
            payload.pulse_events = Math.max(0, Math.round(ch.pulse_events));
          }
        } else {
          payload.mode = null;
        }
        return store.updateDeviceChannel(deviceType, serialNumber, ch.channel_id, payload);
      })
    );
    await loadChannels();
    closeSettingsDialog();
  } catch (err) {
    console.error("Failed to save channel settings:", err);
    alert(err.message || "Failed to save settings");
  } finally {
    settingsSaving.value = false;
  }
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

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding: 0 4px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  color: #1d1d1f;
  margin: 0;
}

.settings-btn {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  border: none;
  background: rgba(0, 113, 227, 0.08);
  color: #0071e3;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s ease;
}

.settings-btn:hover {
  background: rgba(0, 113, 227, 0.16);
}

.settings-dialog {
  min-width: 720px;
  max-width: 90vw;
  border-radius: 12px;
}

.dialog-header {
  padding-bottom: 8px;
}

.dialog-title {
  font-size: 16px;
  font-weight: 600;
  color: #1d1d1f;
}

.dialog-subtitle {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.5);
  margin-top: 2px;
}

.dialog-body {
  padding-top: 0;
  padding-bottom: 8px;
}

.dialog-actions {
  padding: 12px 20px;
}

.settings-qtable :deep(.q-table thead th) {
  padding: 8px 6px;
  font-size: 12px;
  font-weight: 600;
}

.settings-qtable :deep(.q-table tbody td) {
  padding: 6px;
}

.settings-qtable :deep(.q-table tbody tr) {
  height: 44px;
}
</style>
