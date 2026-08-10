# 3psLCCA — AI editing demo

A standalone, throwaway prototype showing how an AI layer would work over
3psLCCA data. It implements **CRUD over a small subset of the real project
schema**, then lets the same operations be driven by natural-language prompts
through tool calling.

Companion document:
[`docs/ai-in-web-applications.md`](../docs/ai-in-web-applications.md).

It is deliberately **not** wired into the React app. Nothing here imports from
`src/`, and nothing in `src/` imports from here — delete the folder and the
project is unchanged.

## Run it

```bash
node ai-demo/server.js
```

**Zero dependencies. No `npm install`, no build step, no API key.** Requires
Node 18+ (for global `fetch`). Open <http://localhost:4173>.

Run the tests (server must be running):

```bash
node --test ai-demo/test.js
```

## Four modes

Click **⚙** in the top bar. Everything below is configured there — no restart,
no env vars needed.

| Mode | What happens | Why you'd pick it |
| --- | --- | --- |
| **Rules only** *(default)* | Offline regex engine. Never leaves your machine. | Free, instant, works on a plane. Handles the phrasings in the example chips. |
| **Model only** | Every prompt goes to the API. | Most capable — understands phrasings nobody anticipated. |
| **Rules → model fallback** | Try the rules; call the API **only** when they can't parse it. | The cheapest useful mix. Common requests cost nothing and answer in ~1 ms; the long tail still works. |
| **Model → rules fallback** | Use the API; drop to the rules if it errors, times out, or is rate-limited. | The most resilient. The feature keeps working during an outage instead of dying. |

The last two are the interesting ones, and they optimise for **opposite
things** — cost versus availability. Which you want depends on whether your
worry is the bill or the pager.

The **route is always shown** above the result: `rules` for a local hit,
`rules: no match → gemini` when it escalated. A silent fallback would be worse
than no fallback — you need to know whether a model or a regex answered you.

## Using your own API key

Paste it into **⚙ Settings**. You choose how long it is kept:

| Choice | Stored in | Survives |
| --- | --- | --- |
| **On this browser** | `localStorage` | Restarts. Convenient, and the riskiest. |
| **Until I close the tab** *(default)* | `sessionStorage` | The tab only. |
| **Don't keep it** | nothing — memory only | Not even a refresh. |

**Test key** validates it with one cheap real call, so you find out here rather
than on your first real prompt.

### What the demo does to keep it safe

- The key goes in an `x-provider-key` **header**, never the JSON body — so
  nothing that gets logged or replayed as a body contains it.
- The server uses it for **one upstream call** and never writes it to disk, to a
  log, or into any response. `/api/ai/status` returns at most a fingerprint
  (`••••1234`).
- **Every provider error is redacted** before it reaches a log, a tooltip, or
  your screen ([`lib/ai/redact.js`](lib/ai/redact.js)). Gemini puts the key in
  the query string and echoes requests back in some errors — this is a real
  leak path, not a theoretical one.
- A browser-supplied key is **refused unless the request came from localhost**,
  so deploying this to a public host cannot turn it into a key-harvesting proxy.
  `ALLOW_REMOTE_KEYS=true` overrides it deliberately.
- Changing where the key is kept **clears the old location**, so switching from
  "on this browser" to "don't keep it" doesn't leave a copy behind.

### What it does not do — read this

A saved key sits in your browser **in plain text**. Any script running on the
page can read it. That is inherent to the approach, not a gap in this
implementation.

**This is the right pattern for a local tool where you bring your own key. It
is the wrong pattern for a deployed product** — there the key belongs on the
server and the browser should never see one. The demo does it this way so you
can try Gemini or Claude without editing a shell profile, and the UI says so
plainly rather than pretending otherwise.

Use a key with a **spending limit**, scoped to this experiment, and revoke it
when you're done.

### Or use environment variables instead

If you'd rather never put a key in a browser, the old path still works and
takes over automatically:

```bash
GEMINI_API_KEY=... node ai-demo/server.js
ANTHROPIC_API_KEY=... node ai-demo/server.js
```

A key pasted in Settings takes precedence over the environment, so one running
server can serve several people using their own keys.

**A mode that needs a key but has none degrades to rules and says so** in the
badge, rather than failing at the first prompt.

## Things to try

Manually: add a material, edit a rate, trash a row and restore it from **Trash**,
change a parameter — watch the life-cycle result move each time.

Then the prompt box (chips fill it in for you):

| Prompt | What it exercises |
| --- | --- |
| `Increase all foundation rates by 8%` | Bulk update scoped to one section |
| `Set the discount rate to 8` | Parameter change → re-discounting |
| `Add 240 m³ of RCC M40 pier shaft to substructure at 9500` | Create |
| `Change the MS railing quantity to 520` | Update by fuzzy name match |
| `Delete the drainage spout` | Soft delete |
| `Which section is the biggest cost driver?` | Read-only, changes nothing |
| `Increase all superstructure rates by 5% and set the analysis period to 75` | **Two tool calls from one sentence** |

And the guardrails — these are the interesting ones:

| Prompt | Expected |
| --- | --- |
| `Set the discount rate to 400` | **Rejected** — out of range, nothing changes |
| `Delete the reinforcement steel` | **Rejected** — ambiguous, it exists in two sections |
| `Delete the reinforcement steel and set the discount rate to 8` | Delete rejected, parameter change still applied |

And to see the fallback chain, in **Rules → model fallback** mode ask something
conversational the rules were never taught:

> `Could you please reconsider the procurement approach for the girders?`

The route shows `rules: no match → gemini`. Without a working key it shows
`rules: no match → gemini: failed` and falls back to the rules' own "I don't
understand" — hover the red pill for the (redacted) provider error.

## Layout

```
ai-demo/
├── server.js            zero-dep HTTP server: static files + REST + AI endpoint
├── test.js              28 end-to-end tests over the API
├── lib/
│   ├── seed.js          the data subset, with a seeded PRNG so resets reproduce
│   ├── store.js         in-memory project + THE CRUD PRIMITIVES + audit + undo
│   ├── lcca.js          simplified NPV / 3-pillar calculation
│   └── ai/
│       ├── tools.js     tool schema shared by all providers + the executor
│       ├── index.js     mode router + the prompt→ops→recompute pipeline
│       ├── mock.js      offline deterministic rule engine
│       ├── gemini.js    Gemini functionDeclarations
│       ├── claude.js    Anthropic tool use
│       └── redact.js    key redaction for logs, errors, and responses
└── public/
    ├── app.js           UI: render, CRUD wiring, prompt box
    ├── settings.js      ALL key handling lives here — one file to audit
    ├── index.html
    └── styles.css
```

**Read `lib/store.js` and `lib/ai/tools.js` first.** They contain the actual
idea; everything else is scaffolding.

The design point: the AI layer has **no privileged access**. It emits
operations, which are validated and then executed through the *same* functions
the REST handlers call for a mouse click — only `actor` differs. So an AI edit
gets the same validation, the same audit entry, and the same undo as a manual
one, and a hallucinated field fails at the same gate a malformed HTTP request
would.

## The data subset

A ~240 m, 6-span, 4-lane PSC I-girder bridge with **20 material line items**
across the four construction sections, plus 8 analysis parameters.

Row shape mirrors the real app
([`MaterialAddModal.jsx`](../src/gui/components/constructionworkdata/MaterialAddModal.jsx)):

```js
{ id, workName, qty, unit, rate, source,
  carbonEmission: { factor, perUnit, source },
  state: { in_trash } }
```

Two honest caveats about the numbers:

- **Totals read low.** 20 line items is a fraction of what a real project
  carries (no formwork, staging, launching, utilities, protection works), so
  the ~₹9 Cr construction cost is well under a real bridge of this size. The
  *mechanism* is what the demo is showing, not the estimate.
- **`lcca.js` is not the real engine.** It is a ~70-line stand-in with the same
  *shape* as `three_ps_lcca_core`: quantities → stage costs → discounting →
  three sustainability pillars. Pointing it at the real
  `POST /api/lcca/calculate` instead is a one-function change.

Carbon factors are **tCO₂e per unit of each row's own unit** — so kg-measured
rows carry per-kg figures (steel ≈ 0.00199, not 1.99). Getting that conversion
wrong inflates embodied carbon 1000× and swamps every other pillar; the first
draft of this seed data had exactly that bug, which is why the test suite now
range-checks it.

## State

Everything is **in memory**. Restarting the server resets it, and so does the
**Reset data** button — reproducibly, to byte-identical seed values.
