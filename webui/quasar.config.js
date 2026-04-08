/* eslint-env node */

const { configure } = require("quasar/wrappers");

module.exports = configure(function () {
  return {
    supportTS: false,
    css: ["app.css"],
    extras: ["roboto-font", "material-icons"],
    build: {
      target: {
        browser: ["es2022", "firefox115", "chrome115", "safari14"]
      },
      vueRouterMode: "history",
      distDir: "../pytimetag/gui/webui_dist",
      env: {
        API_BASE: "/api/v1"
      }
    },
    devServer: {
      port: 5173,
      open: false,
      proxy: {
        "/api": {
          target: "http://127.0.0.1:8787",
          changeOrigin: true
        },
        "/ws": {
          target: "ws://127.0.0.1:8787",
          ws: true
        }
      }
    },
    framework: {
      plugins: []
    }
  };
});

