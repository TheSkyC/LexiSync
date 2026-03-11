/*
 * Copyright (c) 2025, TheSkyC
 * SPDX-License-Identifier: Apache-2.0
 */

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  base: './', 
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:20455',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://127.0.0.1:20455',
        ws: true
      }
    }
  },
  build: {
    outDir: '../src/lexisync/resources/web', 
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: `assets/[name].js`,
        chunkFileNames: `assets/[name].js`,
        assetFileNames: `assets/[name].[ext]`
      }
    }
  }
})