# AI Integration Plan for 3psLCCA-web

**Branch context:** builds on `feat/cdn-calc-engine` — the browser-first build
where the official `3psLCCA-core` engine runs in the browser (Pyodide, CDN
wheel, shared adapter) and the FastAPI backend is only a fallback. The deployed
artifact is a **static site (GitHub Pages) with no server of ours behind it**.

**Prototype reference:** `ai-demo/` (standalone, zero-dependency) proved the
core pattern end to end — tool-calling over a schema subset, four routing
modes, BYO API key with safety rails, 28 passing tests. This plan is about
moving that pattern into the real app properly, not copy-pasting the demo.

---

## 1. Design constraints (what "properly" means here)

These come from what the project *is* — open source, statically deployed,
schema-driven — and they decide most of the architecture up front.

**C1 — No server, no secrets of ours.**
The production deployment is static. There is no place to hide an API key we
own, and an open-source repo must never ship one. Therefore the default model
access is **bring-your-own-key** (the demo's settings pattern, hardened), with
an **optional proxy URL** setting so any organisation deploying 3psLCCA-web can
point the app at their own key-holding endpoint instead. Both paths use the
same provider interface; the proxy is just another base URL.

**C2 — The AI is a leaf, never a dependency.**
No existing module may import from the AI package. The AI package imports from
the app (schema, context, engine API) — one direction only. With the feature
flag off, the AI code must be tree-shaken out of the bundle entirely
(dynamic `import()` behind the flag). A contributor who ignores AI entirely
must never be affected by it.

**C3 — Every AI write goes through the existing funnel.**
All page components already mutate the project via
`updateProjectData(sectionKey, data)` in `ProjectDataContext`. The AI executor
uses exactly that — same normalization (`normalizeProjectSection`), same
persistence (`projectStorageService`), same autosave. No parallel write path,
ever. This is the demo's `actor: 'ai'` principle transplanted.

**C4 — The model never produces a number the user relies on.**
Results come from `calculateLcca()` — the same engine call the Results page
makes. The model only emits operations; the engine recomputes. (See
`docs/ai-in-web-applications.md` Part 3 for the full argument.)

**C5 — Configurable at three levels.**
1. *Build time:* `VITE_AI_ENABLED` (default **off**) — deployments that don't
   want the feature never ship it.
2. *Runtime, per user:* provider, model, routing mode, key, key-storage
   policy — in the Settings modal, persisted like existing user settings.
3. *Code:* providers and tools are registries, not switch statements — adding
   a provider or a tool is a new file plus a registration line, which is the
   contribution surface for the open-source community.

---

## 2. Target architecture

```
src/lib/ai/                     ← the whole feature lives here (C2)
├── index.js                    public API: isAiEnabled(), loadAi() (dynamic import)
├── config.js                   build flag + runtime settings merge
├── settings.js                 key + prefs persistence (port of demo, hardened)
├── redact.js                   key redaction (port of demo)
├── router.js                   modes: rules | model | rules-first | model-first
├── providers/
│   ├── registry.js             { id, label, generate(prompt, opts) } registry
│   ├── rules.js                offline deterministic engine (port of demo mock)
│   ├── gemini.js               direct API, BYO key
│   ├── claude.js               direct API, BYO key
│   └── proxy.js                POSTs to a user-configured proxy URL (C1)
├── tools/
│   ├── registry.js             tool declarations + executor registry
│   ├── schema.js               JSON-Schema for each tool (single source, all providers)
│   ├── construction.js         create/update/delete/scale materials
│   ├── parameters.js           financial + bridge scalar edits
│   ├── query.js                read-only answers from computed results
│   └── executor.js             validate → execute via ProjectDataContext → diff
├── audit.js                    per-project change log entries (actor: user|ai)
└── __tests__/                  node --test, no model calls (deterministic parts)

src/gui/components/ai/
├── AiPanel.jsx                 prompt box + chips + route display + result cards
├── AiDiffModal.jsx             propose-and-confirm diff view (Phase 2)
├── AiSettingsTab.jsx           new tab in the existing SettingsModal
└── AiBadge.jsx                 mode/provider indicator (mirrors engine provenance UI)
```

Supporting decisions:

- **Tool schema is data, not code** (`tools/schema.js` exports plain objects) —
  the same declarations feed Gemini, Claude, the rules engine's documentation,
  and eventually the Python desktop app if it grows the same feature.
- **The rules provider ships always** and is the default. The app's AI box
  works offline, free, with zero configuration — models are an upgrade, not a
  requirement. This matters for an open-source tool used in low-connectivity
  settings.
- **`proxy.js`** speaks the same request/response contract as the demo server's
  `/api/ai/command`. Anyone can stand up a 50-line endpoint (serverless
  function, FastAPI route — we ship a reference implementation in Phase 4) and
  keep keys server-side. This resolves the C1 tension without us running
  anything.

---

## 3. The phases

Each phase is a separate PR train off `feat/cdn-calc-engine` (suggested
branches: `feat/ai-p1-assistant`, `feat/ai-p2-edits`, …), ends in a
manager-demoable state, and leaves the app releasable — the flag stays off by
default until Phase 2 is accepted.

---

### Phase 1 — Foundation + read-only assistant

**The pitch to the manager:** *"An assistant you can ask about the current
project — totals, drivers, assumptions — that cannot change anything, costs
nothing by default, and doesn't exist in the bundle unless we turn it on."*

Read-only first is deliberate (staged-trust argument from
`docs/ai-in-web-applications.md` §7): zero risk while we learn how users
phrase things, and phrasing data is exactly what Phase 2's write tools need.

**Scope:**

1. **The whole `src/lib/ai/` skeleton** — config, settings, redaction, router,
   provider registry with `rules`, `gemini`, `claude`, `proxy`. This is the
   bulk of the phase and everything later stands on it.
2. **Feature flag plumbing** (`VITE_AI_ENABLED`, dynamic import, bundle-size
   assertion in a test so the flag-off bundle provably excludes the AI code).
3. **Settings → AI tab**: enable toggle (runtime, on top of build flag),
   provider picker, mode picker, BYO key with storage-policy choice
   (localStorage / sessionStorage / memory), Test-key button, proxy URL field.
   Same safety rails as the demo: header transport, redaction, fingerprints,
   plain-language warning text.
4. **Read-only tools only**: `answer_question` grounded in the *computed*
   results (runs `calculateLcca` if results are stale), `summarize_project`,
   `explain_validation_errors` (feeds the validation messages users already
   see into a plain-language explanation).
5. **`AiPanel` on the Results page** (collapsible side panel, mirroring where
   engine provenance already shows), with example chips and the route display
   (`rules` / `rules: no match → gemini`).
6. **Docs:** `docs/ai-setup.md` (user-facing), `CONTRIBUTING` section for the
   provider interface.

**Explicitly out:** any write operation. The executor exists but registers
zero mutating tools.

**Acceptance / demo script:**
- Flag off → no AI anywhere, bundle unchanged (test-enforced).
- Flag on, no key → rules mode answers "what is the total NPV?", "which
  section drives cost?", offline, instantly.
- Paste a Gemini key in Settings → same questions plus free-form phrasings;
  route display shows which engine answered.
- Test suite: settings persistence, redaction, router fallback logic, tool
  registry — all deterministic, no live API calls in CI.

---

### Phase 2 — Write operations with propose-and-confirm

**The pitch:** *"Now it can make the edit for you — but it shows you a diff
first, nothing changes without your click, every change is logged and
undoable."*

**Scope:**

1. **Mutating tools over the Phase-1 subset that demoed well:**
   - `construction.js`: add / update / soft-delete (trash) / restore material
     rows, `scale_rates` for bulk percentage changes — matching the existing
     trash workflow in `ConstructionTrash.jsx`.
   - `parameters.js`: financial data scalars (discount rate, analysis period,
     inflation…) and bridge data scalars, each with a validation spec
     (min/max/enum) mirrored from what the page components accept.
2. **The executor** (`tools/executor.js`): resolves fuzzy row references
   (ambiguity = refusal, the demo rule), validates every argument, computes a
   **structured diff** against current `projectData`, and — only after
   confirmation — applies via `updateProjectData` per section (C3).
3. **`AiDiffModal`**: field-level before→after, per-operation accept/reject
   (a 3-operation prompt can apply 2), projected result delta (runs the engine
   on a *copy* for preview — cheap, since the browser engine is already
   loaded).
4. **Audit + undo**: `audit.js` writes entries (actor, op, before-state) into
   `outputs_data`-adjacent project metadata; single-step undo surfaced in the
   panel. Integrates with the existing version-history concept
   (`VersionHistoryModal.jsx`) rather than competing with it.
5. **Direct-apply setting** (off by default): power users can skip the modal
   for single-parameter edits only; bulk/destructive always confirm.
6. **Golden-prompt eval script** (`npm run ai:eval`, local, key required, not
   CI): ~30 canonical prompts with expected operation shapes, so provider or
   model changes are measurable from here on.

**Acceptance / demo script:**
- "Increase all foundation rates by 8% and set the discount rate to 8" →
  diff modal shows both operations with before→after and projected NPV change →
  Apply → tables update, engine recomputes, audit shows two `ai` entries →
  Undo reverts.
- "Delete the reinforcement steel" with two matches → refusal listing both.
- Out-of-range value → rejected with the same message manual entry produces.

---

### Phase 3 — Full-schema coverage, scenarios, and the report

**The pitch:** *"It covers every data page now, can compare what-if scenarios
side by side, and writes the report's narrative — from numbers the engine
computed, never numbers it made up."*

**Scope:**

1. **Tool coverage for the remaining sections**: traffic (vehicle table +
   growth), maintenance & repair schedule, carbon emission inputs, recycling,
   demolition, transport. Each follows the Phase-2 pattern (schema + validator
   + executor entry); this is where the registry design pays off — it's
   repetitive, parallelizable work, and good first-issue territory for
   contributors.
2. **Scenario comparison**: `run_scenario` tool forks the project in memory,
   applies proposed operations to the fork, runs the engine on both, renders a
   side-by-side delta view. Nothing touches the saved project unless the user
   promotes the scenario. (The engine being a pure function makes this nearly
   free — the argument from `docs/ai-in-web-applications.md` §7 Tier 1.)
3. **Report narration**: an "Executive summary" section option in the existing
   report flow (`reportSections.js` / jsPDF pipeline) — computed results in,
   paragraph out, clearly labelled as AI-drafted and editable before inclusion.
   Zero hallucination risk on figures because the model only describes values
   it was handed (C4).
4. **Prompt-context management**: with the full schema in scope, stop sending
   whole projects — a selector maps the prompt to the relevant section slices
   (cost control; also improves accuracy).
5. **Multi-turn context**: the panel keeps conversation state so "now do the
   same for the substructure" resolves against the previous turn.

**Acceptance / demo script:**
- Edit prompts against every data page succeed end to end.
- "Show me this bridge at 4% discount over 100 years" → side-by-side
  comparison without modifying the project; "keep it" promotes the scenario.
- Generate a PDF containing the AI-drafted summary; hand-edit it first;
  numbers in the text match the tables exactly.

---

### Phase 4 — Deployment story, hardening, ecosystem

**The pitch:** *"Any organisation can deploy this with their own keys held
server-side; imports are safe against hostile files; the provider interface is
documented for the community."*

**Scope:**

1. **Reference proxy implementations** (in-repo, `deploy/ai-proxy/`): the
   FastAPI route (drops into the existing `backend/`) and a single-file
   serverless variant (Cloudflare Worker / Vercel function) speaking the
   `proxy.js` contract — auth pass-through, rate limiting, logging hooks.
   This closes C1 completely for institutional deployments.
2. **Import-mapping tool with prompt-injection defenses**: AI-assisted column
   mapping for the Excel construction import (`constructionExcel.js`) —
   imported cell content is data-only (never concatenated into instructions),
   mapping is propose-and-confirm, and destructive ops are never derivable
   from file content. This is the feature where injection is a *real* threat,
   so it lands only after the confirm infrastructure is mature.
3. **Rules-engine expansion** from Phase 1–3 telemetry-free logs (the local
   rejection log): promote the most common model-handled phrasings into the
   free offline rules layer — the cost-reduction flywheel.
4. **Provider ecosystem**: documented provider contract + an
   OpenAI-compatible generic provider (covers Ollama/local models — full
   offline model support, which is a genuinely good fit for this project's
   audience), provider conformance test kit.
5. **Hardening pass**: rate limiting in the panel, request cancellation,
   stale-context detection (project changed while the model was thinking →
   re-validate the diff before apply), accessibility audit of the panel and
   modal, i18n-readiness of AI-facing strings.

**Acceptance:**
- A fresh clone can deploy the proxy in under 30 minutes from docs alone.
- A malicious workbook with instruction-bearing cells cannot cause any
  operation beyond the mapping it proposed visibly.
- Ollama running locally works as a provider with zero external network.

---

## 3.5 UI workstream — the floating assistant (parallel to Phase 2)

> **Status: shipped** (branch `feat/ai-floating-fab`). Delivered as specced —
> vector logo FAB (`AiLogoMark.jsx`) with breathe/hover/orbit/pulse states,
> corner sheet, `useAiAssistant()` hook shared with the Results-page cue,
> ProjectLayout mount inside the flag gate, page-aware chips
> (`pageChips.js`), modal hiding via a `body.modal-open` observer. Deferred:
> draggable/remembered FAB position (fixed bottom-right for now).

Phase 1 embedded the assistant as a panel inside the Results page — right for
proving the pipeline, wrong as a home: it is invisible from every other page,
and Phase 2's whole point is editing data on *any* page.

**Target: a floating assistant anchored bottom-right, built as a play on the
3psLCCA logo** (three overlapping circles — orange, green, purple — the three
pillars).

1. **The launcher (FAB).** Recreate the logo's three circles as real vector
   shapes (the shipped logo is a raster; a ~20-line SVG reproduces it) so
   they can animate:
   - *Idle:* the three circles sit in the logo arrangement, gently breathing
     (slow scale pulse, `prefers-reduced-motion` respected).
   - *Hover:* circles separate slightly and re-overlap — the logo "opens".
   - *Thinking:* the circles orbit a common centre — the natural spinner,
     and it IS the brand mark.
   - *Answer ready (panel closed):* one soft pulse + a badge dot.
   - *Per-tier tint (optional, subtle):* rules answered → green emphasis,
     encoder → purple, cloud → orange; the route pills stay authoritative.
2. **The sheet.** Clicking the FAB opens a card (spring scale+fade from the
   FAB corner, ~200 ms) with exactly today's panel content: chips, prompt
   box, route pills with confidence, answers. Esc / outside-click closes.
   On narrow screens it becomes a bottom sheet.
3. **App-wide mount.** The FAB moves out of Outputs.jsx into ProjectLayout,
   inside the same `VITE_AI_ENABLED` lazy gate, so it floats over every data
   page — the prerequisite for Phase 2's "edit from anywhere". Page-aware
   chips (Foundation page → material questions) come free from the existing
   intent catalogue.
4. **Placement rules.** Bottom-right, above the page scroll, never overlapping
   modals (hidden while any modal is open); z-index below toasts; position
   remembered per browser.

Implementation notes: pure CSS/SVG animation (no animation library — the
bundle discipline stays), one new `AiFab.jsx` + a `useAiAssistant()` hook
extracted from today's panel so panel and sheet share all logic. The Results
page keeps a slim "Ask about these results" affordance that opens the same
sheet. Estimated as one focused PR, independent of (and mergeable before)
Phase 2's write tools.

## 4. Cross-cutting rules (all phases)

- **Testing:** deterministic parts (router, validators, executor, diff,
  settings, redaction) get exhaustive `node --test` coverage in CI with zero
  model calls; model integration is covered by the local golden-prompt evals.
  This split is why the demo's suite is fast and never flaky — keep it.
- **Every PR keeps `main` shippable** with the flag off; the flag flips on
  per-deployment, not in the repo default, until the team decides otherwise.
- **No telemetry, ever, by default.** Rejection/phrasing logs stay in the
  browser; surfacing them to the user (Phase 4) is how we learn, not phoning
  home. Non-negotiable for an open-source tool handling engineering data.
- **Docs move with code:** each phase updates `docs/ai-setup.md` and the
  contributor docs in the same PR.

## 5. Risks and their mitigations

| Risk | Mitigation |
| --- | --- |
| Manager/community wary of AI writes to engineering data | Phase order: read-only → confirm-gated → (opt-in) direct apply. Nothing writes without a click until trust is earned. |
| BYO key UX friction | Rules mode gives a working default with no key; Test-key button; proxy option for orgs. |
| Provider API churn | Thin providers (~50 lines each, no SDKs) behind one contract; conformance tests catch drift. |
| Schema drift between tools and pages | Validation specs live beside the tool schema and are unit-tested against `normalizeProjectSection` outputs. |
| Scope creep inside phases | Each phase's "explicitly out" list is part of the PR description; anything else is a new issue. |
