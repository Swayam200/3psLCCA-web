# AI Assistant Setup

3psLCCA-web includes an **optional, read-only AI assistant** that floats in
the bottom-right corner of every project page — a launcher built from the
3psLCCA logo (the three pillar circles breathe when idle, orbit while
thinking, and pulse when an answer arrives; all animation honors
`prefers-reduced-motion`). Clicking it opens a corner sheet; the Results page
also shows a slim "Ask the AI assistant" cue that opens the same sheet. The
suggestion chips follow the page you are on — the Financial Data page
suggests rate questions, construction pages suggest material questions.

It answers questions about the current project in plain language —
computed results (totals, cost drivers, pillar splits, validation messages)
**and any field of the project's own data**. The app builds a schema-driven
index of every entered input and computed line item (materials, bridge
geometry, traffic, financial parameters, …) and the assistant *searches* it:
exact word matches resolve instantly offline, paraphrases resolve through the
local embedding model, and model providers receive the index so they can
answer free-form. Nothing is hand-registered per question — new schema fields
become askable automatically.

It is deliberately limited by design:

- **Read-only.** It has no operations that modify project data. Asking it to
  change something gets a refusal pointing to the data-entry pages.
- **Grounded.** Every figure it quotes comes from the LCCA engine's computed
  results. It is never asked to calculate, estimate, or extrapolate anything.
- **Off by default, absent by default.** It only exists in builds made with
  the flag below, and only appears when the user turns it on in Settings.

Background reading: [ai-in-web-applications.md](ai-in-web-applications.md)
(how the pattern works), [ai-integration-plan.md](ai-integration-plan.md)
(the phased roadmap this implements Phase 1 of).

## Enabling it

Two switches, both required:

1. **Build flag** — set in `.env` (or the deployment's build environment):

   ```
   VITE_AI_ENABLED=true
   ```

   Without it, the AI code is not shipped at all: the production bundle
   contains none of it (enforced by `tests/ai/bundleExclusion.test.js`). With
   it, the AI ships as lazy chunks that load only when the panel is used.

2. **Runtime toggle** — Settings → **AI Assistant** → "Enable the AI
   assistant". Per-browser, off by default.

## The five modes

| Mode | What happens | Cost |
| --- | --- | --- |
| **Rules only** *(default)* | An offline pattern engine answers common questions locally. Nothing leaves the browser. | Free |
| **Local cascade** | Rules → a ~34 MB in-browser retrieval matcher → (optional, experimental) a ~200 MB in-browser generative model. Each tier hands over when its **confidence** is below its gate. No API key; nothing leaves the browser. | Free |
| **Model only** | Every question goes to the configured cloud provider. | Per question |
| **Rules → cloud fallback** | Rules first; the cloud model is called only for questions they cannot parse. | Minimal |
| **Cloud → rules fallback** | Cloud model first; rules take over if it errors or is unreachable. | Per question |

The answer panel always shows the **route with per-tier confidence** — e.g.
`rules: no match → encoder 82%` — so a fallback is never silent and the user
always knows who answered and how sure it was.

### Confidence, and how the cascade decides

- The **rules** tier is deterministic: a pattern hit is confidence **100%**,
  otherwise it declines.
- The **retrieval matcher** (E5-small embeddings via transformers.js, plain
  WASM, no GPU needed) searches the project index and the known question
  phrasings, reporting its similarity score as confidence. Two calibrated
  gates apply — data-field matches accept above **81%** (adjustable in
  Settings), question-paraphrase matches above a stricter fixed **90%** —
  and below them it refuses and hands over rather than guessing, telling you
  what its best near-miss was. The calibration story, with measurements, is
  in [ai-smoke-test.md](ai-smoke-test.md).
- **Generative tiers** (FunctionGemma, cloud models) have no calibrated
  confidence, and the UI deliberately does not invent one.

Local models download once on first use (or via the **Download now** buttons
in Settings) and are cached by the browser. The cloud modes are kept on
purpose — running the same question in `Local cascade` and `Model only` is
how we compare quality, latency, and cost.

### FunctionGemma (experimental)

The optional third tier is
[FunctionGemma 270M](https://huggingface.co/onnx-community/functiongemma-270m-it-ONNX),
a compact function-calling model running fully in-browser (WebGPU
recommended). Expect rough answers until it is fine-tuned on real phrasings —
see docs/ai-local-models-research.md for why (~58% out of the box, ~85%
fine-tuned on benchmark data) and for the Phase 3–4 plan to collect that
data. It is off by default and behind an explicit opt-in with its download
size stated.

## Providing model access

Rules mode needs nothing. The model modes need one of:

### Option A — your own API key (individuals)

Paste a [Gemini](https://aistudio.google.com/apikey) or
[Anthropic](https://console.anthropic.com/) key in Settings → AI Assistant,
and choose how long the browser keeps it: **localStorage** (survives
restarts), **sessionStorage** (until the tab closes — the default), or
**memory only** (gone on refresh).

Understand the trade-off: a saved key sits in your browser **in plain text**,
readable by any script on this origin. Only do this on a machine you trust,
use a key with a spending limit, and revoke it when done. Keys never sync to
your account or into project files, are sent only to the chosen provider,
and every provider error is redacted before display or logging
(`src/lib/ai/redact.js`).

### Option B — a proxy endpoint (organisations)

Set **Proxy URL** in Settings instead. Questions then go to your endpoint,
which holds the API key server-side — browsers never need one. The endpoint
implements a single route:

```
POST <proxyUrl>
Content-Type: application/json

{ "prompt": "...", "system": "...", "tools": [...], "provider": "gemini", "model": "" }

→ 200 { "calls": [{ "name": "answer", "args": { "text": "..." } }] }
→ 4xx/5xx { "error": "message safe to show the user" }
```

Full contract in [`src/lib/ai/providers/proxy.js`](../src/lib/ai/providers/proxy.js).
A reference implementation ships in a later phase; it is ~50 lines of FastAPI
or a serverless function.

## For contributors

### Package rules

Everything lives in `src/lib/ai/` (logic) and `src/gui/components/ai/` (UI).
The package imports from the app; **nothing outside those directories may
import from it** except through a dynamic `import()` gated on an inline
`import.meta.env.VITE_AI_ENABLED === 'true'` comparison — that inlining is
what lets Vite drop the package from flag-off bundles, and the bundle test
will fail your PR if it breaks.

### Adding a provider

A provider is a module exporting:

```js
export const DEFAULT_MODEL = 'some-model-id';
export async function generate(prompt, { apiKey, model, system, tools }) {
    // → { calls: [{ name, args }], usage?, model? }
}
```

- `calls` must only use tools declared in `src/lib/ai/tools/schema.js` —
  unknown names are rejected by the executor, so a misbehaving provider can
  annoy but not act.
- Thrown errors must be user-safe and key-free — build them with
  `providerError()` / `redact()` from `src/lib/ai/redact.js`.
- Register it in `src/lib/ai/providers/registry.js` and it appears in the
  Settings picker automatically.

Test doubles in `tests/ai/router.test.js` show the contract in miniature.

### Extending the rules engine

`src/lib/ai/providers/rules.js` is a deterministic pattern matcher over the
context object built by `src/lib/ai/tools/context.js`. Add a pattern + answer
and a test in `tests/ai/rules.test.js`. Two rules of the house: answer only
from the context (never compute new figures), and when in doubt return
`unparsed: true` rather than guessing — "I don't know" routes the question to
a model; a wrong guess misinforms silently.
