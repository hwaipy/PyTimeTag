import { defineConfig } from 'vitest/config'
import path from 'path'

export default defineConfig({
  test: {
    environment: 'node',
    globals: true,
    include: ['src/**/*.{test,spec}.{js,ts}'],
    coverage: {
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'src/**/*.{test,spec}.{js,ts}',
      ]
    }
  },
  resolve: {
    alias: {
      '~': path.resolve(__dirname, './src'),
      'src': path.resolve(__dirname, './src')
    }
  }
})
