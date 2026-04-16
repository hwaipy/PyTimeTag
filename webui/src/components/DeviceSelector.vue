<template>
  <div class="device-selector">
    <span class="device-label">{{ displayLabel }}</span>
    <span v-if="currentDevice?.running" class="device-status-dot" title="Running"></span>
    <span v-else class="device-status-dot inactive" title="Idle"></span>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useRuntimeStore } from "../stores/runtime";

const store = useRuntimeStore();

const currentDevice = computed(() => store.currentDevice);

const displayLabel = computed(() => {
  const device = currentDevice.value;
  if (!device) return "No Device";
  const make = device.manufacturer || device.device_type || "";
  const model = device.model_name || "";
  const name = [make, model].filter(Boolean).join(" ");
  const sn = device.serial_number || "";
  return name && sn ? `${name} / ${sn}` : name || sn || "Unknown Device";
});
</script>

<style scoped>
.device-selector {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 12px;
  background-color: rgba(255, 255, 255, 0.1);
  border-radius: 8px;
}

.device-label {
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 12px;
  font-weight: 600;
  color: #ffffff;
  letter-spacing: -0.12px;
  line-height: 1.2;
  white-space: nowrap;
  text-transform: capitalize;
}

.device-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #4caf50;
  flex-shrink: 0;
}

.device-status-dot.inactive {
  background-color: rgba(255, 255, 255, 0.35);
}
</style>
