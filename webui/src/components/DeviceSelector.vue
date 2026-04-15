<template>
  <div class="device-selector" ref="selectorRef">
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
            <span class="device-item-name">{{ device.device_type }}</span>
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
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useRuntimeStore } from "../stores/runtime";

const store = useRuntimeStore();
const isOpen = ref(false);
const selectorRef = ref(null);

const displayName = computed(() => {
  if (store.currentDevice) {
    return store.currentDevice.device_type;
  }
  if (store.devices.length > 0) {
    return store.devices[0].device_type;
  }
  return "No Device";
});

const displaySerial = computed(() => {
  if (store.currentDevice) {
    return store.currentDevice.serial_number;
  }
  if (store.devices.length > 0) {
    return store.devices[0].serial_number;
  }
  return "";
});

function isCurrent(device) {
  const current = store.currentDevice || store.devices[0] || null;
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

function handleClickOutside(event) {
  if (selectorRef.value && !selectorRef.value.contains(event.target)) {
    isOpen.value = false;
  }
}

onMounted(() => {
  store.fetchDevices();
  if (!store.currentDevice && store.devices.length > 0) {
    store.currentDevice = store.devices[0];
  }
  document.addEventListener("click", handleClickOutside);
});

onUnmounted(() => {
  document.removeEventListener("click", handleClickOutside);
});
</script>

<style scoped>
.device-selector {
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
