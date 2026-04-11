<template>
  <div class="startup-loader column flex-center q-pa-xl">
    <svg class="startup-loader__logo-svg" viewBox="0 0 780 150" role="img" aria-label="PyTimeTag handwritten script logo">
      <defs>
        <linearGradient id="logoScriptFill" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#8f959d" />
          <stop offset="55%" stop-color="#6e747c" />
          <stop offset="100%" stop-color="#575d65" />
        </linearGradient>
      </defs>
      <text x="390" y="102" text-anchor="middle" font-size="104" font-family="'Snell Roundhand', 'Brush Script MT', 'Segoe Script', 'Lucida Handwriting', cursive" font-weight="700" font-style="italic" letter-spacing="1.5" transform="skewX(-6)" fill="url(#logoScriptFill)" stroke="#4d5258" stroke-width="1.2" paint-order="stroke fill">PyTimeTag</text>
    </svg>
    <div class="text-subtitle2 text-grey-7 q-mb-md">{{ label }}</div>
    <q-linear-progress
      v-if="showProgress"
      rounded
      size="12px"
      :value="progress"
      color="primary"
      track-color="grey-3"
      class="startup-loader__bar"
    />
    <div v-if="showProgress" class="text-caption text-grey-7 q-mt-sm">{{ percentage }}%</div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  progress: {
    type: Number,
    default: 0,
  },
  label: {
    type: String,
    default: "Loading...",
  },
  showProgress: {
    type: Boolean,
    default: false,
  },
});

const percentage = computed(() => Math.min(100, Math.round((props.progress || 0) * 100)));
</script>

<style scoped>
.startup-loader {
  min-height: 100vh;
}

.startup-loader__logo-svg {
  width: min(720px, 92vw);
  height: auto;
  display: block;
  margin: 0 0 14px;
}

.startup-loader__bar {
  width: min(560px, 90vw);
}
</style>
