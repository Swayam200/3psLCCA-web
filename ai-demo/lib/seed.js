/**
 * Seed data for the AI demo.
 *
 * This is a deliberately small subset of the real 3psLCCA project schema:
 * only the four construction-work sections (foundation / substructure /
 * superstructure / miscellaneous) plus the handful of financial parameters
 * that drive the life-cycle cost roll-up.
 *
 * Row shape mirrors the real app (see
 * src/gui/components/constructionworkdata/MaterialAddModal.jsx):
 *   { id, workName, qty, unit, rate, source, carbonEmission, state }
 */

// Deterministic PRNG so every demo run produces the same "random" numbers.
// (A demo that changes under you is a demo you cannot narrate.)
const makeRng = (seed) => {
    let s = seed >>> 0;
    return () => {
        s = (s * 1664525 + 1013904223) >>> 0;
        return s / 0x100000000;
    };
};

const SEED = 20260730;

// Quantities describe a 240 m, 6-span, 4-lane PSC I-girder bridge.
// Carbon factors are tCO2e PER UNIT OF THE ROW'S OWN UNIT — so a kg-measured
// row carries a per-kg figure (steel ≈ 1.99 kgCO2e/kg = 0.00199 tCO2e/kg).
// Getting that conversion wrong is the classic LCCA data-entry bug: it inflates
// embodied carbon by 1000× and swamps every other pillar.
const CATALOG = {
    foundation_data: {
        name: 'Foundation',
        items: [
            ['Excavation in ordinary soil (up to 3 m depth)', 2400, 'm³', 310, 0.0042, 'Bihar SoR 2025'],
            ['PCC M15 levelling course', 180, 'm³', 6250, 0.221, 'Bihar SoR 2025'],
            ['Bored cast-in-situ pile, 1200 mm dia', 1480, 'm', 9850, 0.318, 'Bihar SoR 2025'],
            ['Pile cap, RCC M35', 620, 'm³', 8400, 0.342, 'Bihar SoR 2025'],
            ['Reinforcement steel Fe500D', 96000, 'kg', 78, 0.00199, 'Market rate 2025-Q2'],
        ],
    },
    substructure_data: {
        name: 'Sub Structure',
        items: [
            ['Pier shaft, RCC M40', 540, 'm³', 9100, 0.371, 'Bihar SoR 2025'],
            ['Pier cap, RCC M40', 210, 'm³', 9650, 0.371, 'Bihar SoR 2025'],
            ['Pedestal, RCC M40', 34, 'm³', 10200, 0.371, 'Bihar SoR 2025'],
            ['Elastomeric bearing, 400x500 mm', 48, 'nos', 41500, 0.18, 'Vendor quote 2025'],
            ['Reinforcement steel Fe500D', 74500, 'kg', 78, 0.00199, 'Market rate 2025-Q2'],
        ],
    },
    superstructure_data: {
        name: 'Super Structure',
        items: [
            ['PSC I-girder, M45', 1260, 'm³', 13400, 0.409, 'Bihar SoR 2025'],
            ['Deck slab, RCC M40', 880, 'm³', 9450, 0.371, 'Bihar SoR 2025'],
            ['Diaphragm, RCC M40', 96, 'm³', 9950, 0.371, 'Bihar SoR 2025'],
            ['Prestressing strand, 15.2 mm low-relaxation', 138000, 'kg', 96, 0.00231, 'Market rate 2025-Q2'],
            ['Bituminous concrete wearing coat, 65 mm', 3150, 'm²', 720, 0.012, 'Bihar SoR 2025'],
        ],
    },
    miscellaneous_data: {
        name: 'Miscellaneous',
        items: [
            ['RCC crash barrier, F-shape', 480, 'm', 3850, 0.098, 'Bihar SoR 2025'],
            ['MS railing, galvanised', 480, 'm', 2100, 0.058, 'Vendor quote 2025'],
            ['Strip-seal expansion joint, 70 mm', 30, 'm', 18600, 0.12, 'Vendor quote 2025'],
            ['Drainage spout with down-take pipe', 24, 'nos', 5400, 0.04, 'Bihar SoR 2025'],
            ['Approach slab, RCC M30', 168, 'm³', 8150, 0.318, 'Bihar SoR 2025'],
        ],
    },
};

export const SECTION_KEYS = Object.keys(CATALOG);

export const SECTION_LABELS = Object.fromEntries(
    SECTION_KEYS.map((key) => [key, CATALOG[key].name]),
);

export function createSeedProject() {
    // Both the id counter and the PRNG are re-created per call, so "Reset data"
    // returns byte-identical seed data every time — a demo you can re-run mid
    // presentation and get the same numbers back.
    let idCounter = 0;
    const nextId = (sectionKey) => `${sectionKey.replace('_data', '')}-row-${++idCounter}`;

    const rng = makeRng(SEED);
    const jitter = (base, spreadPct) => {
        const spread = base * (spreadPct / 100);
        return Number((base - spread + rng() * spread * 2).toFixed(2));
    };

    const sections = {};
    for (const key of SECTION_KEYS) {
        sections[key] = CATALOG[key].items.map(([workName, qty, unit, rate, factor, source]) => ({
            id: nextId(key),
            workName,
            // Jitter quantities and rates so the demo data reads as "a real
            // project someone typed in", not a rounded textbook example.
            qty: jitter(qty, 6),
            unit,
            rate: jitter(rate, 4),
            source,
            carbonEmission: { factor, perUnit: unit, source: 'ICE v3.0 / CPWD' },
            state: { in_trash: false },
        }));
    }

    return {
        schema_version: 1,
        name: 'Kosi Bridge — Demo',
        country: 'INDIA',
        currency: 'INR',
        unitSystem: 'Metric (SI)',

        general_info: {
            project_name: 'Kosi Bridge — Demo',
            project_country: 'INDIA',
            project_currency: 'INR',
            unit_system: 'Metric (SI)',
        },

        bridge_data: {
            bridge_name: 'Kosi River Crossing (demo)',
            bridge_type: 'PSC I-girder, 6 × 40 m',
            span: 240,
            num_lanes: 4,
            carriageway_width: 14.5,
            design_life: 100,
        },

        // The parameter block the AI is allowed to tune.
        financial_data: {
            analysis_period: 50,
            discount_rate: 6.5,          // %
            inflation_rate: 4.2,         // %
            maintenance_interval: 8,     // years
            maintenance_pct: 3.5,        // % of construction cost per event
            demolition_pct: 6.0,         // % of construction cost at EOL
            social_cost_of_carbon: 4500, // INR per tCO2e
            annual_road_user_cost: 4200000, // INR / year
        },

        ...sections,
    };
}
