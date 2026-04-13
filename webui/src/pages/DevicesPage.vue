<template>
  <div class="devices-page">
    <!-- Header Section -->
    <section class="apple-section-dark hero-section">
      <h1 class="apple-display-hero">Devices</h1>
      <p class="apple-sub-heading" style="color: rgba(255,255,255,0.8); margin-top: 8px;">
        Select and configure time-tagging devices
      </p>
    </section>

    <!-- Device Selection -->
    <section class="apple-section">
      <div class="apple-card device-selector">
        <div class="apple-card-header">
          <h2 class="apple-card-title">Select Device</h2>
        </div>
        <div class="apple-card-body">
          <div class="device-dropdown">
            <button class="apple-btn apple-btn-light dropdown-trigger" @click="showDeviceList = !showDeviceList">
              <span v-if="selectedDevice">{{ selectedDevice.serial_number }}</span>
              <span v-else>Choose a device...</span>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" :style="{ transform: showDeviceList ? 'rotate(180deg)' : '' }">
                <path d="M7 10l5 5 5-5z"/>
              </svg>
            </button>

            <div v-if="showDeviceList" class="dropdown-menu">
              <div
                v-for="device in availableDevices"
                :key="device.unique_id"
                class="dropdown-item"
                :class="{ active: selectedDevice?.unique_id === device.unique_id }"
                @click="selectDevice(device)"
              >
                <div class="device-option">
                  <span class="device-type-tag">{{ device.device_type }}</span>
                  <span class="device-serial">{{ device.serial_number }}</span>
                  <span class="device-channels">{{ device.channel_count }}ch</span>
                </div>
              </div>
              <div v-if="availableDevices.length === 0" class="dropdown-empty">
                No devices available
              </div>
            </div>
          </div>

          <div class="device-actions">
            <template v-if="selectedDevice">
              <button
                class="apple-btn"
                :class="selectedDevice.running ? 'apple-btn-danger' : 'apple-btn-primary'"
                @click="toggleDevice"
              >
                {{ selectedDevice.running ? 'Stop' : 'Start' }}
              </button>
            </template>
            <div class="dropdown" style="position: relative;">
              <button class="apple-btn apple-btn-outline" @click="showCreateMenu = !showCreateMenu">
                + New Device
              </button>
              <div v-if="showCreateMenu" class="dropdown-menu" style="right: 0; left: auto; min-width: 200px;">
                <div class="dropdown-item" @click="createSimulator">
                  <div class="device-option">
                    <span class="device-type-tag">16ch</span>
                    <span>Standard Simulator</span>
                  </div>
                </div>
                <div class="dropdown-item" @click="createSwabianSimulator">
                  <div class="device-option">
                    <span class="device-type-tag" style="background: rgba(0,113,227,0.1); color: #0071e3;">8ch</span>
                    <span>Swabian Simulator</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Channel Information -->
    <section v-if="selectedDevice && channels.length > 0" class="apple-section">
      <div class="apple-card">
        <div class="apple-card-header" style="display: flex; align-items: center; justify-content: space-between;">
          <h2 class="apple-card-title">Channel Configuration</h2>
          <span class="apple-caption" style="color: rgba(0,0,0,0.5);">
            {{ channels.length }} channels
          </span>
        </div>
        <div class="apple-card-body" style="padding: 0;">
          <div class="table-container">
            <table class="apple-table channels-table">
              <thead>
                <tr>
                  <th>Channel</th>
                  <th>Mode</th>
                  <th style="text-align: right;">Dead Time</th>
                  <th style="text-align: right;">Threshold</th>
                  <th style="text-align: center;">Status</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="ch in channels"
                  :key="ch.channel_id"
                  class="channel-row"
                  @click="openChannelEdit(ch)"
                >
                  <td>
                    <span class="channel-id">CH{{ ch.channel_id }}</span>
                  </td>
                  <td>
                    <span class="channel-mode" :class="ch.mode?.toLowerCase()">
                      {{ ch.mode || 'Off' }}
                    </span>
                  </td>
                  <td style="text-align: right;">
                    <span class="channel-value">{{ formatTime(ch.dead_time_s) }}</span>
                  </td>
                  <td style="text-align: right;">
                    <span class="channel-value">{{ formatVoltage(ch.threshold_voltage) }}</span>
                  </td>
                  <td style="text-align: center;">
                    <span class="channel-status" :class="{ enabled: ch.enabled }">
                      {{ ch.enabled ? 'On' : 'Off' }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>

    <!-- Channel Edit Modal -->
    <transition name="fade">
      <div v-if="editingChannel" class="apple-modal-overlay" @click="closeEdit">
        <div class="apple-modal" @click.stop>
          <div class="apple-modal-header">
            <h3 class="apple-card-title">Configure Channel {{ editingChannel.channel_id }}</h3>
            <button class="apple-modal-close" @click="closeEdit">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
              </svg>
            </button>
          </div>
          <div class="apple-modal-body">
            <div class="form-group">
              <label class="form-label">Mode</label>
              <select v-model="editForm.mode" class="apple-input">
                <option value="">Off</option>
                <option value="Period">Period</option>
                <option value="Random">Random</option>
                <option value="Pulse">Pulse</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">Dead Time (seconds)</label>
              <input
                v-model.number="editForm.dead_time_s"
                type="number"
                step="1e-9"
                class="apple-input"
                placeholder="e.g., 0.000001"
              />
            </div>

            <div class="form-group">
              <label class="form-label">Threshold Voltage (V)</label>
              <input
                v-model.number="editForm.threshold_voltage"
                type="number"
                step="0.1"
                class="apple-input"
                placeholder="e.g., -0.5"
              />
            </div>

            <div class="form-group">
              <label class="form-check">
                <input v-model="editForm.enabled" type="checkbox" />
                <span>Enabled</span>
              </label>
            </div>

            <div v-if="editForm.mode === 'Period'" class="form-group">
              <label class="form-label">Period Count (Hz)</label>
              <input
                v-model.number="editForm.period_count"
                type="number"
                class="apple-input"
                placeholder="Events per second"
              />
            </div>

            <div v-if="editForm.mode === 'Random'" class="form-group">
              <label class="form-label">Random Count (Hz)</label>
              <input
                v-model.number="editForm.random_count"
                type="number"
                class="apple-input"
                placeholder="Events per second"
              />
            </div>
          </div>
          <div class="apple-modal-footer">
            <button class="apple-btn apple-btn-light" @click="closeEdit">Cancel</button>
            <button class="apple-btn apple-btn-primary" @click="saveChannel">Save</button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive } from "vue";
import { useRuntimeStore } from "../stores/runtime";

const store = useRuntimeStore();

const availableDevices = ref([]);
const selectedDevice = ref(null);
const channels = ref([]);
const showDeviceList = ref(false);
const showCreateMenu = ref(false);
const editingChannel = ref(null);

const editForm = reactive({
  mode: "",
  dead_time_s: 0,
  threshold_voltage: 0,
  enabled: true,
  period_count: 0,
  random_count: 0,
});

function formatTime(seconds) {
  if (!seconds || seconds === 0) return "-";
  if (seconds >= 1) return `${seconds.toFixed(3)} s`;
  if (seconds >= 0.001) return `${(seconds * 1000).toFixed(2)} ms`;
  if (seconds >= 0.000001) return `${(seconds * 1000000).toFixed(1)} µs`;
  return `${(seconds * 1000000000).toFixed(0)} ns`;
}

function formatVoltage(voltage) {
  if (voltage === undefined || voltage === null) return "-";
  return `${voltage > 0 ? '+' : ''}${voltage.toFixed(2)} V`;
}

async function loadDevices() {
  await store.fetchDevices();
  availableDevices.value = store.devices;
}

async function selectDevice(device) {
  selectedDevice.value = device;
  showDeviceList.value = false;
  await loadChannels();
}

async function loadChannels() {
  if (!selectedDevice.value) return;
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

async function toggleDevice() {
  if (!selectedDevice.value) return;
  const { device_type, serial_number } = selectedDevice.value;
  try {
    if (selectedDevice.value.running) {
      await store.stopDevice(device_type, serial_number);
    } else {
      await store.startDevice(device_type, serial_number);
    }
    await loadDevices();
  } catch (err) {
    alert(err.message);
  }
}

async function createSimulator() {
  showCreateMenu.value = false;
  const serial = `SIM-${Date.now().toString(36).toUpperCase()}`;
  try {
    await store.createDevice("simulator", serial, 16);
    await loadDevices();
    const newDevice = availableDevices.value.find(d => d.serial_number === serial);
    if (newDevice) {
      await selectDevice(newDevice);
    }
  } catch (err) {
    alert(err.message);
  }
}

async function createSwabianSimulator() {
  showCreateMenu.value = false;
  const serial = `SWABIAN-${Date.now().toString(36).toUpperCase()}`;
  try {
    await store.createDevice("swabian_simulator", serial, 8);
    await loadDevices();
    const newDevice = availableDevices.value.find(d => d.serial_number === serial);
    if (newDevice) {
      await selectDevice(newDevice);
    }
  } catch (err) {
    alert(err.message);
  }
}

function openChannelEdit(ch) {
  editingChannel.value = ch;
  editForm.mode = ch.mode || "";
  editForm.dead_time_s = ch.dead_time_s || 0;
  editForm.threshold_voltage = ch.threshold_voltage || 0;
  editForm.enabled = ch.enabled !== false;
  editForm.period_count = ch.period_count || 0;
  editForm.random_count = ch.random_count || 0;
}

function closeEdit() {
  editingChannel.value = null;
}

async function saveChannel() {
  if (!editingChannel.value || !selectedDevice.value) return;

  const config = {
    mode: editForm.mode || null,
    dead_time_s: editForm.dead_time_s,
    threshold_voltage: editForm.threshold_voltage,
    enabled: editForm.enabled,
  };

  if (editForm.mode === "Period") {
    config.period_count = editForm.period_count;
  } else if (editForm.mode === "Random") {
    config.random_count = editForm.random_count;
  }

  try {
    await store.updateDeviceChannel(
      selectedDevice.value.device_type,
      selectedDevice.value.serial_number,
      editingChannel.value.channel_id,
      config
    );
    await loadChannels();
    closeEdit();
  } catch (err) {
    alert(err.message);
  }
}

onMounted(() => {
  loadDevices();
});
</script>

<style scoped>
@import "../css/apple-design.css";

.devices-page {
  padding-bottom: 48px;
}

.hero-section {
  text-align: center;
  padding: 48px 24px;
  margin-bottom: 48px;
}

.device-selector {
  background: white;
}

.device-dropdown {
  position: relative;
  margin-bottom: 16px;
}

.dropdown-trigger {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.dropdown-menu {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 4px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.15);
  z-index: 100;
  max-height: 300px;
  overflow-y: auto;
}

.dropdown-item {
  padding: 12px 16px;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.dropdown-item:hover,
.dropdown-item.active {
  background-color: rgba(0, 113, 227, 0.08);
}

.dropdown-empty {
  padding: 24px;
  text-align: center;
  color: rgba(0,0,0,0.5);
  font-size: 14px;
}

.device-option {
  display: flex;
  align-items: center;
  gap: 12px;
}

.device-type-tag {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  padding: 2px 8px;
  background: rgba(0,0,0,0.05);
  border-radius: 4px;
  color: rgba(0,0,0,0.6);
}

.device-type-tag.simulator {
  background: rgba(76, 175, 80, 0.1);
  color: #4caf50;
}

.device-type-tag.swabian_simulator {
  background: rgba(0, 113, 227, 0.1);
  color: #0071e3;
}

.device-serial {
  font-weight: 500;
  flex: 1;
}

.device-channels {
  font-size: 13px;
  color: rgba(0,0,0,0.5);
}

.device-actions {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}

.channels-table {
  font-size: 14px;
}

.channel-row {
  cursor: pointer;
}

.channel-id {
  font-family: "SF Mono", Monaco, monospace;
  font-size: 13px;
  font-weight: 500;
  color: #1d1d1f;
}

.channel-mode {
  display: inline-block;
  font-size: 12px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 4px;
  text-transform: uppercase;
}

.channel-mode.period {
  background: rgba(0, 113, 227, 0.1);
  color: #0071e3;
}

.channel-mode.random {
  background: rgba(76, 175, 80, 0.1);
  color: #4caf50;
}

.channel-mode.pulse {
  background: rgba(255, 152, 0, 0.1);
  color: #ff9800;
}

.channel-value {
  font-family: "SF Mono", Monaco, monospace;
  font-size: 13px;
  color: rgba(0,0,0,0.7);
}

.channel-status {
  font-size: 12px;
  font-weight: 500;
  color: rgba(0,0,0,0.4);
}

.channel-status.enabled {
  color: #4caf50;
}

.form-check {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  cursor: pointer;
}

.form-check input[type="checkbox"] {
  width: 18px;
  height: 18px;
  accent-color: #0071e3;
}

.apple-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
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

@media (max-width: 768px) {
  .hero-section .apple-display-hero {
    font-size: 40px;
  }

  .device-actions {
    flex-direction: column;
  }

  .channels-table {
    font-size: 12px;
  }
}
</style>
