<template>
  <q-layout view="lHh Lpr lFf">
    <q-header elevated>
      <q-linear-progress
        v-show="store.isLoading || store.loadingProgress > 0"
        :value="store.loadingProgress"
        color="accent"
        track-color="transparent"
        class="absolute-top"
      />
      <q-toolbar>
        <q-btn flat dense round icon="menu" @click="leftDrawerOpen = !leftDrawerOpen" />
        <q-toolbar-title>PyTimeTag GUI</q-toolbar-title>
        <q-chip dense square color="primary" text-color="white" class="q-ml-sm">
          Device: {{ currentDevice }}
        </q-chip>
        <q-badge :color="running ? 'positive' : 'grey'" class="q-ml-sm">
          {{ running ? "RUNNING" : "IDLE" }}
        </q-badge>
      </q-toolbar>
    </q-header>

    <q-drawer v-model="leftDrawerOpen" show-if-above bordered>
      <q-list>
        <q-item-label header>Navigation</q-item-label>
        <q-item clickable v-ripple to="/" exact>
          <q-item-section>Dashboard</q-item-section>
        </q-item>
        <q-item clickable v-ripple to="/offline">
          <q-item-section>Offline</q-item-section>
        </q-item>
        <q-item clickable v-ripple to="/settings">
          <q-item-section>Settings</q-item-section>
        </q-item>
        <q-item clickable v-ripple to="/logs">
          <q-item-section>Logs</q-item-section>
        </q-item>
      </q-list>
    </q-drawer>

    <q-page-container>
      <router-view />
    </q-page-container>
  </q-layout>
</template>

<script setup>
import { computed, ref } from "vue";
import { useRuntimeStore } from "../stores/runtime";

const leftDrawerOpen = ref(true);
const store = useRuntimeStore();
const running = computed(() => Boolean(store.metrics?.running || store.session?.running));
const currentDevice = computed(() => store.metrics?.source || store.session?.source || "simulator");
</script>

