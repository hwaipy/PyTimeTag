<template>
  <div class="device-selector">
    <div class="device-selector-main" ref="selectorRef">
      <button
        class="device-selector-trigger"
        :class="{ open: isOpen }"
        @click="toggleDropdown"
      >
        <div class="device-info">
          <span class="device-name">{{ displayName }}</span>
          <span class="device-serial">{{ displaySerial }}</span>
        </div>
        <svg
          class="chevron"
          width="10"
          height="10"
          viewBox="0 0 24 24"
          fill="currentColor"
          :style="{ transform: isOpen ? 'rotate(180deg)' : '' }"
        >
          <path d="M7 10l5 5 5-5z"/>
        </svg>
      </button>

      <transition name="dropdown">
        <div v-if="isOpen" class="device-dropdown-menu">
          <div
            v-for="device in store.devices"
            :key="device.unique_id"
            class="device-dropdown-item"
            :class="{ active: isCurrent(device) }"
            @click="selectDevice(device)"
          >
            <div class="device-item-info">
              <span class="device-item-name">{{ device.manufacturer || device.device_type }}</span>
              <span class="device-item-serial">{{ device.serial_number }}</span>
            </div>
            <span v-if="device.running" class="device-status-dot"></span>
          </div>
          <div v-if="store.devices.length === 0" class="device-dropdown-empty">
            No devices available
          </div>
        </div>
      </transition>
    </div>

    <button
      class="device-run-toggle"
      :class="{
        running: currentDevice?.running && !isSwitching,
        idle: !currentDevice?.running && !isSwitching,
      }"
      :disabled="!currentDevice || isSwitching"
      :title="isSwitching ? 'Switching device state...' : (currentDevice?.running ? 'Stop device' : 'Start device')"
      @click="toggleRunning"
    >
      <span v-if="isSwitching" class="run-spinner"></span>
      <template v-else>
        <svg
          class="run-arrow"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="currentColor"
        >
          <path d="M8 5v14l11-7z"/>
        </svg>
        <span class="run-stop-square"></span>
      </template>
    </button>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useRuntimeStore } from "../stores/runtime";

const store = useRuntimeStore();
const isOpen = ref(false);
const selectorRef = ref(null);
const isSwitching = ref(false);

function pickDefaultDevice(devices) {
  if (!Array.isArray(devices) || devices.length === 0) return null;
  return devices.find((device) => device.device_type === "simulator") || devices[0];
}

const displayName = computed(() => {
  const current = store.currentDevice || pickDefaultDevice(store.devices);
  if (current) {
    return current.manufacturer || current.device_type;
  }
  return "No Device";
});

const displaySerial = computed(() => {
  const current = store.currentDevice || pickDefaultDevice(store.devices);
  if (current) {
    return current.serial_number;
  }
  return "";
});
const currentDevice = computed(() => store.currentDevice || pickDefaultDevice(store.devices));

function isCurrent(device) {
  const current = store.currentDevice || pickDefaultDevice(store.devices);
  if (!current) return false;
  return device.unique_id === current.unique_id;
}

function toggleDropdown() {
  isOpen.value = !isOpen.value;
}

function selectDevice(device) {
  store.currentDevice = device;
  isOpen.value = false;
}

async function toggleRunning(event) {
  event.stopPropagation();
  const current = currentDevice.value;
  if (!current || isSwitching.value) return;

  isSwitching.value = true;
  const currentId = current.unique_id;
  try {
    if (current.running) {
      await store.stopDevice(current.device_type, current.serial_number);
    } else {
      await store.startDevice(current.device_type, current.serial_number);
    }
    const refreshed = store.devices.find((device) => device.unique_id === currentId);
    store.currentDevice = refreshed || pickDefaultDevice(store.devices);
  } catch (err) {
    alert(err.message || "Failed to switch device state");
  } finally {
    isSwitching.value = false;
  }
}

function handleClickOutside(event) {
  if (selectorRef.value && !selectorRef.value.contains(event.target)) {
    isOpen.value = false;
  }
}

onMounted(async () => {
  await store.fetchDevices();
  const stillExists = store.currentDevice
    ? store.devices.some((device) => device.unique_id === store.currentDevice.unique_id)
    : false;
  if (!stillExists) {
    store.currentDevice = pickDefaultDevice(store.devices);
  }
  document.addEventListener("click", handleClickOutside);
});

onUnmounted(() => {
  document.removeEventListener("click", handleClickOutside);
});
</script>

<style scoped>
.device-selector {
  display: flex;
  align-items: center;
  gap: 8px;
}

.device-selector-main {
  position: relative;
}

.device-selector-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background-color: rgba(255, 255, 255, 0.1);
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  outline: none;
}

.device-selector-trigger:hover,
.device-selector-trigger.open {
  background-color: rgba(255, 255, 255, 0.18);
}

.device-selector-trigger:focus-visible {
  box-shadow: 0 0 0 2px #0071e3;
}

.device-info {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1px;
}

.device-name {
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 12px;
  font-weight: 600;
  color: #ffffff;
  letter-spacing: -0.12px;
  line-height: 1.2;
  text-transform: capitalize;
}

.device-serial {
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 11px;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.7);
  letter-spacing: -0.08px;
  line-height: 1.2;
}

.chevron {
  color: rgba(255, 255, 255, 0.7);
  transition: transform 0.2s ease;
  flex-shrink: 0;
}

.device-dropdown-menu {
  position: absolute;
  top: calc(100% + 20px);
  left: 0;
  min-width: 220px;
  background-color: rgba(39, 39, 41, 0.95);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  border-radius: 8px;
  box-shadow: rgba(0, 0, 0, 0.22) 3px 5px 30px 0px;
  padding: 6px;
  z-index: 1001;
  overflow: hidden;
}

.device-dropdown-menu::before {
  content: "";
  position: absolute;
  top: -7px;
  left: 22px;
  width: 14px;
  height: 14px;
  background-color: rgba(39, 39, 41, 0.95);
  transform: rotate(45deg);
  border-radius: 2px;
  z-index: -1;
}

.device-dropdown-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.device-dropdown-item:hover {
  background-color: rgba(255, 255, 255, 0.08);
}

.device-dropdown-item.active {
  background-color: rgba(0, 113, 227, 0.25);
}

.device-item-info {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
}

.device-item-name {
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 13px;
  font-weight: 500;
  color: #ffffff;
  letter-spacing: -0.12px;
  line-height: 1.2;
  text-transform: capitalize;
}

.device-item-serial {
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 12px;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.65);
  letter-spacing: -0.08px;
  line-height: 1.2;
}

.device-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #4caf50;
  flex-shrink: 0;
}

.device-dropdown-empty {
  padding: 16px 12px;
  text-align: center;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
}

.device-run-toggle {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  border: 1px solid rgba(76, 175, 80, 0.45);
  background: rgba(76, 175, 80, 0.1);
  color: #66d96e;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.device-run-toggle:hover:not(:disabled) {
  background: rgba(76, 175, 80, 0.16);
  border-color: rgba(76, 175, 80, 0.7);
}

.device-run-toggle:disabled {
  opacity: 0.7;
  cursor: default;
}

.device-run-toggle.running {
  background: rgba(76, 175, 80, 0.24);
  box-shadow: 0 0 12px rgba(76, 175, 80, 0.5), 0 0 22px rgba(76, 175, 80, 0.28);
  animation: running-glow 1.6s ease-in-out infinite;
}

.run-arrow {
  transform: translateX(0.5px);
}

.device-run-toggle.running .run-arrow {
  filter: drop-shadow(0 0 6px rgba(102, 217, 110, 0.75));
}

.run-stop-square {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  background: #ff5f57;
  box-shadow: 0 0 8px rgba(255, 95, 87, 0.45);
  display: none;
}

.device-run-toggle.running:hover .run-arrow {
  display: none;
}

.device-run-toggle.running:hover {
  color: #ff5f57;
  border-color: rgba(255, 95, 87, 0.72);
  background: rgba(255, 95, 87, 0.16);
  box-shadow: 0 0 12px rgba(255, 95, 87, 0.5), 0 0 22px rgba(255, 95, 87, 0.28);
}

.device-run-toggle.running:hover .run-stop-square {
  display: inline-block;
}

.run-spinner {
  width: 15px;
  height: 15px;
  border-radius: 50%;
  border: 2px solid rgba(102, 217, 110, 0.28);
  border-top-color: #66d96e;
  animation: spin 0.8s linear infinite;
}

@keyframes running-glow {
  0%,
  100% {
    box-shadow: 0 0 10px rgba(76, 175, 80, 0.42), 0 0 20px rgba(76, 175, 80, 0.2);
  }
  50% {
    box-shadow: 0 0 16px rgba(76, 175, 80, 0.62), 0 0 30px rgba(76, 175, 80, 0.34);
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Dropdown animation */
.dropdown-enter-active,
.dropdown-leave-active {
  transition: all 0.2s ease;
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
