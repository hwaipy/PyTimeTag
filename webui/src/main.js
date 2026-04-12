import { createApp } from "vue";
import { Quasar } from "quasar";
import { createPinia } from "pinia";
import "quasar/src/css/index.sass";
import "./css/apple-design.css";
import "./app.css";
import App from "./App.vue";

const app = createApp(App);
app.use(Quasar, {});
app.use(createPinia());
app.mount("#q-app");

