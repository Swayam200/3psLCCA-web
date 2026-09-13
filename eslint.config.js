import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  // Verbatim upstream runtimes and generated output are not maintained here.
  globalIgnores(['dist', 'coverage', 'test-results', 'playwright-report', 'public/vendor/**', 'public/report-smoke/**']),
  {
    files: ['**/*.{js,jsx,mjs}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
  },
  {
    files: ['tests/**/*.{js,jsx}', 'scripts/**/*.mjs', '*.config.{js,mjs}'],
    languageOptions: {
      globals: { ...globals.browser, ...globals.node },
    },
  },
  {
    // ai-demo/ is a standalone Node server; only its public/ folder is browser code.
    files: ['ai-demo/**/*.js'],
    ignores: ['ai-demo/public/**/*.js'],
    languageOptions: { globals: globals.node },
  },
])
