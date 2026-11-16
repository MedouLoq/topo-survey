import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development, /api and /uploads (logo) are proxied to the FastAPI backend (override with VITE_API_PROXY).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': process.env.VITE_API_PROXY || 'http://localhost:8000',
      '/uploads': process.env.VITE_API_PROXY || 'http://localhost:8000'
    }
  }
})
