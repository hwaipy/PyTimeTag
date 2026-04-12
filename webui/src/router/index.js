import { route } from "quasar/wrappers";
import { createMemoryHistory, createRouter, createWebHistory } from "vue-router";
import { ref } from "vue";
import routes from "./routes";

// 路由加载进度条状态（独立于 API 请求）
export const routeLoadingProgress = ref(0);
export const isRouteLoading = ref(false);

let progressTimer = null;
let startDelayTimer = null;
let startTime = null;
const SHOW_DELAY = 300; // 超过 300ms 才开始显示

function startProgress() {
  // 清除之前的定时器
  if (startDelayTimer) {
    clearTimeout(startDelayTimer);
  }
  if (progressTimer) {
    clearInterval(progressTimer);
  }

  startTime = Date.now();

  // 延迟显示进度条
  startDelayTimer = setTimeout(() => {
    isRouteLoading.value = true;
    routeLoadingProgress.value = 10;

    // 开始模拟进度增长
    progressTimer = setInterval(() => {
      if (routeLoadingProgress.value < 85) {
        routeLoadingProgress.value += Math.random() * 12 + 3;
        if (routeLoadingProgress.value > 85) {
          routeLoadingProgress.value = 85;
        }
      }
    }, 150);
  }, SHOW_DELAY);
}

function finishProgress() {
  const elapsed = Date.now() - startTime;

  // 清除延迟定时器
  if (startDelayTimer) {
    clearTimeout(startDelayTimer);
    startDelayTimer = null;
  }

  // 如果还没开始显示（不到300ms），直接什么都不做
  if (elapsed < SHOW_DELAY) {
    return;
  }

  // 已经在显示进度条，完成它
  if (progressTimer) {
    clearInterval(progressTimer);
    progressTimer = null;
  }

  routeLoadingProgress.value = 100;

  setTimeout(() => {
    isRouteLoading.value = false;
    routeLoadingProgress.value = 0;
  }, 200);
}

export default route(function () {
  const createHistory = process.env.SERVER ? createMemoryHistory : createWebHistory;
  const Router = createRouter({
    scrollBehavior: () => ({ left: 0, top: 0 }),
    routes,
    history: createHistory(process.env.VUE_ROUTER_BASE),
  });

  let isNavigating = false;

  // 路由导航守卫 - 控制进度条
  Router.beforeEach((to, from, next) => {
    if (!isNavigating) {
      isNavigating = true;
      startProgress();
    }
    next();
  });

  Router.afterEach(() => {
    isNavigating = false;
    finishProgress();
  });

  Router.onError(() => {
    isNavigating = false;
    finishProgress();
  });

  return Router;
});
