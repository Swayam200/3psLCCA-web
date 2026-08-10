/**
 * FunctionGemma provider — Tier 3 of the local cascade. EXPERIMENTAL.
 *
 * A 270M-parameter function-calling specialist (distilled from Gemma 3 270M)
 * running fully in-browser via transformers.js. Unlike the rules and encoder
 * tiers it is genuinely generative: it can attempt free-form questions and
 * emits tool calls in a strict control-token format:
 *
 *   <start_function_call>call:answer{text:<escape>…<escape>}<end_function_call>
 *
 * Expectations, stated honestly (docs/ai-local-models-research.md §3):
 * out of the box this model scores ~58% on function-calling benchmarks; it
 * becomes production-grade (~85%) only after fine-tuning on domain phrasings,
 * which is the Phase 3–4 plan once the phrasing logs exist. Until then it is
 * the experimental last local resort — and the executor's validation plus the
 * read-only tool registry mean a wrong guess is an error message, never a
 * data change.
 *
 * Download is a few hundred MB, WebGPU strongly recommended — strictly opt-in.
 */

import { TOOLS } from '../tools/schema.js';

export const GEMMA_MODEL_ID = 'onnx-community/functiongemma-270m-it-ONNX';
export const GEMMA_DOWNLOAD_MB = 200; // order of magnitude, quantization-dependent

// ---------------------------------------------------------------------------
// Pure output parser — unit-testable without the model.
// ---------------------------------------------------------------------------

const CALL_BLOCK = /<start_function_call>\s*call:([\w.-]+)\{([\s\S]*?)\}\s*<end_function_call>/g;

/** Split `key:value,key:value` at top-level commas (values may hold commas inside <escape> pairs). */
const splitArgs = (body) => {
    const parts = [];
    let current = '';
    let inEscape = false;
    for (let i = 0; i < body.length; i++) {
        if (body.startsWith('<escape>', i)) {
            inEscape = !inEscape;
            current += '<escape>';
            i += 7;
            continue;
        }
        if (body[i] === ',' && !inEscape) {
            parts.push(current);
            current = '';
            continue;
        }
        current += body[i];
    }
    if (current.trim()) parts.push(current);
    return parts;
};

const parseValue = (raw) => {
    const trimmed = raw.trim();
    const escaped = trimmed.match(/^<escape>([\s\S]*)<escape>$/);
    if (escaped) return escaped[1];
    if (/^-?\d+(\.\d+)?$/.test(trimmed)) return Number(trimmed);
    if (trimmed === 'true') return true;
    if (trimmed === 'false') return false;
    return trimmed;
};

/**
 * Parse FunctionGemma's generation into [{ name, args }]. Unparseable blocks
 * are skipped rather than guessed at; an empty array means "no valid call".
 */
export function parseFunctionCalls(text) {
    const calls = [];
    for (const match of String(text || '').matchAll(CALL_BLOCK)) {
        const [, name, body] = match;
        const args = {};
        for (const part of splitArgs(body)) {
            const colon = part.indexOf(':');
            if (colon === -1) continue;
            const key = part.slice(0, colon).trim();
            if (key) args[key] = parseValue(part.slice(colon + 1));
        }
        calls.push({ name, args });
    }
    return calls;
}

// ---------------------------------------------------------------------------
// Lazy model loading — nothing downloads until the tier is explicitly used.
// ---------------------------------------------------------------------------

let enginePromise = null;
let ready = false;

export const isGemmaReady = () => ready;

export function loadGemma(onProgress = () => {}) {
    enginePromise ||= (async () => {
        onProgress('Loading transformers.js…');
        const { AutoModelForCausalLM, AutoTokenizer } = await import('@huggingface/transformers');
        onProgress(`Fetching ${GEMMA_MODEL_ID} (~${GEMMA_DOWNLOAD_MB} MB, cached after first download)…`);
        const device = (typeof navigator !== 'undefined' && navigator.gpu) ? 'webgpu' : 'wasm';
        const tokenizer = await AutoTokenizer.from_pretrained(GEMMA_MODEL_ID);
        const model = await AutoModelForCausalLM.from_pretrained(GEMMA_MODEL_ID, {
            dtype: 'q4',
            device,
            progress_callback: (p) => {
                if (p.status === 'progress' && p.file?.endsWith('.onnx')) {
                    onProgress(`Downloading model… ${Math.round(p.progress || 0)}%`);
                }
            },
        });
        ready = true;
        onProgress(`FunctionGemma ready (${device}).`);
        return { tokenizer, model };
    })();
    enginePromise.catch(() => { enginePromise = null; });
    return enginePromise;
}

/** Tool declarations in the JSON-schema shape the chat template consumes. */
const toolDeclarations = () => TOOLS.map((tool) => ({
    type: 'function',
    function: { name: tool.name, description: tool.description, parameters: tool.parameters },
}));

export async function generate(prompt, { context, runner } = {}) {
    // `runner` is the injectable inference function for tests:
    // (prompt, context) → generated text.
    const generated = runner
        ? await runner(prompt, context)
        : await realGenerate(prompt, context);

    const calls = parseFunctionCalls(generated);

    if (!calls.length) {
        return {
            unparsed: true,
            calls: [{
                name: 'answer',
                args: {
                    text: 'The local FunctionGemma model did not produce a usable tool call for '
                        + 'that question. Try rephrasing, or configure a cloud provider in '
                        + 'Settings → AI Assistant for free-form questions.',
                },
            }],
        };
    }
    // Generative output has no calibrated confidence — deliberately undefined.
    return { calls, model: GEMMA_MODEL_ID };
}

async function realGenerate(prompt, context) {
    const { tokenizer, model } = await loadGemma();

    const messages = [
        {
            role: 'developer',
            content: 'You are the read-only assistant of 3psLCCA, a bridge life-cycle cost tool. '
                + 'Answer ONLY with a function call. Quote figures exactly from this context, never '
                + 'invent numbers:\n'
                + JSON.stringify(context || {}),
        },
        { role: 'user', content: String(prompt || '') },
    ];

    const inputs = tokenizer.apply_chat_template(messages, {
        tools: toolDeclarations(),
        add_generation_prompt: true,
        return_dict: true,
    });

    const output = await model.generate({ ...inputs, max_new_tokens: 256 });
    const decoded = tokenizer.batch_decode(
        output.slice(null, [inputs.input_ids.dims[1], null]),
        { skip_special_tokens: false },
    );
    return decoded[0] || '';
}
