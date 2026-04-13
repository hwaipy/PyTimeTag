<template>
  <div class="app-container">
    <!-- Navigation Bar -->
    <nav class="apple-nav">
      <div class="nav-brand">PyTimeTag</div>

      <div class="nav-links">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-link"
          :class="{ active: $route.path === item.path }"
        >
          {{ item.label }}
        </router-link>
      </div>

      <div class="nav-right">
        <a
          href="https://github.com/Hwaipy/PyTimeTag"
          target="_blank"
          rel="noopener noreferrer"
          class="github-link"
          title="View on GitHub"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
          </svg>
        </a>
      </div>

      <!-- Route Loading Progress Bar -->
      <div class="route-progress" v-show="isRouteLoading">
        <div class="route-progress-bar" :style="{ width: progressPercent }"></div>
      </div>
    </nav>

    <!-- Main Content -->
    <main class="main-content">
      <div class="content-wrapper">
        <router-view />
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";
import { routeLoadingProgress, isRouteLoading } from "../router/index.js";

const route = useRoute();

const navItems = [
  { path: "/", label: "Devices" },
  { path: "/dashboard", label: "Dashboard" },
  { path: "/offline", label: "Offline" },
  { path: "/storage", label: "Storage" },
  { path: "/settings", label: "Settings" },
  { path: "/logs", label: "Logs" },
];

const progressPercent = computed(() => {
  return Math.min(routeLoadingProgress.value, 100) + "%";
});
</script>

<style scoped>
@import "../css/apple-design.css";

.app-container {
  min-height: 100vh;
  background-color: var(--apple-light-gray);
}

/* Navigation Bar - Centered Links */
.apple-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 48px;
  background-color: rgba(0, 0, 0, 0.8);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  /* 确保子元素的 absolute 定位相对于导航栏 */
  transform: translateZ(0);
}

.nav-brand {
  font-size: 18px;
  font-weight: 600;
  color: white;
  letter-spacing: -0.3px;
  min-width: 100px;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 8px;
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.nav-link {
  color: rgba(255, 255, 255, 0.8);
  text-decoration: none;
  font-size: 13px;
  font-weight: 400;
  padding: 8px 16px;
  border-radius: 6px;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.nav-link:hover {
  color: white;
  background-color: rgba(255, 255, 255, 0.1);
}

.nav-link.active {
  color: white;
  background-color: rgba(255, 255, 255, 0.15);
  font-weight: 500;
}

.nav-right {
  min-width: 100px;
  display: flex;
  justify-content: flex-end;
  align-items: center;
}

.github-link {
  color: rgba(255, 255, 255, 0.8);
  padding: 8px;
  border-radius: 6px;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.github-link:hover {
  color: white;
  background-color: rgba(255, 255, 255, 0.1);
  transform: translateY(-1px);
}

/* Route Loading Progress Bar */
.route-progress {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  background-color: rgba(255, 255, 255, 0.1);
  overflow: hidden;
}

.route-progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #0071e3 0%, #2997ff 100%);
  box-shadow: 0 0 10px rgba(0, 113, 227, 0.5), 0 0 20px rgba(0, 113, 227, 0.3);
  transition: width 0.15s ease-out;
}

/* Main Content - No Sidebar */
.main-content {
  padding-top: 48px;
  min-height: 100vh;
}

.content-wrapper {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 24px;
}

/* Responsive */
@media (max-width: 768px) {
  .apple-nav {
    padding: 0 16px;
  }

  .nav-brand {
    font-size: 16px;
    min-width: auto;
  }

  .nav-links {
    position: static;
    transform: none;
    gap: 4px;
    margin-left: auto;
  }

  .nav-link {
    padding: 6px 10px;
    font-size: 12px;
  }

  .nav-right {
    display: none;
  }

  .content-wrapper {
    padding: 20px 16px;
  }
}

@media (max-width: 480px) {
  .nav-links {
    gap: 2px;
  }

  .nav-link {
    padding: 6px 8px;
    font-size: 11px;
  }
}
</style>
