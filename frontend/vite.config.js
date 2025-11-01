import { defineConfig } from 'vite'  
import react from '@vitejs/plugin-react'  

// https://vitejs.dev/config/  
export default defineConfig({  
  plugins: [react()],  
  base: '/static/',
  build: {
    outDir: 'dist',
    assetsDir: 'static/assets'
  },
  server: {  
    proxy: {  
      '/api': {  
        target: 'http://localhost:8000',  
        changeOrigin: true  
      },  
      '/ws': {  
        target: 'ws://localhost:8000',  
        ws: true  
      },
      '/mcp': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }  
  }  
})