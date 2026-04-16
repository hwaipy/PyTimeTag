<template>
  <div class="app-container">
    <!-- Navigation Bar -->
    <nav class="apple-nav">
      <div class="nav-left">
        <div class="nav-brand">PyTimeTag</div>
        <DeviceSelector />
      </div>

      <div class="nav-links" ref="navLinksRef">
        <router-link
          v-for="item in visibleItems"
          :key="item.path"
          :to="item.path"
          class="nav-link"
          :class="{ active: $route.path === item.path }"
        >
          {{ item.label }}
        </router-link>
        <div v-if="overflowItems.length" class="nav-more" ref="moreRef">
          <button
            class="nav-more-btn"
            :class="{ active: showMore }"
            @click="toggleMore"
          >
            <span>More</span>
            <svg
              width="10"
              height="10"
              viewBox="0 0 24 24"
              fill="currentColor"
              :style="{ transform: showMore ? 'rotate(180deg)' : '' }"
            >
              <path d="M7 10l5 5 5-5z"/>
            </svg>
          </button>
          <transition name="dropdown">
            <div v-if="showMore" class="more-dropdown">
              <router-link
                v-for="item in overflowItems"
                :key="item.path"
                :to="item.path"
                class="more-link"
                :class="{ active: $route.path === item.path }"
                @click="showMore = false"
              >
                {{ item.label }}
              </router-link>
            </div>
          </transition>
        </div>
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
import { computed, ref, onMounted, onUnmounted, nextTick } from "vue";
import { useRoute } from "vue-router";
import { routeLoadingProgress, isRouteLoading } from "../router/index.js";
import DeviceSelector from "../components/DeviceSelector.vue";

const route = useRoute();

const navItems = [
  { path: "/", label: "Config" },
  { path: "/traces", label: "Traces" },
  { path: "/dashboard", label: "Dashboard" },
  { path: "/offline", label: "Offline" },
  { path: "/storage", label: "Storage" },
  { path: "/settings", label: "Settings" },
  { path: "/logs", label: "Logs" },
];

const navLinksRef = ref(null);
const moreRef = ref(null);
const showMore = ref(false);
const visibleCount = ref(navItems.length);

const visibleItems = computed(() => {
  const count = visibleCount.value;
  const currentIndex = navItems.findIndex((item) => item.path === route.path);

  if (currentIndex === -1) {
    return navItems.slice(0, Math.min(count, navItems.length));
  }

  if (count >= navItems.length) {
    return [...navItems];
  }

  const selected = new Set([currentIndex]);
  for (let i = 0; i < navItems.length && selected.size < count; i++) {
    if (i !== currentIndex) {
      selected.add(i);
    }
  }

  return navItems.filter((_, i) => selected.has(i));
});
const overflowItems = computed(() => {
  const visible = visibleItems.value;
  return navItems.filter((item) => !visible.includes(item));
});

function toggleMore() {
  showMore.value = !showMore.value;
}

function handleClickOutside(event) {
  if (moreRef.value && !moreRef.value.contains(event.target)) {
    showMore.value = false;
  }
}

function updateVisibleCount() {
  if (!navLinksRef.value) return;

  const linksEl = navLinksRef.value;
  const availableWidth = linksEl.offsetWidth;
  if (availableWidth < 32) return;

  const gap = 8;
  const moreBtnWidth = 72;
  const safetyMargin = 8;
  const effectiveWidth = availableWidth - safetyMargin;

  let totalWidth = 0;
  let count = 0;

  for (let i = 0; i < navItems.length; i++) {
    // Approximate width based on text length: ~8px per char + 32px padding
    const itemWidth = navItems[i].label.length * 8 + 32 + gap;
    const needed =
      totalWidth +
      itemWidth +
      (count < navItems.length - 1 ? moreBtnWidth : 0);
    if (needed > effectiveWidth && count < navItems.length) {
      break;
    }
    totalWidth += itemWidth;
    count++;
  }

  // If nothing fits, at least show one item
  visibleCount.value = Math.max(1, count);
}

let resizeObserver = null;

onMounted(async () => {
  document.addEventListener("click", handleClickOutside);
  await nextTick();
  updateVisibleCount();

  const nav = navLinksRef.value?.closest(".apple-nav");
  if (nav && typeof ResizeObserver !== "undefined") {
    resizeObserver = new ResizeObserver(() => {
      updateVisibleCount();
    });
    resizeObserver.observe(nav);
    if (navLinksRef.value) {
      resizeObserver.observe(navLinksRef.value);
    }
  } else {
    window.addEventListener("resize", updateVisibleCount);
  }
});

onUnmounted(() => {
  document.removeEventListener("click", handleClickOutside);
  if (resizeObserver) {
    resizeObserver.disconnect();
  } else {
    window.removeEventListener("resize", updateVisibleCount);
  }
});

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

/* Navigation Bar — left | tabs (flex) | right; fixed gap avoids overlap with device */
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
  gap: 24px;
  padding: 0 24px;
  /* 确保子元素的 absolute 定位相对于导航栏 */
  transform: translateZ(0);
}

.nav-left {
  display: flex;
  align-items: center;
  gap: 32px;
  min-width: 100px;
  flex-shrink: 0;
}

.nav-brand {
  font-size: 18px;
  font-weight: 600;
  color: white;
  letter-spacing: -0.3px;
}

.nav-links {
  flex: 1 1 0;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
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
  flex-shrink: 0;
  min-width: 100px;
  display: flex;
  justify-content: flex-end;
  align-items: center;
}

.nav-more {
  position: relative;
}

.nav-more-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  color: rgba(255, 255, 255, 0.8);
  background: transparent;
  border: none;
  font-size: 13px;
  font-weight: 400;
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
  font-family: inherit;
}

.nav-more-btn:hover,
.nav-more-btn.active {
  color: white;
  background-color: rgba(255, 255, 255, 0.1);
}

.nav-more-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px #0071e3;
}

.more-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  min-width: 140px;
  background-color: rgba(39, 39, 41, 0.95);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  border-radius: 8px;
  box-shadow: rgba(0, 0, 0, 0.22) 3px 5px 30px 0px;
  padding: 6px;
  z-index: 1001;
  overflow: hidden;
}

.more-link {
  display: block;
  color: rgba(255, 255, 255, 0.85);
  text-decoration: none;
  font-size: 13px;
  font-weight: 400;
  padding: 10px 12px;
  border-radius: 6px;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.more-link:hover {
  color: white;
  background-color: rgba(255, 255, 255, 0.08);
}

.more-link.active {
  color: white;
  background-color: rgba(0, 113, 227, 0.25);
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
    gap: 16px;
  }

  .nav-brand {
    font-size: 16px;
    min-width: auto;
  }

  .nav-links {
    gap: 4px;
  }

  .nav-link {
    padding: 6px 10px;
    font-size: 12px;
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

/* Dropdown transition animation */
.dropdown-enter-active,
.dropdown-leave-active {
  transition: all 0.2s ease;
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
