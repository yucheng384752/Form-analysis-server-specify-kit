import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/',
  
  // Development server configuration
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    cors: true,
    // hmr: {
    //   host: 'localhost',
    //   port: 5173,
    //   clientPort: 18003
    // },
    // Fix SPA routing - serve index.html for all routes
    middlewareMode: false,
    fs: {
      strict: false
    },
    proxy: {
      // Proxy API calls to backend during development
      '/api': {
        target: process.env.NODE_ENV === 'development' && process.env.DOCKER_ENV 
          ? 'http://backend:8000' 
          : process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
      '/healthz': {
        target: process.env.NODE_ENV === 'development' && process.env.DOCKER_ENV 
          ? 'http://backend:8000' 
          : process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      }
    }
  },
  
  // Preview server configuration (for production build testing)
  preview: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    cors: true,
  },
  
  // Build configuration
  build: {
    outDir: 'dist',
    sourcemap: true,
    target: 'esnext',
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          utils: ['axios']
        }
      }
    }
  },
  
  // Path resolution
  resolve: {
    alias: {
      '@': resolve(__dirname, './src'),
      '@components': resolve(__dirname, './src/components'),
      '@pages': resolve(__dirname, './src/pages'),
      '@lib': resolve(__dirname, './src/lib'),
      '@types': resolve(__dirname, './src/types'),
      '@utils': resolve(__dirname, './src/utils'),
    }
  },
  
  // Environment variable prefix
  envPrefix: 'VITE_',
  
  // Optimize dependencies
  optimizeDeps: {
    include: ['react', 'react-dom', 'react-router-dom', 'axios']
  },
  
  // CSS configuration
  css: {
    devSourcemap: true,
    modules: {
      localsConvention: 'camelCase'
    }
  }
})