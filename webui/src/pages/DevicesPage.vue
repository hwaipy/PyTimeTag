<template>
  <div class="config-page">
    <div class="table-container">
      <table class="apple-table channels-table">
        <thead>
          <tr>
            <th>Channel</th>
            <th style="text-align: right;">Count Rate</th>
            <th style="text-align: right;">Threshold</th>
            <th style="text-align: right;">Dead Time</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="ch in channels" :key="ch.channel_id">
            <td><span class="channel-id">CH{{ ch.channel_id }}</span></td>
            <td style="text-align: right;"><span class="channel-value">{{ formatCountRate(ch) }}</span></td>
            <td style="text-align: right;"><span class="channel-value">{{ formatVoltage(ch.threshold_voltage) }}</span></td>
            <td style="text-align: right;"><span class="channel-value">{{ formatTime(ch.dead_time_s) }}</span></td>
          </tr>
          <tr v-if="channels.length === 0">
            <td colspan="4" class="empty-row">No channel data</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from "vue";
import { useRuntimeStore } from "../stores/runtime";

const store = useRuntimeStore();
const channels = ref([]);

function pickDefaultDevice(devices) {
  if (!Array.isArray(devices) || devices.length === 0) return null;
  return devices.find((device) => device.device_type === "simulator") || devices[0];
}

const selectedDevice = computed(() => store.currentDevice || pickDefaultDevice(store.devices));

function formatTime(seconds) {
  if (!seconds || seconds === 0) return "-";
  if (seconds >= 1) return `${seconds.toFixed(3)} s`;
  if (seconds >= 0.001) return `${(seconds * 1000).toFixed(2)} ms`;
  if (seconds >= 0.000001) return `${(seconds * 1000000).toFixed(1)} us`;
  return `${(seconds * 1000000000).toFixed(0)} ns`;
}

function formatVoltage(voltage) {
  if (voltage === undefined || voltage === null) return "-";
  return `${voltage > 0 ? "+" : ""}${voltage.toFixed(2)} V`;
}

function formatCountRate(channel) {
  if (channel.mode === "Period" && Number.isFinite(channel.period_count)) {
    return `${channel.period_count} Hz`;
  }
  if (channel.mode === "Random" && Number.isFinite(channel.random_count)) {
    return `${channel.random_count} Hz`;
  }
  return "-";
}

async function loadChannels() {
  if (!selectedDevice.value) {
    channels.value = [];
    return;
  }
  try {
    const result = await store.fetchDeviceChannels(
      selectedDevice.value.device_type,
      selectedDevice.value.serial_number
    );
    channels.value = result.channels || [];
  } catch (err) {
    console.error("Failed to load channels:", err);
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
});
</script>

<style scoped>
@import "../css/apple-design.css";

.config-page {
  padding-top: 8px;
}

.table-container {
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.06);
}

.channels-table {
  font-size: 14px;
}

.channel-id {
  font-family: "SF Mono", Monaco, monospace;
  font-size: 13px;
  font-weight: 500;
  color: #1d1d1f;
}

.channel-value {
  font-family: "SF Mono", Monaco, monospace;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.72);
}

.empty-row {
  text-align: center;
  color: rgba(0, 0, 0, 0.5);
  padding: 28px 12px;
}
</style>
