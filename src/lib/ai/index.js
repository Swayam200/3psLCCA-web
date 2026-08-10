/**
 * Public entry point of the AI assistant package.
 *
 * IMPORT DIRECTION RULE (enforced by review, stated here for contributors):
 * this package imports from the app — schema helpers, summary utilities —
 * but nothing outside src/lib/ai and src/gui/components/ai may import from
 * it except through dynamic import() gated on the build flag:
 *
 *   import.meta.env.VITE_AI_ENABLED === 'true'
 *
 * The comparison must be written INLINE at the call site (not read from a
 * shared constant) so Vite's define replacement makes it a build-time literal
 * and the entire package — this file and everything it reaches — is dropped
 * from flag-off bundles. tests/ai/bundleExclusion.test.js enforces that.
 *
 * The build flag decides whether the code EXISTS in the bundle; the runtime
 * toggle in Settings (prefs.enabled) decides whether the UI is shown. Both
 * must be on for the assistant to appear.
 */

export { runPrompt, providerStatus, resolve, MODES } from './router.js';
export { buildAiContext, formatAmount } from './tools/context.js';
export { TOOLS, systemPrompt, executeCalls } from './tools/schema.js';
export {
    loadPrefs, savePrefs, loadKey, saveKey, clearKey, maskKey, DEFAULT_PREFS,
} from './settings.js';
export { redact, fingerprint, providerError } from './redact.js';
export { providerMeta, registerProvider } from './providers/registry.js';
export {
    loadEncoder, isEncoderReady, ENCODER_MODEL_ID, ENCODER_DOWNLOAD_MB,
} from './providers/localEncoder.js';
export {
    loadGemma, isGemmaReady, GEMMA_MODEL_ID, GEMMA_DOWNLOAD_MB,
} from './providers/functionGemma.js';
export { INTENTS, intentExamples, answerIntent } from './tools/intents.js';
