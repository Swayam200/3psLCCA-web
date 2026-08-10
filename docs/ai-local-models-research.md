# Research: Free, Browser-Local AI for the 3psLCCA Assistant

**Question investigated:** can we avoid paid model APIs (Gemini/Claude/OpenAI)
by running a small model in the browser via WASM/WebGPU — specifically, is
TinyBERT a viable engine for our CRUD-over-project-data use case?

**Short answer:** yes to the direction, with one important correction and one
big tailwind. The correction: **TinyBERT alone cannot produce tool calls** —
it's an encoder, not a generator — but for *our* problem that turns out to be
fine, because our problem decomposes into parts an encoder can do plus parts
we already solve deterministically. The tailwind: as of 2026 **WebGPU is
enabled in the stable releases of every major browser engine** (Chrome/Edge,
Firefox 141+ desktop, Safari 26+ including iOS), which makes browser inference
a mainstream target rather than a Chrome-only experiment.

---

## 1. What TinyBERT actually is (and the correction that matters)

TinyBERT is a distilled BERT **encoder**: 4 layers, ~14.5M parameters, ~87%
smaller than BERT while keeping ~97% of its accuracy on classification-style
benchmarks. Quantized ONNX builds are **14.7–55 MB** — genuinely tiny.

What an encoder can do, entirely in the browser via ONNX Runtime Web /
transformers.js:

- **classify** a sentence into one of N known intents,
- **tag tokens** (NER / slot filling — "which words are the quantity, which
  are the material name"),
- **embed** text into vectors for similarity search.

What it structurally **cannot** do: generate text. It will never emit
`{"name": "scale_rates", "args": {...}}`, answer a free-form question, or
write a report paragraph. The dev.to article's own demos — sentiment analysis,
text classification — are exactly the encoder envelope. So "use TinyBERT as
the AI" really means "use TinyBERT as an intent classifier / slot extractor in
front of our existing deterministic execution" — which is a real and
well-studied architecture (it is how the Alexa/Siri generation of NLU worked:
joint intent classification + slot filling, BERT-style).

## 2. Why that limitation barely hurts *our* use case

Our tool-calling problem decomposes cleanly:

| Sub-problem | Example | Needs a generative model? |
| --- | --- | --- |
| **Intent** — which operation? | "bump up", "raise", "make higher" → `scale_rates` | **No** — classification over ~a dozen intents |
| **Numeric slots** — values, percentages, units | "8%", "240 m³", "9500" | **No** — regex is *more* reliable than any LLM here |
| **Entity slots** — section, material row | "foundation", "the MS railing" | **No** — alias tables + the fuzzy row-matcher already in the executor |
| **Free-form Q&A / narration** | "why is my carbon cost high?" | **Yes** — genuinely generative |

The only thing the paid model is doing for CRUD edits is **paraphrase-robust
intent mapping** — surviving the hundred phrasings the regex rules don't know.
That is precisely the part small local models are good at. The generative
tail (open-ended questions, report narration) is the only part that truly
wants a big model, and it is optional by design.

## 3. The menu, cheapest to heaviest

All of these run fully client-side; all are free; all slot into the existing
provider registry (`src/lib/ai/providers/registry.js`) as just another
provider.

### Tier 0 — regex rules (shipped, Phase 1)
0 MB, 0 ms, deterministic. The floor everything else must beat.

### Tier 1 — embedding similarity («rules++») — ~23 MB, no training
Run a small sentence-embedding model (e.g. `all-MiniLM-L6-v2`, ~23 MB
quantized, runs fine on plain WASM — no WebGPU needed) via **transformers.js**.
Maintain a library of canonical phrasings for each intent the rules already
handle ("increase all {section} rates by {pct}%", …). Embed the user's
sentence, cosine-match against the library, dispatch to the *existing* rule
handler, extract slots with the *existing* regex/matcher.

- **Wins:** paraphrase robustness immediately; zero training; zero API cost;
  works offline; a ~23 MB one-time download is in-family for this app (we
  already ship a Pyodide runtime + core wheel from a CDN for calculations).
- **Limits:** can only map to intents we've enumerated; low-confidence matches
  must fall through to "I don't understand" (same `unparsed` contract as
  today).
- **Effort:** small. This is the highest value-per-effort item on the list.

### Tier 2 — fine-tuned encoder (the actual TinyBERT idea) — 15–55 MB
Fine-tune a TinyBERT/MobileBERT-class model for **joint intent classification
+ slot filling** on our own phrasing data, export to ONNX, run in-browser.

- **Wins:** more precise than similarity matching, still tiny, still
  WASM-friendly, fully open (weights + training script in the repo — anyone
  can retrain; a good open-source story).
- **Limits:** needs labeled training data **we do not have yet** — and this is
  exactly what the Phase 1/2 rejection-and-phrasing logs are designed to
  collect. Also needs a small training pipeline (Python, one notebook).
- **Verdict:** right idea, wrong moment. It becomes viable the month we have
  a few hundred real phrasings.

### Tier 3 — tiny generative function-callers — 125 MB–1 GB, WebGPU
Two credible routes, both new since the articles you linked were written:

- **FunctionGemma (Google, Dec 2025):** a 270M-parameter function-calling
  specialist distilled from Gemma 3 270M, with dedicated control tokens for
  function declarations/calls, official browser demos on transformers.js +
  WebGPU, ~125–300 MB quantized. Reported **58% accuracy out of the box on a
  mobile-actions benchmark → 85% after domain fine-tuning** — Google's own
  framing is "small function callers need domain data more than prompt
  engineering."
- **WebLLM + Qwen2.5-0.5B/1.5B (~400 MB / ~1 GB):** OpenAI-compatible API in
  the browser with **grammar-constrained JSON output** (XGrammar), so even a
  small model is *syntactically* incapable of emitting malformed tool calls.
  Semantic correctness (right tool, right values) is still the model's
  problem — grammar constraints don't fix a wrong guess.

- **Wins:** real tool calls and real (modest) Q&A, fully local, genuinely
  replaces the paid API for the CRUD path on capable hardware.
- **Limits:** hundreds of MB (must be an explicit opt-in download, cached in
  browser storage); needs WebGPU for usable speed (now mainstream, but
  low-RAM phones remain rough); base accuracy on *our* schema will be Tier-0
  quality until fine-tuned; model files can't live on GitHub Pages (100 MB
  file cap) — host on Hugging Face Hub's free CDN with SRI-style pinning,
  the same provenance pattern we already use for the calculation engine.

### Tier 4 — Chrome's built-in Gemini Nano (Prompt API)
Now officially launched (Chrome 138+): the browser ships the model, we
download nothing, and it supports schema-constrained output. But it is
Chrome-only, requires ~22 GB free disk + 4 GB VRAM on the user's machine, and
is not available on mobile. **A free bonus provider where present, not a
foundation** for a cross-browser open-source tool.

## 4. Why our architecture makes this nearly free to adopt

Three properties we already built are doing the heavy lifting:

1. **Providers are a registry.** Each tier above is one new module
   implementing `generate(prompt, opts) → { calls }` — the settings UI,
   router, and modes pick it up automatically. The routing modes compose
   naturally into: `rules → local model → (optional, explicit) cloud`.
2. **The executor validates everything and unknown tools are rejected.** A
   58%-accurate local model is therefore *annoying*, never *dangerous*: a
   wrong tool call fails validation or produces a visibly wrong diff in the
   Phase-2 confirm modal. Small-model unreliability is contained by
   construction, which is precisely what makes small models usable at all.
3. **The route display already tells the user who answered.** "rules → local
   model" vs "→ gemini" is the honesty mechanism, and it already exists.

## 5. Recommendation

Staged, mapped onto the existing plan (docs/ai-integration-plan.md):

1. **Now (Phase 1.5, small PR):** add a `local` provider implementing
   **Tier 1** (MiniLM embeddings + canonical-phrasing matcher) behind an
   explicit "download local model (~23 MB)" button in Settings → AI Assistant.
   This alone removes the paid API from the majority of CRUD phrasings and
   works offline.
2. **Phase 2 (unchanged, plus one button):** the propose-and-confirm write
   path as planned. Add an opt-in **"export my phrasings"** button that dumps
   the local log of prompts + how they were routed/resolved — the community
   data-collection mechanism that makes Tiers 2–3 trainable. No telemetry;
   users donate data by explicit action or not at all.
3. **Phase 3–4:** fine-tune **FunctionGemma 270M** on the collected phrasings
   (and/or a TinyBERT joint intent+slot model as the ultra-light variant),
   publish the training notebook in the repo, register it as a provider with
   an opt-in download. At that point the default experience is: rules →
   local model, fully free, fully offline, no key anywhere — and Gemini/Claude
   remain what they should be: an optional top tier for people who want
   free-form Q&A at frontier quality.
4. **Opportunistic:** register Chrome's Prompt API as a zero-download bonus
   provider where the browser offers it.

### Retrieval over the project itself (implemented)

The Tier-1 encoder does more than intent matching: the app builds a
**schema-driven index of every project field** (`src/lib/ai/tools/projectIndex.js`
— a generic walker over all sections; no per-question code) and the local
tiers *search* it — lexically at the rules tier, semantically at the encoder
tier. The generative tiers receive the full index in context. This replaced
an earlier hand-written synonym table, which was a poor man's embedding.

**Tuning history (measured, see docs/ai-smoke-test.md):** the first encoder
was MiniLM, a *symmetric* sentence-similarity model — and the smoke test
showed correct retrievals and junk overlapping in one 53–61% confidence band
no threshold could split ("which binder was specified?" → the right concrete
row at 39%, refused; "write me a poem" → accepted at 61%). Swapping to
**E5-small-v2** (asymmetric retrieval, `query:`/`passage:` prefixes, ~34 MB)
fixed the retrieval side — correct entries ≥ 82, junk < 80 — and calibration
produced a **two-gate design**: entry hits gated at 81% (user-adjustable),
intent-example hits at a fixed 90% (question↔question matching stays
symmetric, so off-topic bridge-flavored queries reach the high 80s). Battery
result: 16/24 → 20/24 correct, remaining misses documented in the smoke-test
doc rather than patched.

### Implementation status

Tiers 0–3 are now wired into the app as the **"Local cascade"** mode
(`rules → encoder → FunctionGemma`) with per-tier confidence gating — see
docs/ai-setup.md. Tier 1 (MiniLM matcher) is fully functional; Tier 3
(FunctionGemma) is an experimental opt-in pending the fine-tuning data from
Phase 2's phrasing logs. Tier 4 (Chrome's built-in Gemini Nano) was
deliberately skipped: a Chrome-only tier sits poorly with an open-source
project whose users are on Firefox too. Cloud providers remain available as
the comparison baseline.

### The one-sentence version

Don't ask "which small model can replace Gemini" — split the problem: keep
slots deterministic, make intent matching semantic with a ~23 MB embedding
model now, and grow into a fine-tuned 270M function-caller once Phase 2's
logs give us the training data; the provider registry means each step is one
new file, and the validation gate means none of it can corrupt a project.

---

## Sources

- [Run AI Models Entirely in the Browser Using WebAssembly + ONNX Runtime (dev.to)](https://dev.to/hexshift/run-ai-models-entirely-in-the-browser-using-webassembly-onnx-runtime-no-backend-required-4lag)
- [Running AI Models Locally in the Browser (Mad Devs)](https://maddevs.io/writeups/running-ai-models-locally-in-the-browser/)
- [Transformers.js v3: WebGPU support (Hugging Face)](https://www.huggingface.co/blog/transformersjs-v3) · [WebGPU guide](https://huggingface.co/docs/transformers.js/en/guides/webgpu)
- [WebGPU now supported in major browsers (web.dev)](https://web.dev/blog/webgpu-supported-major-browsers) · [Implementation status (gpuweb wiki)](https://github.com/gpuweb/gpuweb/wiki/Implementation-Status)
- [WebLLM — in-browser LLM inference engine](https://webllm.mlc.ai/) · [JSON-schema example](https://github.com/mlc-ai/web-llm/blob/main/examples/json-schema/src/json_schema.ts)
- [Introducing Gemma 3 270M (Google Developers Blog)](https://developers.googleblog.com/en/introducing-gemma-3-270m/) · [Fine-tune Gemma 3 270M and run on-device](https://developers.googleblog.com/en/own-your-ai-fine-tune-gemma-3-270m-for-on-device/)
- [FunctionGemma: compact function-calling specialist (MarkTechPost)](https://www.marktechpost.com/2025/12/26/from-gemma-3-270m-to-functiongemma-how-google-ai-built-a-compact-function-calling-specialist-for-edge-workloads/)
- [Chrome Prompt API (Chrome for Developers)](https://developer.chrome.com/docs/ai/prompt-api) · [Built-in AI overview](https://developer.chrome.com/docs/ai/built-in)
- [TinyBERT NER ONNX build (Hugging Face)](https://huggingface.co/onnx-community/TinyBERT-finetuned-NER-ONNX) · [BERT for joint intent classification and slot filling (paper)](https://ar5iv.labs.arxiv.org/html/1902.10909)
