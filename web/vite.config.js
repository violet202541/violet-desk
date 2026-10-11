import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发：先运行 python violet_app.py --serve --port 8765 --token devtoken，
// 再 npm run dev，打开 http://localhost:5173/?t=devtoken
export default defineConfig({
  plugins: [vue()],
  base: '/',
  build: { outDir: 'dist', emptyOutDir: true, assetsInlineLimit: 0, chunkSizeWarningLimit: 900 },
  server: { proxy: { '/api': { target: 'http://127.0.0.1:8765', changeOrigin: false } } },
})
