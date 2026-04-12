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
    datablocksLimit: 50,
    jobsLimit: 50,
    logsLimit: 50,
    loadingCount: 0,
    loadingProgress: 0,
  }),
  getters: {
    isLoading: (state) => state.loadingCount > 0,
  },
  actions: {
    _startLoading() {
      this.loadingCount += 1;
      if (this.loadingCount === 1) {
        this.loadingProgress = 0.1;
      } else {
        this.loadingProgress = Math.min(0.85, this.loadingProgress + 0.12);
      }
    },
    _endLoading() {
      this.loadingCount = Math.max(0, this.loadingCount - 1);
      if (this.loadingCount === 0) {
        this.loadingProgress = 1;
        setTimeout(() => {
          if (this.loadingCount === 0) this.loadingProgress = 0;
        }, 180);
      }
    },
    async _request(url, options) {
      this._startLoading();
      try {
        const res = await fetch(url, options);
        if (!res.ok) {
          throw new Error(`Request failed: ${res.status} ${res.statusText}`);
        }
        return res;
      } finally {
        this._endLoading();
      }
    },
    async fetchSession() {
      const res = await this._request(`${API_BASE}/session/status`);
      this.session = await res.json();
    },
    async startSession() {
      await this._request(`${API_BASE}/session/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: "simulator" }),
      });
      await this.fetchSession();
    },
    async stopSession() {
      await this._request(`${API_BASE}/session/stop`, { method: "POST" });
      await this.fetchSession();
    },
    async fetchDatablocks(limit = this.datablocksLimit) {
      this.datablocksLimit = limit;
      const res = await this._request(`${API_BASE}/datablocks?limit=${this.datablocksLimit}`);
      const data = await res.json();
      this.datablocks = data.items || [];
    },
    async loadMoreDatablocks(step = 50) {
      await this.fetchDatablocks(this.datablocksLimit + step);
    },
    async processDatablock(path) {
      const res = await this._request(`${API_BASE}/offline/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ datablock_path: path }),
      });
      return await res.json();
    },
    async fetchJobs(limit = this.jobsLimit) {
      this.jobsLimit = limit;
      const res = await this._request(`${API_BASE}/jobs?limit=${this.jobsLimit}`);
      const data = await res.json();
      this.jobs = data.items || [];
    },
    async loadMoreJobs(step = 50) {
      await this.fetchJobs(this.jobsLimit + step);
    },
    async fetchAnalyzers() {
      const res = await this._request(`${API_BASE}/analyzers`);
      this.analyzers = await res.json();
    },
    async updateAnalyzer(name, enabled, config) {
      await this._request(`${API_BASE}/analyzers/${name}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled, config }),
      });
      await this.fetchAnalyzers();
    },
    async fetchSettings() {
      const res = await this._request(`${API_BASE}/settings`);
      const data = await res.json();
      this.settings = data.settings || {};
    },
    async saveSettings() {
      await this._request(`${API_BASE}/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ settings: this.settings }),
      });
      await this.fetchSettings();
    },
    async fetchLogs(limit = this.logsLimit) {
      this.logsLimit = limit;
      const res = await this._request(`${API_BASE}/logs?limit=${this.logsLimit}`);
      const data = await res.json();
      this.logs = data.items || [];
    },
    async loadMoreLogs(step = 50) {
      await this.fetchLogs(this.logsLimit + step);
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
    // Storage API methods
    async fetchStorageCollections() {
      const res = await this._request(`${API_BASE}/storage/collections`);
      const data = await res.json();
      return data.items || [];
    },
    async fetchStorageCollection(collection, params = {}) {
      const query = new URLSearchParams();
      if (params.limit) query.set("limit", params.limit);
      if (params.offset) query.set("offset", params.offset);
      if (params.order_by) query.set("order_by", params.order_by);
      if (params.order_desc !== undefined) query.set("order_desc", params.order_desc);
      if (params.after) query.set("after", params.after);
      const res = await this._request(`${API_BASE}/storage/${collection}?${query.toString()}`);
      return await res.json();
    },
    async fetchStorageItem(collection, itemId) {
      const res = await this._request(`${API_BASE}/storage/${collection}/${itemId}`);
      return await res.json();
    },
    async deleteStorageItem(collection, itemId) {
      await this._request(`${API_BASE}/storage/${collection}/${itemId}`, {
        method: "DELETE",
      });
    },
  },
});

