import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useRuntimeStore } from '../runtime.js'

// Mock global fetch
global.fetch = vi.fn()

describe('Runtime Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    fetch.mockClear()
  })

  describe('Session API', () => {
    it('should fetch session status', async () => {
      const mockResponse = {
        running: false,
        source: 'simulator',
        blocks: 0,
        events_total: 0,
      }
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      const store = useRuntimeStore()
      await store.fetchSession()

      expect(fetch).toHaveBeenCalledWith('/api/v1/session/status', undefined)
      expect(store.session).toEqual(mockResponse)
    })

    it('should start session', async () => {
      const startResponse = {
        running: true,
        source: 'simulator',
        blocks: 0,
      }
      const statusResponse = {
        running: true,
        source: 'simulator',
        blocks: 0,
        events_total: 0,
      }
      fetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => startResponse,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => statusResponse,
        })

      const store = useRuntimeStore()
      await store.startSession()

      expect(fetch).toHaveBeenNthCalledWith(1, '/api/v1/session/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: 'simulator' }),
      })
      expect(fetch).toHaveBeenNthCalledWith(2, '/api/v1/session/status', undefined)
      expect(store.session).toEqual(statusResponse)
    })

    it('should stop session', async () => {
      const stopResponse = {
        running: false,
        source: 'simulator',
        blocks: 1,
      }
      const statusResponse = {
        running: false,
        source: 'simulator',
        blocks: 1,
        events_total: 100,
      }
      fetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => stopResponse,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => statusResponse,
        })

      const store = useRuntimeStore()
      await store.stopSession()

      expect(fetch).toHaveBeenNthCalledWith(1, '/api/v1/session/stop', { method: 'POST' })
      expect(fetch).toHaveBeenNthCalledWith(2, '/api/v1/session/status', undefined)
      expect(store.session).toEqual(statusResponse)
    })

    it('should throw on error response', async () => {
      fetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      })

      const store = useRuntimeStore()
      await expect(store.fetchSession()).rejects.toThrow('Request failed: 500 Internal Server Error')
    })
  })

  describe('Storage API', () => {
    it('should fetch storage collections', async () => {
      const mockResponse = { items: ['CounterAnalyser', 'HistogramAnalyser'] }
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      const store = useRuntimeStore()
      const result = await store.fetchStorageCollections()

      expect(fetch).toHaveBeenCalledWith('/api/v1/storage/collections', undefined)
      expect(result).toEqual(['CounterAnalyser', 'HistogramAnalyser'])
    })

    it('should fetch storage collection data', async () => {
      const mockResponse = {
        items: [
          { _id: '1', Data: { count: 100 }, RecordTime: '2026-01-01T00:00:00Z' },
        ],
        collection: 'CounterAnalyser',
        limit: 10,
        offset: 0,
      }
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      const store = useRuntimeStore()
      const result = await store.fetchStorageCollection('CounterAnalyser', { limit: 10 })

      expect(fetch).toHaveBeenCalledWith(
        '/api/v1/storage/CounterAnalyser?limit=10',
        undefined
      )
      expect(result).toEqual(mockResponse)
    })

    it('should fetch single storage item', async () => {
      const mockResponse = { _id: 'test-id', Data: { count: 100 } }
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      const store = useRuntimeStore()
      const result = await store.fetchStorageItem('CounterAnalyser', 'test-id')

      expect(fetch).toHaveBeenCalledWith(
        '/api/v1/storage/CounterAnalyser/test-id',
        undefined
      )
      expect(result).toEqual(mockResponse)
    })

    it('should delete storage item', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ deleted: true }),
      })

      const store = useRuntimeStore()
      await store.deleteStorageItem('CounterAnalyser', 'test-id')

      expect(fetch).toHaveBeenCalledWith(
        '/api/v1/storage/CounterAnalyser/test-id',
        { method: 'DELETE' }
      )
    })
  })

  describe('Datablocks API', () => {
    it('should fetch datablocks', async () => {
      const mockResponse = {
        items: [{ path: '/test.datablock', size: 1024, mtime: 1234567890 }],
      }
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      const store = useRuntimeStore()
      await store.fetchDatablocks(50)

      expect(fetch).toHaveBeenCalledWith('/api/v1/datablocks?limit=50', undefined)
      expect(store.datablocks).toEqual(mockResponse.items)
    })
  })

  describe('Jobs API', () => {
    it('should fetch jobs', async () => {
      const mockResponse = {
        items: [{ id: 'job-1', kind: 'offline_process', status: 'completed' }],
      }
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      const store = useRuntimeStore()
      await store.fetchJobs(50)

      expect(fetch).toHaveBeenCalledWith('/api/v1/jobs?limit=50', undefined)
      expect(store.jobs).toEqual(mockResponse.items)
    })
  })

  describe('Analyzers API', () => {
    it('should fetch analyzers', async () => {
      const mockResponse = {
        CounterAnalyser: { enabled: true, configuration: {} },
      }
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      const store = useRuntimeStore()
      await store.fetchAnalyzers()

      expect(fetch).toHaveBeenCalledWith('/api/v1/analyzers', undefined)
      expect(store.analyzers).toEqual(mockResponse)
    })

    it('should update analyzer', async () => {
      const updateResponse = { enabled: true, configuration: { test: true } }
      const fetchResponse = { CounterAnalyser: updateResponse }
      fetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => updateResponse,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => fetchResponse,
        })

      const store = useRuntimeStore()
      await store.updateAnalyzer('CounterAnalyser', true, { test: true })

      expect(fetch).toHaveBeenNthCalledWith(1, '/api/v1/analyzers/CounterAnalyser', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: true, config: { test: true } }),
      })
      expect(fetch).toHaveBeenNthCalledWith(2, '/api/v1/analyzers', undefined)
    })
  })

  describe('Settings API', () => {
    it('should fetch settings', async () => {
      const mockResponse = { settings: { theme: 'dark' } }
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      const store = useRuntimeStore()
      await store.fetchSettings()

      expect(fetch).toHaveBeenCalledWith('/api/v1/settings', undefined)
      expect(store.settings).toEqual({ theme: 'dark' })
    })

    it('should save settings', async () => {
      const saveResponse = { settings: { theme: 'light' } }
      const fetchResponse = { settings: { theme: 'light' } }
      fetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => saveResponse,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => fetchResponse,
        })

      const store = useRuntimeStore()
      store.settings = { theme: 'light' }
      await store.saveSettings()

      expect(fetch).toHaveBeenNthCalledWith(1, '/api/v1/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ settings: { theme: 'light' } }),
      })
      expect(fetch).toHaveBeenNthCalledWith(2, '/api/v1/settings', undefined)
    })
  })

  describe('Loading State', () => {
    it('should track loading state', async () => {
      fetch.mockImplementation(
        () =>
          new Promise((resolve) => {
            setTimeout(() => {
              resolve({
                ok: true,
                json: async () => ({ running: false }),
              })
            }, 10)
          })
      )

      const store = useRuntimeStore()

      expect(store.isLoading).toBe(false)
      expect(store.loadingCount).toBe(0)

      const promise = store.fetchSession()
      expect(store.loadingCount).toBe(1)
      expect(store.isLoading).toBe(true)

      await promise
      expect(store.loadingCount).toBe(0)
      expect(store.isLoading).toBe(false)
    })
  })
})
