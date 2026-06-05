import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/incidents': 'http://localhost:8000',
      '/responders': 'http://localhost:8000',
      '/incident': 'http://localhost:8000',
      '/acknowledge': 'http://localhost:8000',
    },
  },
})
