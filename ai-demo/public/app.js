/**
 * Demo UI.
 *
 * One state object, one render(). Both the manual CRUD controls and the AI
 * prompt box hit the same REST API and then re-render from the same server
 * response — which is exactly why an AI edit looks "real-time": there is no
 * separate AI code path in the view layer at all.
 */

import {
    loadPrefs, savePrefs, loadKey, saveKey, clearKey,
    authHeaders, settingsPayload, maskKey,
} from './settings.js';

const $ = (sel) => document.querySelector(sel);

let state = null;
let activeSection = 'foundation_data';
let editingId = null;
let flashIds = new Set();
let prefs = loadPrefs();

// --------------------------------------------------------------- helpers --
const inr = (v) => '₹' + Math.round(v).toLocaleString('en-IN');
const compact = (v) => {
    const abs = Math.abs(v);
    if (abs >= 1e7) return `₹${(v / 1e7).toFixed(2)} Cr`;
    if (abs >= 1e5) return `₹${(v / 1e5).toFixed(2)} L`;
    return inr(v);
};
const num = (v) => Number(v).toLocaleString('en-IN', { maximumFractionDigits: 2 });
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const ago = (iso) => {
    const s = Math.round((Date.now() - new Date(iso)) / 1000);
    if (s < 60) return `${s}s ago`;
    if (s < 3600) return `${Math.round(s / 60)}m ago`;
    return `${Math.round(s / 3600)}h ago`;
};

async function api(path, options = {}) {
    const res = await fetch(path, {
        ...options,
        headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
}

/** A request that carries the key header + the non-secret settings. */
const aiApi = (path, body = {}) => api(path, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ ...body, settings: settingsPayload(prefs) }),
});

/** Every mutating response carries the whole view — adopt it and repaint. */
function adopt(payload) {
    if (payload.project) state = payload;
    render();
}

// ---------------------------------------------------------------- render --
function render() {
    if (!state) return;
    const { project, sections, results, ai } = state;

    $('#projectMeta').textContent =
        `${project.bridge_data.bridge_name} · ${project.bridge_data.span} m · `
        + `${project.bridge_data.num_lanes} lanes · ${project.currency}`;

    const badge = $('#providerBadge');
    const usesModel = ai.effectiveMode !== 'rules';
    badge.textContent = ai.degraded ? 'rules (no key)' : ai.modeLabel.toLowerCase();
    $('#settingsBtn').classList.toggle('live', usesModel);
    $('#settingsBtn').title = ai.degradedReason || `${ai.modeLabel} · ${usesModel ? ai.model : 'offline'}`;
    $('#aiModel').textContent = usesModel
        ? `${ai.providerLabel} · ${ai.model}`
        : 'rule engine (offline)';

    renderTabs(sections);
    renderTable(sections.find((s) => s.key === activeSection));
    renderParams();
    renderResults(results);
    renderAudit();

    const trashed = sections.reduce((n, s) => n + s.rows.filter((r) => r.state.in_trash).length, 0);
    $('#trashCount').textContent = trashed;
}

function renderTabs(sections) {
    $('#sectionTabs').innerHTML = sections.map((s) => {
        const active = s.rows.filter((r) => !r.state.in_trash).length;
        return `<button class="tab ${s.key === activeSection ? 'active' : ''}" data-section="${s.key}">
            ${esc(s.label)} <span class="pill">${active}</span></button>`;
    }).join('');
}

function renderTable(section) {
    if (!section) return;
    const rows = section.rows.filter((r) => !r.state.in_trash);

    if (!rows.length) {
        $('#tableWrap').innerHTML = '<p class="empty">No materials in this section yet.</p>';
        return;
    }

    const total = rows.reduce((s, r) => s + r.qty * r.rate, 0);
    const carbon = rows.reduce((s, r) => s + r.qty * (r.carbonEmission?.factor || 0), 0);

    $('#tableWrap').innerHTML = `
    <table>
      <thead><tr>
        <th>Work name</th><th>Quantity</th><th>Unit</th><th>Rate</th>
        <th>tCO₂e</th><th>Amount</th><th></th>
      </tr></thead>
      <tbody>
        ${rows.map((r) => `
          <tr class="${flashIds.has(r.id) ? 'flash' : ''}">
            <td>${esc(r.workName)}<div class="src">${esc(r.source || '—')}</div></td>
            <td>${num(r.qty)}</td>
            <td>${esc(r.unit)}</td>
            <td>${num(r.rate)}</td>
            <td>${num(r.qty * (r.carbonEmission?.factor || 0))}</td>
            <td class="total">${inr(r.qty * r.rate)}</td>
            <td>
              <button class="icon-btn" data-edit="${r.id}" title="Edit">✎</button>
              <button class="icon-btn danger" data-del="${r.id}" title="Move to trash">✕</button>
            </td>
          </tr>`).join('')}
      </tbody>
      <tfoot><tr>
        <td>${rows.length} items</td><td></td><td></td><td></td>
        <td>${num(carbon)}</td><td class="total">${inr(total)}</td><td></td>
      </tr></tfoot>
    </table>`;
    flashIds = new Set();
}

function renderParams() {
    $('#paramGrid').innerHTML = state.parameters.map((p) => `
      <div class="param" data-param="${p.name}">
        <label for="p-${p.name}">${esc(p.label)}</label>
        <input id="p-${p.name}" type="number" step="any" min="${p.min}" max="${p.max}"
               value="${p.value}" data-param-input="${p.name}" />
      </div>`).join('');
}

function renderResults(r) {
    const t = r.totals;
    $('#calcNote').textContent =
        `${r.assumptions.analysis_period} yr · ${r.assumptions.discount_rate}% nominal · ${r.assumptions.real_discount_rate}% real`;

    const pillars = [
        ['Profit — capital + O&M', r.pillars.profit, 'var(--accent)'],
        ['Planet — embodied carbon', r.pillars.planet, 'var(--good)'],
        ['People — road user cost', r.pillars.people, 'var(--ai)'],
    ];
    const max = Math.max(...r.stages.map((s) => s.cost), 1);

    $('#results').innerHTML = `
      <div class="kpis">
        <div class="kpi"><span>Total life-cycle NPV</span><strong>${compact(t.total_npv)}</strong></div>
        <div class="kpi"><span>Initial construction</span><strong>${compact(t.construction_cost)}</strong></div>
        <div class="kpi"><span>Embodied carbon</span><strong>${num(Math.round(t.embodied_carbon_t))} t</strong></div>
        <div class="kpi"><span>NPV per metre</span><strong>${t.npv_per_m ? compact(t.npv_per_m) : '—'}</strong></div>
      </div>
      <div class="bars">
        ${pillars.map(([label, value, color]) => `
          <div class="bar-row">
            <div class="lbl"><span>${label}</span><span>${compact(value)} · ${((value / t.total_npv) * 100).toFixed(1)}%</span></div>
            <div class="track"><div class="fill" style="width:${(value / t.total_npv) * 100}%;background:${color}"></div></div>
          </div>`).join('')}
        <div class="lbl" style="margin:14px 0 6px"><span class="muted-sm">BY LIFE-CYCLE STAGE</span></div>
        ${r.stages.map((s) => `
          <div class="bar-row">
            <div class="lbl"><span>${esc(s.label)}</span><span>${compact(s.cost)}</span></div>
            <div class="track"><div class="fill" style="width:${(s.cost / max) * 100}%;background:var(--text-2)"></div></div>
          </div>`).join('')}
      </div>`;
}

function renderAudit() {
    const items = state.audit;
    $('#auditList').innerHTML = items.length
        ? items.map((e) => `
            <li>
              <span class="who ${e.actor}">${e.actor}</span>
              <span>${esc(e.detail)}</span>
              <span class="when">${ago(e.at)}</span>
            </li>`).join('')
        : '<li class="empty" style="border:none">No changes yet.</li>';
}

// ------------------------------------------------------------- AI output --
function renderAiOutcome(res) {
    const out = $('#aiOut');
    out.classList.add('show');

    if (res.status === 'error') {
        out.innerHTML = `<p class="err">Provider error: ${esc(res.error)}</p>`;
        return;
    }

    // Make the route explicit. A silent fallback is worse than no fallback:
    // the user needs to know whether a model or a regex answered them.
    const routeHtml = (res.route || []).map((step) => {
        const cls = step.outcome === 'ok' ? 'ok' : step.outcome === 'unparsed' ? 'skip' : 'bad';
        const label = step.outcome === 'ok' ? step.step
            : step.outcome === 'unparsed' ? `${step.step}: no match`
                : `${step.step}: failed`;
        return `<span class="hop ${cls}" ${step.error ? `title="${esc(step.error)}"` : ''}>${esc(label)}</span>`;
    }).join('<span class="arrow">→</span>');

    const d = res.delta;
    const arrow = (v) => (v > 0 ? `<span class="up">▲ ${compact(v)}</span>`
        : v < 0 ? `<span class="down">▼ ${compact(Math.abs(v))}</span>` : '<span>no change</span>');

    const cards = [
        ...res.applied.map((a) => `
          <div class="callcard">
            <div class="tool">${esc(a.name)}${a.readOnly ? ' · read-only' : ''}</div>
            <div class="txt">${esc(a.summary)}</div>
            ${a.readOnly ? '' : `<pre>${esc(JSON.stringify(a.args))}</pre>`}
          </div>`),
        ...res.rejected.map((r) => `
          <div class="callcard rejected">
            <div class="tool">${esc(r.name)} · rejected</div>
            <div class="txt">${esc(r.error)}</div>
            <pre>${esc(JSON.stringify(r.args))}</pre>
          </div>`),
    ].join('');

    out.innerHTML = `
      <div class="delta">
        <span><b>NPV</b> ${arrow(d.total_npv)}</span>
        <span><b>Capital</b> ${arrow(d.construction_cost)}</span>
        <span><b>Carbon</b> ${d.embodied_carbon_t.toFixed(1)} t</span>
      </div>
      <div class="route">${routeHtml}</div>
      <p class="muted-sm" style="margin:2px 0 10px">
        ${esc(res.model)} · ${res.latencyMs} ms · ${res.applied.length} applied, ${res.rejected.length} rejected
      </p>
      ${cards}`;

    // Highlight rows the model touched.
    flashIds = new Set(res.applied.map((a) => a.row?.id).filter(Boolean));
    const touched = res.applied.find((a) => a.row);
    if (touched) {
        const sec = state.sections.find((s) => s.rows.some((r) => r.id === touched.row.id));
        if (sec) activeSection = sec.key;
    }
    render();
}

// ------------------------------------------------------------- listeners --
$('#sectionTabs').addEventListener('click', (e) => {
    const tab = e.target.closest('[data-section]');
    if (!tab) return;
    activeSection = tab.dataset.section;
    render();
});

$('#tableWrap').addEventListener('click', async (e) => {
    const del = e.target.closest('[data-del]');
    const edit = e.target.closest('[data-edit]');
    try {
        if (del) adopt(await api(`/api/materials/${del.dataset.del}`, { method: 'DELETE' }));
        if (edit) openRowDialog(edit.dataset.edit);
    } catch (err) { alert(err.message); }
});

// Parameter inputs commit on change (not on every keystroke).
$('#paramGrid').addEventListener('change', async (e) => {
    const input = e.target.closest('[data-param-input]');
    if (!input) return;
    try {
        adopt(await api('/api/parameters', {
            method: 'PATCH',
            body: JSON.stringify({ name: input.dataset.paramInput, value: Number(input.value) }),
        }));
    } catch (err) { alert(err.message); render(); }
});

$('#addBtn').addEventListener('click', () => openRowDialog(null));
$('#undoBtn').addEventListener('click', async () => {
    try { adopt(await api('/api/undo', { method: 'POST' })); }
    catch (err) { alert(err.message); }
});
$('#resetBtn').addEventListener('click', async () => {
    adopt(await api('/api/reset', { method: 'POST' }));
    $('#aiOut').classList.remove('show');
});

function openRowDialog(id) {
    editingId = id;
    const form = $('#rowForm');
    form.reset();
    if (id) {
        const row = state.sections.flatMap((s) => s.rows).find((r) => r.id === id);
        $('#rowDialogTitle').textContent = 'Edit material';
        form.workName.value = row.workName;
        form.qty.value = row.qty;
        form.unit.value = row.unit;
        form.rate.value = row.rate;
        form.carbonFactor.value = row.carbonEmission?.factor ?? 0;
        form.source.value = row.source || '';
    } else {
        $('#rowDialogTitle').textContent =
            `Add material — ${state.sections.find((s) => s.key === activeSection).label}`;
    }
    $('#rowDialog').showModal();
}

$('#rowForm').addEventListener('submit', async (e) => {
    if (e.submitter?.value !== 'save') return;
    e.preventDefault();
    const f = e.target;
    const payload = {
        workName: f.workName.value,
        qty: Number(f.qty.value),
        unit: f.unit.value,
        rate: Number(f.rate.value),
        carbonFactor: Number(f.carbonFactor.value || 0),
        source: f.source.value,
    };
    try {
        const res = editingId
            ? await api(`/api/materials/${editingId}`, { method: 'PATCH', body: JSON.stringify(payload) })
            : await api(`/api/sections/${activeSection}/materials`, { method: 'POST', body: JSON.stringify(payload) });
        flashIds = new Set([res.row.id]);
        $('#rowDialog').close();
        adopt(res);
    } catch (err) { alert(err.message); }
});

// ----------------------------------------------------------------- trash --
$('#trashBtn').addEventListener('click', () => {
    const trashed = state.sections.flatMap((s) => s.rows.filter((r) => r.state.in_trash).map((r) => ({ ...r, sec: s.label })));
    $('#trashList').innerHTML = trashed.length
        ? `<table><tbody>${trashed.map((r) => `
            <tr><td>${esc(r.workName)}<div class="src">${esc(r.sec)}</div></td>
                <td class="total">${inr(r.qty * r.rate)}</td>
                <td><button class="icon-btn" data-restore="${r.id}">Restore</button></td></tr>`).join('')}
          </tbody></table>`
        : '<p class="empty">Trash is empty.</p>';
    $('#trashDialog').showModal();
});
$('#trashDialog').addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-restore]');
    if (!btn) return;
    adopt(await api(`/api/materials/${btn.dataset.restore}/restore`, { method: 'POST' }));
    $('#trashDialog').close();
});
$('#trashClose').addEventListener('click', () => $('#trashDialog').close());

// ------------------------------------------------------------- settings --
function renderSettings() {
    const { ai } = state;

    $('#modeSelect').innerHTML = ai.modes
        .map((m) => `<option value="${m.id}" ${m.id === prefs.mode ? 'selected' : ''}>${esc(m.label)}</option>`)
        .join('');
    $('#providerSelect').innerHTML = ai.providers
        .map((p) => `<option value="${p.id}" ${p.id === prefs.provider ? 'selected' : ''}>${esc(p.label)}</option>`)
        .join('');

    const mode = ai.modes.find((m) => m.id === prefs.mode);
    $('#modeBlurb').textContent = mode?.blurb || '';
    // Rules-only needs no key, so hide the whole block rather than showing
    // fields that do nothing.
    $('#keyBlock').style.display = mode?.needsKey ? '' : 'none';

    const provider = ai.providers.find((p) => p.id === prefs.provider);
    $('#modelInput').placeholder = provider?.defaultModel || '';
    $('#modelInput').value = prefs.model || '';

    for (const radio of document.querySelectorAll('input[name="storage"]')) {
        radio.checked = radio.value === prefs.storage;
    }

    const key = loadKey();
    const input = $('#apiKeyInput');
    if (document.activeElement !== input) {
        input.value = key;
        input.placeholder = ai.keySource === 'environment'
            ? `using ${provider?.envVar} from the server environment`
            : 'paste your own key';
    }
    $('#testResult').textContent = key
        ? `Key loaded (${maskKey(key)}), kept: ${prefs.storage}.`
        : '';
}

const applyPrefs = async (patch) => {
    prefs = { ...prefs, ...patch };
    savePrefs(prefs);
    // Re-ask the server so the badge reflects what will actually happen —
    // including whether the chosen mode has degraded for want of a key.
    const status = await aiApi('/api/ai/status');
    state = { ...state, ai: status };
    render();
    renderSettings();
};

$('#settingsBtn').addEventListener('click', () => {
    renderSettings();
    $('#settingsDialog').showModal();
});
$('#settingsClose').addEventListener('click', () => $('#settingsDialog').close());

$('#modeSelect').addEventListener('change', (e) => applyPrefs({ mode: e.target.value }));
$('#providerSelect').addEventListener('change', (e) => applyPrefs({ provider: e.target.value, model: '' }));
$('#modelInput').addEventListener('change', (e) => applyPrefs({ model: e.target.value.trim() }));

$('#apiKeyInput').addEventListener('change', async (e) => {
    saveKey(e.target.value.trim(), prefs.storage);
    await applyPrefs({});
});

document.querySelectorAll('input[name="storage"]').forEach((radio) => {
    radio.addEventListener('change', async () => {
        // Re-save under the new choice, which also clears the old location.
        saveKey(loadKey(), radio.value);
        await applyPrefs({ storage: radio.value });
    });
});

$('#revealBtn').addEventListener('click', () => {
    const input = $('#apiKeyInput');
    input.type = input.type === 'password' ? 'text' : 'password';
});

$('#clearKeyBtn').addEventListener('click', async () => {
    clearKey();
    $('#apiKeyInput').value = '';
    $('#testResult').textContent = 'Key cleared from this browser.';
    await applyPrefs({});
});

$('#testKeyBtn').addEventListener('click', async () => {
    const el = $('#testResult');
    el.textContent = 'Testing…';
    el.className = 'hint';
    try {
        const res = await aiApi('/api/ai/test');
        el.textContent = res.ok
            ? `Works — ${res.provider} responded using ${res.model}.`
            : `Failed: ${res.error}`;
        el.className = res.ok ? 'hint ok' : 'hint bad';
    } catch (err) {
        el.textContent = `Failed: ${err.message}`;
        el.className = 'hint bad';
    }
});

// -------------------------------------------------------------- AI panel --
const EXAMPLES = [
    'Increase all foundation rates by 8%',
    'Set the discount rate to 8',
    'Change the analysis period to 75 years',
    'Add 240 m³ of RCC M40 pier shaft to substructure at 9500',
    'Change the MS railing quantity to 520',
    'Delete the drainage spout',
    'What is the total life-cycle NPV?',
    'Which section is the biggest cost driver?',
];

$('#chips').innerHTML = EXAMPLES.map((t) => `<button class="chip">${esc(t)}</button>`).join('');
$('#chips').addEventListener('click', (e) => {
    const chip = e.target.closest('.chip');
    if (!chip) return;
    $('#prompt').value = chip.textContent;
    $('#prompt').focus();
});

async function runPrompt() {
    const prompt = $('#prompt').value.trim();
    if (!prompt) return;
    const btn = $('#runBtn');
    btn.disabled = true;
    btn.textContent = 'Thinking…';
    try {
        const res = await aiApi('/api/ai/command', { prompt });
        state = res;
        renderAiOutcome(res);
    } catch (err) {
        $('#aiOut').classList.add('show');
        $('#aiOut').innerHTML = `<p class="err">${esc(err.message)}</p>`;
    } finally {
        btn.disabled = false;
        btn.textContent = 'Run';
    }
}

$('#runBtn').addEventListener('click', runPrompt);
$('#prompt').addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') runPrompt();
});

// ----------------------------------------------------------------- boot ---
adopt(await api('/api/state'));
// The boot state reports the server's env-only view; correct it to reflect the
// settings this browser has stored.
state = { ...state, ai: await aiApi('/api/ai/status') };
render();
