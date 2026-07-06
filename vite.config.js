import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { cpSync, createReadStream, existsSync, mkdirSync } from 'node:fs'
import { extname, join, resolve } from 'node:path'
import process from 'node:process'

const PYODIDE_FILES = [
  'pyodide.asm.mjs',
  'pyodide.asm.wasm',
  'pyodide-lock.json',
  'pyodide.mjs',
  'python_stdlib.zip',
]

const CONTENT_TYPES = {
  '.json': 'application/json',
  '.mjs': 'text/javascript',
  '.wasm': 'application/wasm',
  '.whl': 'application/zip',
  '.zip': 'application/zip',
}

const wasmStaticAssets = () => {
  const projectRoot = process.cwd()
  const pyodideRoot = resolve(projectRoot, 'node_modules/pyodide')
  const generatedRoot = resolve(projectRoot, '.wasm-assets/lcca-wasm')
  let outputRoot = resolve(projectRoot, 'dist')
  let basePath = '/'

  return {
    name: 'lcca-wasm-static-assets',
    configResolved(config) {
      outputRoot = resolve(config.root, config.build.outDir)
      basePath = config.base
    },
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        const rawPath = decodeURIComponent((request.url || '').split('?')[0])
        const requestPath = basePath !== '/' && rawPath.startsWith(basePath)
          ? `/${rawPath.slice(basePath.length)}`
          : rawPath
        let source
        if (requestPath.startsWith('/pyodide/')) {
          source = join(pyodideRoot, requestPath.slice('/pyodide/'.length))
        } else if (requestPath.startsWith('/lcca-wasm/')) {
          source = join(generatedRoot, requestPath.slice('/lcca-wasm/'.length))
        }
        if (!source || !existsSync(source)) {
          next()
          return
        }
        response.setHeader('Content-Type', CONTENT_TYPES[extname(source)] || 'application/octet-stream')
        createReadStream(source).pipe(response)
      })
    },
    closeBundle() {
      const pyodideOut = join(outputRoot, 'pyodide')
      mkdirSync(pyodideOut, { recursive: true })
      for (const file of PYODIDE_FILES) {
        cpSync(join(pyodideRoot, file), join(pyodideOut, file))
      }
      cpSync(generatedRoot, join(outputRoot, 'lcca-wasm'), { recursive: true })
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  base: process.env.VITE_BASE_PATH || '/',
  plugins: [react(), wasmStaticAssets()],
  build: {
    rollupOptions: {
      input: {
        app: resolve(process.cwd(), 'index.html'),
        wasmSmoke: resolve(process.cwd(), 'wasm-smoke.html'),
        swiftlatexReportSmoke: resolve(process.cwd(), 'swiftlatex-report-smoke.html'),
      },
    },
  },
})
