/**
 * Local encoder provider — Tier 1 of the local cascade.
 *
 * A ~34 MB retrieval-embedding model (E5-small-v2, quantized ONNX) running
 * fully in-browser via transformers.js on plain WASM (no WebGPU). It embeds
 * the user's sentence and cosine-matches it against two candidate sets in one
 * similarity space: the canonical intent phrasings (tools/intents.js) and
 * every entry of the schema-driven project index (tools/projectIndex.js).
 *
 * WHY E5 AND NOT A PLAIN SENTENCE-SIMILARITY MODEL: matching a short question
 * against a data-field label is an ASYMMETRIC retrieval task. The first
 * implementation used MiniLM (symmetric) and the smoke test
 * (docs/ai-smoke-test.md) measured the consequence: correct retrievals and
 * junk landed in one overlapping 53–61% band that no threshold could split.
 * E5 is trained query→passage with explicit "query: " / "passage: " prefixes,
 * which is exactly this task's shape.
 *
 * Confidence contract: confidence = best cosine similarity. NOTE that E5's
 * contrastive training compresses cosines upward (~0.7–1.0), so the default
 * threshold here is calibrated for E5 and is NOT comparable to thresholds
 * used with other embedding models — settings.js discards a stored threshold
 * when the encoder model changes for this reason. Below the threshold the
 * provider reports `unparsed` and the cascade falls through rather than
 * guessing.
 *
 * The model download (one-time, cached by the browser) happens only on
 * explicit user action or first cascade use — never at page load.
 */

import { intentExamples, answerIntent } from '../tools/intents.js';

export const ENCODER_MODEL_ID = 'Xenova/e5-small-v2';
export const ENCODER_DOWNLOAD_MB = 34;

/**
 * TWO gates, calibrated from the measured battery (docs/ai-smoke-test.md):
 *
 * - Entry gate (the Settings slider): query→passage retrieval is E5's home
 *   game and separates cleanly — correct entries scored ≥ 0.818, junk's best
 *   entries < 0.798. Default sits in that gap.
 * - Intent gate (fixed, higher): question↔question matching is symmetric, so
 *   E5 behaves like any sentence model there and off-topic questions ("write
 *   me a poem about bridges" → "Tell me about this bridge", 0.89) overlap
 *   with loose paraphrases. Legitimate intent matches measured ≥ 0.92.
 */
export const DEFAULT_ENCODER_THRESHOLD = 0.81;
export const DEFAULT_INTENT_THRESHOLD = 0.9;

// ---------------------------------------------------------------------------
// Pure matcher — dependency-injected embedder, fully unit-testable without
// the real model.
// ---------------------------------------------------------------------------

const dot = (a, b) => {
    let sum = 0;
    for (let i = 0; i < a.length; i++) sum += a[i] * b[i];
    return sum;
};

/** Cheap fingerprint of an index so its embeddings can be cached per project. */
const indexHash = (texts) =>
    `${texts.length}:${texts.reduce((n, t) => n + t.length, 0)}:${texts[0] || ''}:${texts.at(-1) || ''}`;

/**
 * Build a matcher using any embed function (texts) → number[][] of
 * L2-normalised vectors. Candidates live in ONE similarity space:
 *
 *   - the intent examples (aggregate questions — totals, drivers, …)
 *   - every entry of the schema-driven project index (tools/projectIndex.js)
 *
 * The second kind is what makes this robust: "which binder was specified?"
 * needs no synonym table, because it simply embeds near the concrete
 * material rows. The index embeddings are cached per project fingerprint and
 * recomputed only when the data changes.
 */
export function createMatcher(embed) {
    const examples = intentExamples();
    let examplesPromise = null;
    let indexCache = { hash: null, vectors: [], entries: [] };

    // E5 prefix convention: "query: " on the question side, "passage: " on
    // the document side. Intent examples are question↔question (a symmetric
    // pair), so both sides carry "query: "; index entries are documents.
    const exampleVectors = () => {
        examplesPromise ||= embed(examples.map((e) => `query: ${e.text}`));
        return examplesPromise;
    };

    const entryVectors = async (entries) => {
        // Embed the SEMANTIC part only (section + label). Quantities, units
        // and rates in the display text dilute similarity — "binder" should
        // compete against "Foundation material — Cement Concrete M35", not
        // against "… 500 m³ — Cubic Metre @ 8500".
        const texts = entries.map((entry) => `passage: ${entry.section} — ${entry.label}`);
        const hash = indexHash(texts);
        if (indexCache.hash !== hash) {
            indexCache = { hash, entries, vectors: texts.length ? await embed(texts) : [] };
        }
        return indexCache;
    };

    // Returns the best candidate of EACH type — the two types have separately
    // calibrated acceptance gates (see the threshold constants above).
    return async function match(text, indexEntries = []) {
        const [exVectors, index, [query]] = await Promise.all([
            exampleVectors(),
            entryVectors(indexEntries),
            embed([`query: ${text}`]),
        ]);

        let bestIntent = { score: -1, intent: null, example: null };
        for (let i = 0; i < exVectors.length; i++) {
            const score = dot(query, exVectors[i]);
            if (score > bestIntent.score) {
                bestIntent = { score, intent: examples[i].intent, example: examples[i].text };
            }
        }

        let bestEntry = { score: -1, entry: null };
        for (let i = 0; i < index.vectors.length; i++) {
            const score = dot(query, index.vectors[i]);
            if (score > bestEntry.score) {
                bestEntry = { score, entry: index.entries[i] };
            }
        }
        return { bestIntent, bestEntry };
    };
}

// ---------------------------------------------------------------------------
// Real embedder — lazy transformers.js, loaded only when actually used.
// ---------------------------------------------------------------------------

let pipelinePromise = null;
let ready = false;

export const isEncoderReady = () => ready;

/**
 * Load (and on first ever use, download) the embedding model. `onProgress`
 * receives human-readable status strings for the settings UI.
 */
export function loadEncoder(onProgress = () => {}) {
    pipelinePromise ||= (async () => {
        onProgress('Loading transformers.js…');
        // Dynamic import: transformers.js (~1 MB of JS) stays out of every
        // bundle until a local tier is actually used.
        const { pipeline } = await import('@huggingface/transformers');
        onProgress(`Fetching ${ENCODER_MODEL_ID} (~${ENCODER_DOWNLOAD_MB} MB, cached after first download)…`);
        const extractor = await pipeline('feature-extraction', ENCODER_MODEL_ID, {
            dtype: 'q8',
            progress_callback: (p) => {
                if (p.status === 'progress' && p.file?.endsWith('.onnx')) {
                    onProgress(`Downloading model… ${Math.round(p.progress || 0)}%`);
                }
            },
        });
        ready = true;
        onProgress('Local encoder ready.');
        return extractor;
    })();
    pipelinePromise.catch(() => { pipelinePromise = null; });
    return pipelinePromise;
}

const realEmbed = async (texts) => {
    const extractor = await loadEncoder();
    const output = await extractor(texts, { pooling: 'mean', normalize: true });
    return output.tolist();
};

let defaultMatcher = null;

/**
 * Provider contract. `options.embedder` / `options.threshold` are injectable
 * for tests and tuning; defaults use the real model and the stored threshold.
 */
export async function generate(prompt, { context, threshold, intentThreshold, embedder } = {}) {
    const entryGate = Number.isFinite(threshold) ? threshold : DEFAULT_ENCODER_THRESHOLD;
    const intentGate = Number.isFinite(intentThreshold) ? intentThreshold : DEFAULT_INTENT_THRESHOLD;
    const matcher = embedder ? createMatcher(embedder) : (defaultMatcher ||= createMatcher(realEmbed));

    const { bestIntent, bestEntry } = await matcher(String(prompt || '').trim(), context?.index || []);

    // Grounded data first: if the question retrieves a concrete field above
    // the entry gate, that answer is self-verifying (the user sees exactly
    // which field matched) and beats a looser intent paraphrase.
    if (bestEntry.entry && bestEntry.score >= entryGate) {
        return {
            calls: [{ name: 'answer', args: { text: `From the project data: ${bestEntry.entry.text}.` } }],
            intent: 'data_lookup',
            matchedExample: bestEntry.entry.label,
            confidence: Number(bestEntry.score.toFixed(3)),
        };
    }

    if (bestIntent.intent && bestIntent.score >= intentGate) {
        return {
            calls: [{ name: 'answer', args: { text: answerIntent(bestIntent.intent, context || {}, prompt) } }],
            intent: bestIntent.intent,
            matchedExample: bestIntent.example,
            confidence: Number(bestIntent.score.toFixed(3)),
        };
    }

    const best = bestIntent.score >= bestEntry.score
        ? { score: bestIntent.score, label: bestIntent.example, gate: intentGate }
        : { score: bestEntry.score, label: bestEntry.entry?.text, gate: entryGate };

    return {
        unparsed: true,
        confidence: Number(Math.max(0, best.score).toFixed(3)),
        calls: [{
            name: 'answer',
            args: {
                text: `The local encoder's best match (${(best.score * 100).toFixed(0)}% similar to `
                    + `"${best.label}") is below its ${(best.gate * 100).toFixed(0)}% confidence threshold, `
                    + 'so it will not guess.',
            },
        }],
    };
}
