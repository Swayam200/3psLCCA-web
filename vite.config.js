import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { copyFileSync, existsSync } from 'node:fs'
import { join, resolve } from 'node:path'
import process from 'node:process'

// GitHub Pages (and most static hosts) serve their own 404 page for deep
// links like /project/<id>/Results on refresh. Shipping the app shell as
// 404.html makes those URLs load the SPA instead.
const spaFallback = () => {
  let outputRoot = resolve(process.cwd(), 'dist')
  return {
    name: 'lcca-spa-404-fallback',
    configResolved(config) {
      outputRoot = resolve(config.root, config.build.outDir)
    },
    closeBundle() {
      const indexHtml = join(outputRoot, 'index.html')
      if (existsSync(indexHtml)) {
        copyFileSync(indexHtml, join(outputRoot, '404.html'))
      }
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  base: process.env.VITE_BASE_PATH || '/',
  plugins: [react(), spaFallback()],
})
