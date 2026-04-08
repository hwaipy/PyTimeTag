import { defineStore } from "pinia";

const API_BASE = import.meta.env.API_BASE || "/api/v1";

export const useRuntimeStore = defineStore("runtime", {
  state: () => ({
    session: null,
    datablocks: [],
    metrics: null,
    jobs: [],
    analyzers: {},
    settings: {},
    logs: [],
  }),
  actions: {
    async fetchSession() {
      const res = await fetch(`${API_BASE}/session/status`);
      this.session = await res.json();
    },
    async startSession() {
      await fetch(`${API_BASE}/session/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: "simulator" }),
      });
      await this.fetchSession();
    },
    async stopSession() {
      await fetch(`${API_BASE}/session/stop`, { method: "POST" });
      await this.fetchSession();
    },
    async fetchDatablocks() {
      const res = await fetch(`${API_BASE}/datablocks?limit=50`);
      const data = await res.json();
      this.datablocks = data.items || [];
    },
    async processDatablock(path) {
      const res = await fetch(`${API_BASE}/offline/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ datablock_path: path }),
      });
      return await res.json();
    },
    async fetchJobs() {
      const res = await fetch(`${API_BASE}/jobs?limit=50`);
      const data = await res.json();
      this.jobs = data.items || [];
    },
    async fetchAnalyzers() {
      const res = await fetch(`${API_BASE}/analyzers`);
      this.analyzers = await res.json();
    },
    async updateAnalyzer(name, enabled, config) {
      await fetch(`${API_BASE}/analyzers/${name}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled, config }),
      });
      await this.fetchAnalyzers();
    },
    async fetchSettings() {
      const res = await fetch(`${API_BASE}/settings`);
      const data = await res.json();
      this.settings = data.settings || {};
    },
    async saveSettings() {
      await fetch(`${API_BASE}/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ settings: this.settings }),
      });
      await this.fetchSettings();
    },
    async fetchLogs() {
      const res = await fetch(`${API_BASE}/logs?limit=200`);
      const data = await res.json();
      this.logs = data.items || [];
    },
    connectMetrics() {
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${protocol}://${window.location.host}/ws/metrics`);
      ws.onmessage = (evt) => {
        this.metrics = JSON.parse(evt.data);
      };
      return ws;
    },
    connectLogs() {
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${protocol}://${window.location.host}/ws/logs`);
      ws.onmessage = (evt) => {
        const row = JSON.parse(evt.data);
        this.logs = [...this.logs.slice(-199), row];
      };
      return ws;
    },
  },
});

