const routes = [
  {
    path: "/",
    component: () => import("../layouts/MainLayout.vue"),
    children: [
      { path: "", component: () => import("../pages/IndexPage.vue") },
      { path: "offline", component: () => import("../pages/OfflinePage.vue") },
      { path: "storage", component: () => import("../pages/StoragePage.vue") },
      { path: "settings", component: () => import("../pages/SettingsPage.vue") },
      { path: "logs", component: () => import("../pages/LogsPage.vue") },
    ],
  },
];

export default routes;

