/**
 * Report figures — the desktop report's three result plots
 * (report/plot_exporter.py), drawn with the Results page's own chart
 * components so they match what the user already saw on screen.
 */
import { useRef } from 'react';
import { computeAllSummaries } from '../gui/components/outputs/lifecycleSummary.js';
import { COLORS as LC } from '../gui/components/outputs/lccColors.js';
import { SimpleDonut, SimpleBars, StackedBars } from '../gui/components/outputs/ResultsView.jsx';

const PILLARS = [['Economic', 'eco', LC.eco_color], ['Environmental', 'env', LC.env_color], ['Social', 'social', LC.soc_color]];
const STAGES = [['Initial', 'initial', LC.init_color], ['Use', 'use', LC.use_color], ['End-of-Life', 'end_of_life', LC.end_color]];

/** Plot 1 — pillar donut (falls back to bars when a pillar total is negative). */
export const PillarDonutFigure = ({ results, currency }) => {
    const svgRef = useRef(null);
    const { pillar_totals: pt } = computeAllSummaries(results);
    const items = PILLARS.map(([name, key, color]) => [name, pt[key] || 0, color]);
    const ok = items.every(([, v]) => v >= 0);
    return ok
        ? <SimpleDonut items={items.filter(([, v]) => v > 0)} currency={currency} svgRef={svgRef} />
        : <SimpleBars items={items.filter(([, v]) => v !== 0)} currency={currency} svgRef={svgRef} legendTitle="Pillars" />;
};

/** Plot 2 — stage bars. */
export const StageBarsFigure = ({ results, currency }) => {
    const svgRef = useRef(null);
    const { stagewise: st } = computeAllSummaries(results);
    const items = STAGES.map(([label, key, color]) => [label, st[key] || 0, color]).filter(([, v]) => v !== 0);
    return <SimpleBars items={items} currency={currency} svgRef={svgRef} legendTitle="Life Cycle Stages" />;
};

/** Plot 3 — pillar bars stacked by stage. */
export const PillarBarsFigure = ({ results, currency }) => {
    const svgRef = useRef(null);
    const { pillar_wise: pw } = computeAllSummaries(results);
    const groups = PILLARS.map(([pName, pKey]) => ({
        label: pName,
        values: Object.fromEntries(STAGES.map(([sLabel, sKey]) => [sLabel, Math.max(0, pw[sKey]?.[pKey] || 0)])),
    }));
    return <StackedBars groups={groups} segments={STAGES.map(([l, , c]) => [l, c])} currency={currency} svgRef={svgRef} legendTitle="Life Cycle Stages" />;
};
