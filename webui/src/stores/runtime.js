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
    devices: [],
    currentDevice: null,
    streamPaths: [],
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
      this._metricsWsRef = (this._metricsWsRef || 0) + 1;
      if (this._metricsWs && this._metricsWs.readyState <= WebSocket.OPEN) {
        return this._metricsWs;
      }
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${protocol}://${window.location.host}/ws/metrics`);
      ws.onmessage = (evt) => {
        this.metrics = JSON.parse(evt.data);
      };
      ws.onclose = () => {
        this._metricsWs = null;
        this._metricsWsRef = 0;
      };
      this._metricsWs = ws;
      return ws;
    },
    disconnectMetrics() {
      this._metricsWsRef = Math.max(0, (this._metricsWsRef || 1) - 1);
      if (this._metricsWsRef === 0 && this._metricsWs) {
        this._metricsWs.close();
        this._metricsWs = null;
      }
    },
    connectLogs() {
      this._logsWsRef = (this._logsWsRef || 0) + 1;
      if (this._logsWs && this._logsWs.readyState <= WebSocket.OPEN) {
        return this._logsWs;
      }
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${protocol}://${window.location.host}/ws/logs`);
      ws.onmessage = (evt) => {
        const row = JSON.parse(evt.data);
        this.logs = [...this.logs.slice(-199), row];
      };
      ws.onclose = () => {
        this._logsWs = null;
        this._logsWsRef = 0;
      };
      this._logsWs = ws;
      return ws;
    },
    disconnectLogs() {
      this._logsWsRef = Math.max(0, (this._logsWsRef || 1) - 1);
      if (this._logsWsRef === 0 && this._logsWs) {
        this._logsWs.close();
        this._logsWs = null;
      }
    },
    // Storage API methods - unified style: /storage/{collection}/{function}/{arg}
    async fetchStorageCollections() {
      const res = await this._request(`${API_BASE}/storage/collections`);
      const data = await res.json();
      return data.items || [];
    },
    async storageAppend(collection, data, fetchTime) {
      const res = await this._request(`${API_BASE}/storage/${collection}/append`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data, fetchTime }),
      });
      return await res.json();
    },
    async storageList(collection, params = {}) {
      const query = new URLSearchParams();
      if (params.limit) query.set("limit", params.limit);
      if (params.offset) query.set("offset", params.offset);
      if (params.by) query.set("by", params.by);
      if (params.after) query.set("after", params.after);
      const res = await this._request(`${API_BASE}/storage/${collection}/list?${query.toString()}`);
      return await res.json();
    },
    async storageFirst(collection, params = {}) {
      const query = new URLSearchParams();
      if (params.by) query.set("by", params.by);
      if (params.after) query.set("after", params.after);
      const res = await this._request(`${API_BASE}/storage/${collection}/first?${query.toString()}`);
      return await res.json();
    },
    async storageRange(collection, begin, end, params = {}) {
      const query = new URLSearchParams();
      query.set("begin", begin);
      query.set("end", end);
      if (params.by) query.set("by", params.by);
      if (params.limit) query.set("limit", params.limit);
      const res = await this._request(`${API_BASE}/storage/${collection}/range?${query.toString()}`);
      return await res.json();
    },
    async storageGet(collection, value, key = "_id") {
      const query = new URLSearchParams();
      if (key !== "_id") query.set("key", key);
      const res = await this._request(`${API_BASE}/storage/${collection}/get/${value}?${query.toString()}`);
      return await res.json();
    },
    async storageDelete(collection, value, key = "_id") {
      const query = new URLSearchParams();
      if (key !== "_id") query.set("key", key);
      await this._request(`${API_BASE}/storage/${collection}/delete/${value}?${query.toString()}`, {
        method: "DELETE",
      });
    },
    async storageUpdate(collection, id, value) {
      const res = await this._request(`${API_BASE}/storage/${collection}/update/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value }),
      });
      return await res.json();
    },
    // Current device API (read-only)
    async fetchDevices() {
      const res = await this._request(`${API_BASE}/device/current`);
      const device = await res.json();
      this.devices = [device];
      this.currentDevice = device;
      return this.devices;
    },
    async fetchStreamPaths() {
      const res = await this._request(`${API_BASE}/stream_paths`);
      const data = await res.json();
      this.streamPaths = data.items || [];
      return this.streamPaths;
    },
    async fetchDeviceChannels(deviceType, serialNumber) {
      const res = await this._request(`${API_BASE}/devices/${deviceType}/${serialNumber}/channels`);
      return await res.json();
    },
    async updateDeviceChannel(deviceType, serialNumber, channelId, config) {
      const res = await this._request(`${API_BASE}/devices/${deviceType}/${serialNumber}/channels/${channelId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      return await res.json();
    },
  },
});
