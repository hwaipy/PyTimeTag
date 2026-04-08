import MainLayout from "../layouts/MainLayout.vue";
import IndexPage from "../pages/IndexPage.vue";
import OfflinePage from "../pages/OfflinePage.vue";
import SettingsPage from "../pages/SettingsPage.vue";
import LogsPage from "../pages/LogsPage.vue";

const routes = [
  {
    path: "/",
    component: MainLayout,
    children: [
      { path: "", component: IndexPage },
      { path: "offline", component: OfflinePage },
      { path: "settings", component: SettingsPage },
      { path: "logs", component: LogsPage },
    ],
  },
];

export default routes;

