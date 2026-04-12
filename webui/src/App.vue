<template>
  <router-view />
</template>

<script setup>
import { onMounted } from "vue";

onMounted(() => {
  // Hide the initial loading screen when Vue app is ready
  const loader = document.getElementById("app-loader");
  if (loader) {
    // Small delay to ensure the Vue app is fully rendered
    requestAnimationFrame(() => {
      loader.classList.add("hidden");
      // Remove from DOM after transition completes
      setTimeout(() => {
        loader.remove();
      }, 400);
    });
  }
});
</script>
