// import { defineConfig } from 'vite'
// import react from '@vitejs/plugin-react'

// export default defineConfig({
//   plugins: [react()],
//   server: {
//     port: 5000,
//     proxy: {
//       '/api': {
//         target: 'http://localhost:5000',
//         changeOrigin: true
//       }
//     }
//   }
// })
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173, // Changed from 5000 to 5173 to avoid conflict with Flask
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000', // Points to your Python Backend
        changeOrigin: true,
        secure: false,
      }
    }
  }
})
