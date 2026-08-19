/**
 * ResultsView — desktop-parity Results page.
 *
 * Layout, section order, texts, colors, and chart behavior mirror desktop
 * gui/components/outputs/outputs_page.py + plots_helper/{Pie,AggregateChart}.py
 * + lcc_plot.py (LCCDetailsTable / LCCBreakdownTable). Desktop is the visual
 * reference; deviations are limited to platform idioms (SVG instead of
 * matplotlib, a save-image button instead of the full toolbar).
 */
import { Fragment, useMemo, useRef, useState } from 'react';
import * as d3 from 'd3';
import { computeAllSummaries } from './lifecycleSummary';
import { COLORS as LC, PILLAR_COLORS, STAGE_COLORS } from './lccColors';
import { BREAKDOWN_STAGES, CREDIT_KEYS, STAGE_DEFS, STAGE_META, stageTotals } from './lccData';
import { currencyNote, fmtCurrency } from './displayFormat';

const PILLAR_LIST = [
    ['Economic', 'eco', LC.eco_color],
    ['Environmental', 'env', LC.env_color],
    ['Social', 'social', LC.soc_color],
];
const STAGE_LIST = [
    ['Initial', 'initial', LC.init_color],
    ['Use', 'use', LC.use_color],
    ['End-of-Life', 'end_of_life', LC.end_color],
];

const TEXT = 'var(--app-text-primary)';
const TEXT_2 = 'var(--app-text-secondary)';
const SURFACE = 'var(--app-bg-card)';
const SURFACE_MID = 'var(--app-border-mid)';

const short = (v, currency) => fmtCurrency(v, currency, { decimals: 0, style: 'short' });
const shortSuffix = (v, currency) => fmtCurrency(v, currency, { decimals: 0, style: 'short', useShortSuffix: true });

// ─────────────────────────────────────────────────────────────────────────
// Shared building blocks
// ─────────────────────────────────────────────────────────────────────────

const SectionHeading = ({ children }) => (
    <h4 className="fw-bold mt-2 mb-3" style={{ color: TEXT }}>{children}</h4>
);

const SectionDescription = ({ children }) => (
    <p style={{ color: TEXT_2, fontSize: '0.9rem' }}>{children}</p>
);

const Divider = () => <hr style={{ borderColor: SURFACE_MID, opacity: 0.6, margin: '1.5rem 0' }} />;

const KpiCard = ({ title, value, accent, currency, large = false }) => (
    <div
        className="flex-fill"
        style={{
            backgroundColor: SURFACE,
            border: `1px solid ${SURFACE_MID}`,
            borderTop: `3px solid ${accent}`,
            borderRadius: 10,
            padding: '14px 18px',
            minHeight: large ? 110 : 90,
        }}
    >
        <div style={{ color: TEXT_2, fontSize: '0.8rem', fontWeight: 500, letterSpacing: 1 }}>{title}</div>
        <div style={{ color: accent, fontSize: large ? '1.9rem' : '1.4rem', fontWeight: 700, marginTop: 4 }}>
            {short(value, currency)}
        </div>
        <div style={{ color: TEXT_2, opacity: 0.7, fontSize: '0.72rem', letterSpacing: 0.5 }}>{currency}</div>
    </div>
);

/** Desktop ResponsiveTotalCard: total on the left, About text on the right. */
const TotalCard = ({ total, currency, analysisPeriod, yearOfConstruction }) => {
    const ap = analysisPeriod ? `${analysisPeriod} years` : '-';
    const yoc = yearOfConstruction ? String(yearOfConstruction) : '-';
    return (
        <div
            className="d-flex flex-column flex-md-row"
            style={{
                backgroundColor: SURFACE,
                border: `1px solid ${SURFACE_MID}`,
                borderTop: '3px solid var(--app-primary-accent)',
                borderRadius: 10,
                padding: '14px 18px',
                minHeight: 110,
                gap: 18,
            }}
        >
            <div style={{ minWidth: 220 }}>
                <div style={{ color: TEXT_2, fontSize: '0.8rem', fontWeight: 500, letterSpacing: 1 }}>Total Life Cycle Cost</div>
                <div style={{ color: 'var(--app-primary-accent)', fontSize: '2rem', fontWeight: 700, marginTop: 4 }}>
                    {short(total, currency)}
                </div>
                <div style={{ color: TEXT_2, opacity: 0.7, fontSize: '0.72rem', letterSpacing: 0.5 }}>{currency}</div>
            </div>
            <div style={{ borderLeft: `1px solid ${SURFACE_MID}` }} className="d-none d-md-block" />
            <div className="flex-fill">
                <div style={{ color: TEXT_2, fontSize: '0.8rem', fontWeight: 500, letterSpacing: 1 }}>About This Analysis</div>
                <div style={{ color: TEXT, fontSize: '0.9rem', marginTop: 6, textAlign: 'justify' }}>
                    Total life cycle cost (across the three pillars) evaluated over an analysis
                    period of {ap} at the assessment year {yoc}.
                </div>
            </div>
        </div>
    );
};

/** Desktop ratio box: three colored lines — names, percentages, amounts. */
const RatioBox = ({ entries }) => {
    const sep = <span style={{ color: TEXT_2, opacity: 0.6, fontWeight: 700 }}> : </span>;
    const line = (values, mono = false) => (
        <div
            className="text-center"
            style={{ fontWeight: 700, letterSpacing: mono ? 0 : 1.2, fontFamily: mono ? 'Consolas, monospace' : undefined, fontSize: '0.9rem' }}
        >
            {values.map(([text, color], i) => (
                <span key={i}>{i > 0 && sep}<span style={{ color }}>{text}</span></span>
            ))}
        </div>
    );
    return (
        <div style={{ backgroundColor: SURFACE_MID, border: `1px solid ${SURFACE_MID}`, borderRadius: 10, padding: 12 }}>
            {line(entries.map(([name, , , color]) => [name, color]))}
            {line(entries.map(([, pct, , color]) => [`${pct.toFixed(1)}%`, color]), true)}
            {line(entries.map(([, , amt, color]) => [amt, color]))}
        </div>
    );
};

/** Toolbar-lite: save the chart SVG as a PNG (desktop has the mpl toolbar). */
const saveSvgAsPng = (svgEl, fileName) => {
    if (!svgEl) return;
    const xml = new XMLSerializer().serializeToString(svgEl);
    const svgBlob = new Blob([xml], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(svgBlob);
    const img = new Image();
    img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = svgEl.viewBox.baseVal.width * 2;
        canvas.height = svgEl.viewBox.baseVal.height * 2;
        const ctx = canvas.getContext('2d');
        const bg = getComputedStyle(document.body).getPropertyValue('--app-bg-main') || '#1a1a24';
        ctx.fillStyle = bg.trim() || '#1a1a24';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        URL.revokeObjectURL(url);
        const link = document.createElement('a');
        link.download = fileName;
        link.href = canvas.toDataURL('image/png');
        link.click();
    };
    img.src = url;
};

const ChartBox = ({ children, svgRef, fileName }) => (
    <div className="flex-fill" style={{ minWidth: 0 }}>
        {children}
        <div className="text-end">
            <button
                type="button"
                className="btn btn-sm"
                style={{ color: TEXT_2, border: `1px solid ${SURFACE_MID}`, fontSize: '0.72rem', padding: '2px 10px' }}
                onClick={() => saveSvgAsPng(svgRef.current, fileName)}
                title="Save chart as image"
            >
                ⤓ Save
            </button>
        </div>
    </div>
);

// ─────────────────────────────────────────────────────────────────────────
// Chart geometry helpers (desktop Pie.py `_add_smart_labels` port)
// ─────────────────────────────────────────────────────────────────────────

/** Matplotlib-style pie: counterclockwise from 3 o'clock. Returns slices with
 * start/end angles in SVG-arc terms plus the mid-angle unit vector. */
const pieSlices = (values) => {
    const total = values.reduce((s, v) => s + v, 0) || 1;
    let acc = 0;
    return values.map((v) => {
        const a0 = (acc / total) * 2 * Math.PI;
        acc += v;
        const a1 = (acc / total) * 2 * Math.PI;
        const mid = (a0 + a1) / 2;
        return {
            // d3.arc angles are clockwise from 12 o'clock: convert from
            // counterclockwise-from-3-o'clock (matplotlib convention).
            startAngle: Math.PI / 2 - a1,
            endAngle: Math.PI / 2 - a0,
            frac: (a1 - a0) / (2 * Math.PI),
            cx: Math.cos(mid),
            cy: Math.sin(mid),
        };
    });
};

/** Hemisphere label stacking with push-apart relaxation (desktop `_resolve`). */
const resolveLabels = (entries, minGap) => {
    const group = [...entries].sort((a, b) => b.yNat - a.yNat);
    const ys = group.map((e) => e.yNat);
    for (let iter = 0; iter < 300; iter += 1) {
        let moved = false;
        for (let j = 0; j < ys.length - 1; j += 1) {
            const gap = ys[j] - ys[j + 1];
            if (gap < minGap) {
                const shift = (minGap - gap) / 2;
                ys[j] += shift;
                ys[j + 1] -= shift;
                moved = true;
            }
        }
        if (!moved) break;
    }
    return [group, ys];
};

/** Elbow leader labels for donut slices. Returns SVG elements. */
const SmartLabels = ({ slices, labels, radius, leaderRadius, k, cx0, cy0 }) => {
    const entries = slices.map((s, i) => ({
        idx: i,
        cx: s.cx,
        cy: s.cy,
        x0: s.cx * radius,
        y0: s.cy * radius,
        yNat: s.cy * leaderRadius,
        label: labels[i],
    }));
    const maxLines = Math.max(...labels.map((l) => l.length));
    const minGap = maxLines >= 3 ? 0.62 : 0.32;
    const xCol = leaderRadius + 0.22;
    const out = [];

    const draw = (group, ys, ha, colX) => {
        const tick = ha === 'start' ? 0.08 : -0.08;
        group.forEach((e, gi) => {
            const yLbl = ys[gi];
            const px = (u) => cx0 + u * k;
            const py = (u) => cy0 - u * k; // math y-up → svg y-down
            out.push(
                <polyline
                    key={`l${e.idx}`}
                    points={`${px(e.x0)},${py(e.y0)} ${px(e.cx * leaderRadius)},${py(e.yNat)} ${px(colX)},${py(yLbl)}`}
                    fill="none" stroke={SURFACE_MID} strokeWidth={1} opacity={0.9} strokeLinecap="round"
                />,
                <circle key={`d${e.idx}`} cx={px(e.x0)} cy={py(e.y0)} r={2.5} fill={SURFACE_MID} opacity={0.9} />,
            );
            const xTxt = px(colX + tick);
            const parts = e.label;
            if (parts.length === 3) {
                out.push(
                    <text key={`t${e.idx}a`} x={xTxt} y={py(yLbl + 0.16)} textAnchor={ha} dominantBaseline="middle" fill={TEXT} opacity={0.65} fontSize={10}>{parts[0]}</text>,
                    <text key={`t${e.idx}b`} x={xTxt} y={py(yLbl)} textAnchor={ha} dominantBaseline="middle" fill={TEXT} fontWeight={700} fontSize={12}>{parts[1]}</text>,
                    <text key={`t${e.idx}c`} x={xTxt} y={py(yLbl - 0.16)} textAnchor={ha} dominantBaseline="middle" fill={TEXT} opacity={0.65} fontSize={10.5}>{parts[2]}</text>,
                );
            } else if (parts.length === 2) {
                out.push(
                    <text key={`t${e.idx}a`} x={xTxt} y={py(yLbl + 0.09)} textAnchor={ha} dominantBaseline="middle" fill={TEXT} fontWeight={700} fontSize={12}>{parts[0]}</text>,
                    <text key={`t${e.idx}b`} x={xTxt} y={py(yLbl - 0.09)} textAnchor={ha} dominantBaseline="middle" fill={TEXT} opacity={0.65} fontSize={10.5}>{parts[1]}</text>,
                );
            } else {
                out.push(
                    <text key={`t${e.idx}a`} x={xTxt} y={py(yLbl)} textAnchor={ha} dominantBaseline="middle" fill={TEXT} fontWeight={700} fontSize={12}>{parts[0]}</text>,
                );
            }
        });
    };

    const right = entries.filter((e) => e.cx >= 0);
    const left = entries.filter((e) => e.cx < 0);
    if (right.length) { const [g, ys] = resolveLabels(right, minGap); draw(g, ys, 'start', xCol); }
    if (left.length) { const [g, ys] = resolveLabels(left, minGap); draw(g, ys, 'end', -xCol); }
    return out;
};

const donutArc = (k, rOuter, width) => d3.arc()
    .innerRadius((rOuter - width) * k)
    .outerRadius(rOuter * k);

// ─────────────────────────────────────────────────────────────────────────
// Pie card charts
// ─────────────────────────────────────────────────────────────────────────

const W_PIE = 620;
const H_PIE = 440;

/** CHART 0 — simple pillar donut (desktop SimplePillarPlotter). */
const SimpleDonut = ({ items, currency, svgRef }) => {
    const k = 100;
    const cx0 = W_PIE / 2;
    const cy0 = H_PIE / 2 - 20;
    const slices = pieSlices(items.map(([, v]) => v));
    const arc = donutArc(k, 1.05, 0.42 * 1.05);
    const total = items.reduce((s, [, v]) => s + v, 0);
    return (
        <svg ref={svgRef} viewBox={`0 0 ${W_PIE} ${H_PIE}`} style={{ width: '100%', height: 'auto' }}>
            <text x={W_PIE - 8} y={16} textAnchor="end" fill={TEXT} opacity={0.85} fontSize={11}>{currencyNote(currency)}</text>
            {slices.map((s, i) => (
                <path key={i} d={arc(s)} fill={items[i][2]} transform={`translate(${cx0},${cy0})`} />
            ))}
            <SmartLabels
                slices={slices}
                labels={items.map(([l, v]) => [l, short(v, currency)])}
                radius={1.05}
                leaderRadius={1.25}
                k={k} cx0={cx0} cy0={cy0}
            />
            <text x={cx0} y={cy0 - 8} textAnchor="middle" fill={TEXT} fontWeight={700} fontSize={13}>Total</text>
            <text x={cx0} y={cy0 + 10} textAnchor="middle" fill={TEXT} fontWeight={700} fontSize={13}>{short(total, currency)}</text>
            {items.map(([l, , c], i) => {
                const lw = 130;
                const x0 = cx0 - (items.length * lw) / 2 + i * lw;
                return (
                    <g key={l}>
                        <rect x={x0} y={H_PIE - 24} width={12} height={12} fill={c} />
                        <text x={x0 + 18} y={H_PIE - 14} fill={TEXT} fontSize={11}>{l}</text>
                    </g>
                );
            })}
        </svg>
    );
};

/** CHART 1 — nested stage+pillar donut (desktop SustainabilityCircularPlotter). */
const NestedDonut = ({ data, currency, svgRef }) => {
    const k = 92;
    const cx0 = W_PIE / 2;
    const cy0 = H_PIE / 2 - 20;
    const innerVals = data.map((e) => e.pillars.reduce((s, [, v]) => s + v, 0));
    const outer = data.flatMap((e) => e.pillars.map(([name, v, color]) => ({ stage: e.stage, name, v, color })));
    const innerSlices = pieSlices(innerVals);
    const outerSlices = pieSlices(outer.map((o) => o.v));
    const arcInner = donutArc(k, 0.8, 0.3);
    const arcOuter = donutArc(k, 1.1, 0.3);
    const total = innerVals.reduce((s, v) => s + v, 0);

    // Stage separator spokes (desktop draws them from r 0.5 → 1.1)
    const spokes = innerVals.reduce((state, v) => {
        const acc = state.acc + v;
        const a = (acc / (total || 1)) * 2 * Math.PI;
        return { acc, points: [...state.points, [Math.cos(a), Math.sin(a)]] };
    }, { acc: 0, points: [] }).points;

    return (
        <svg ref={svgRef} viewBox={`0 0 ${W_PIE} ${H_PIE}`} style={{ width: '100%', height: 'auto' }}>
            <text x={W_PIE - 8} y={16} textAnchor="end" fill={TEXT} opacity={0.85} fontSize={11}>{currencyNote(currency)}</text>
            {innerSlices.map((s, i) => (
                <path key={`i${i}`} d={arcInner(s)} fill={STAGE_LIST.find(([l]) => l === data[i].stage)?.[2] || '#DDD'} transform={`translate(${cx0},${cy0})`} />
            ))}
            {outerSlices.map((s, i) => (
                <path key={`o${i}`} d={arcOuter(s)} fill={outer[i].color} transform={`translate(${cx0},${cy0})`} />
            ))}
            {spokes.map(([x, y], i) => (
                <line
                    key={`s${i}`}
                    x1={cx0 + 0.5 * k * x} y1={cy0 - 0.5 * k * y}
                    x2={cx0 + 1.1 * k * x} y2={cy0 - 1.1 * k * y}
                    stroke={SURFACE_MID} strokeWidth={1.5} opacity={0.5}
                />
            ))}
            <SmartLabels
                slices={outerSlices}
                labels={outer.map((o) => [o.stage, o.name, short(o.v, currency)])}
                radius={1.1}
                leaderRadius={1.45}
                k={k} cx0={cx0} cy0={cy0}
            />
            <text x={cx0} y={cy0 - 8} textAnchor="middle" fill={TEXT} fontWeight={700} fontSize={13}>Total</text>
            <text x={cx0} y={cy0 + 10} textAnchor="middle" fill={TEXT} fontWeight={700} fontSize={13}>{short(total, currency)}</text>
            {PILLAR_LIST.map(([pName, , pColor], col) => {
                const [sName, , sColor] = STAGE_LIST[col];
                const lw = 150;
                const x0 = cx0 - (3 * lw) / 2 + col * lw;
                return (
                    <g key={pName}>
                        <rect x={x0} y={H_PIE - 38} width={12} height={12} fill={pColor} />
                        <text x={x0 + 18} y={H_PIE - 28} fill={TEXT} fontSize={11}>{pName}</text>
                        <rect x={x0} y={H_PIE - 20} width={12} height={12} fill={sColor} />
                        <text x={x0 + 18} y={H_PIE - 10} fill={TEXT} fontSize={11}>{sName}</text>
                    </g>
                );
            })}
        </svg>
    );
};

// ─────────────────────────────────────────────────────────────────────────
// Bar charts (desktop AggregateChart.py plotters)
// ─────────────────────────────────────────────────────────────────────────

const W_BAR = 620;
const H_BAR = 400;
const M_BAR = { top: 36, right: 150, bottom: 44, left: 78 };

const BarFrame = ({ currency, yScale, children, svgRef, legend, legendTitle }) => {
    const innerH = H_BAR - M_BAR.top - M_BAR.bottom;
    const ticks = yScale.ticks(6);
    return (
        <svg ref={svgRef} viewBox={`0 0 ${W_BAR} ${H_BAR}`} style={{ width: '100%', height: 'auto' }}>
            <text x={W_BAR - 8} y={16} textAnchor="end" fill={TEXT} opacity={0.85} fontSize={11}>{currencyNote(currency)}</text>
            {ticks.map((t) => (
                <g key={t}>
                    <line x1={M_BAR.left} x2={W_BAR - M_BAR.right} y1={yScale(t)} y2={yScale(t)} stroke={SURFACE_MID} opacity={0.5} strokeDasharray="2,3" />
                    <text x={M_BAR.left - 8} y={yScale(t) + 3} textAnchor="end" fill={TEXT_2} fontSize={10}>{short(t, currency)}</text>
                </g>
            ))}
            <text
                transform={`translate(16, ${M_BAR.top + innerH / 2}) rotate(-90)`}
                textAnchor="middle" fill={TEXT_2} fontSize={11}
            >
                Cost
            </text>
            {children}
            {/* Legend (desktop _make_legend: right side with title) */}
            <g transform={`translate(${W_BAR - M_BAR.right + 16}, ${M_BAR.top + 4})`}>
                <text x={0} y={0} fill={TEXT} fontWeight={700} fontSize={11}>{legendTitle}</text>
                {legend.map(([label, color], i) => (
                    <g key={label} transform={`translate(0, ${14 + i * 18})`}>
                        <rect width={12} height={12} fill={color} />
                        <text x={18} y={10} fill={TEXT} fontSize={11}>{label}</text>
                    </g>
                ))}
            </g>
        </svg>
    );
};

/** Simple bars with value labels above (desktop StageBarPlotter). */
const SimpleBars = ({ items, currency, svgRef, legendTitle = 'Life Cycle Stages' }) => {
    const values = items.map(([, v]) => v);
    const maxV = Math.max(0, ...values);
    const minV = Math.min(0, ...values);
    const pad = (maxV - minV) * 0.12 || 1;
    const yScale = d3.scaleLinear()
        .domain([Math.min(0, minV) - pad, Math.max(0, maxV) + pad])
        .range([H_BAR - M_BAR.bottom, M_BAR.top]);
    const innerW = W_BAR - M_BAR.left - M_BAR.right;
    const step = innerW / items.length;
    const barW = step * (0.5 / 0.75);
    return (
        <BarFrame currency={currency} yScale={yScale} svgRef={svgRef} legendTitle={legendTitle}
            legend={items.map(([l, , c]) => [l, c])}>
            {items.map(([label, v, color], i) => {
                const x = M_BAR.left + i * step + (step - barW) / 2;
                const y0 = yScale(0);
                const y1 = yScale(v);
                return (
                    <g key={label}>
                        <rect x={x} y={Math.min(y0, y1)} width={barW} height={Math.abs(y1 - y0)} fill={color} />
                        <text
                            x={x + barW / 2}
                            y={v >= 0 ? y1 - 6 : y1 + 14}
                            textAnchor="middle" fill={TEXT} fontWeight={700} fontSize={11}
                        >
                            {short(v, currency)}
                        </text>
                        <text x={x + barW / 2} y={H_BAR - M_BAR.bottom + 18} textAnchor="middle" fill={TEXT_2} fontSize={11}>{label}</text>
                    </g>
                );
            })}
        </BarFrame>
    );
};

/** Stacked bars (desktop SustainabilityBarPlotter / PillarBreakdownBarPlotter). */
const StackedBars = ({ groups, segments, currency, svgRef, legendTitle }) => {
    // groups: [{label, values: {segName: v}}]; segments: [[name, color]]
    const totals = groups.map((g) => segments.reduce((s, [n]) => s + (g.values[n] || 0), 0));
    const maxV = Math.max(0, ...totals);
    const pad = maxV * 0.12 || 1;
    const yScale = d3.scaleLinear().domain([0, maxV + pad]).range([H_BAR - M_BAR.bottom, M_BAR.top]);
    const innerW = W_BAR - M_BAR.left - M_BAR.right;
    const step = innerW / groups.length;
    const barW = step * (0.5 / 0.75);
    return (
        <BarFrame currency={currency} yScale={yScale} svgRef={svgRef} legendTitle={legendTitle} legend={segments}>
            {groups.map((g, i) => {
                const x = M_BAR.left + i * step + (step - barW) / 2;
                let yCursor = yScale(0);
                return (
                    <g key={g.label}>
                        {segments.map(([name, color]) => {
                            const v = g.values[name] || 0;
                            if (v <= 0) return null;
                            const h = yScale(0) - yScale(v);
                            yCursor -= h;
                            return <rect key={name} x={x} y={yCursor} width={barW} height={h} fill={color} />;
                        })}
                        <text x={x + barW / 2} y={yScale(totals[i]) - 6} textAnchor="middle" fill={TEXT} fontWeight={700} fontSize={11}>
                            {short(totals[i], currency)}
                        </text>
                        <text x={x + barW / 2} y={H_BAR - M_BAR.bottom + 18} textAnchor="middle" fill={TEXT_2} fontSize={11}>{g.label}</text>
                    </g>
                );
            })}
        </BarFrame>
    );
};

// ─────────────────────────────────────────────────────────────────────────
// Card 1 — "Across 3 Pillars of Sustainability" (desktop LCCPieWidget)
// ─────────────────────────────────────────────────────────────────────────

const PieCard = ({ results, currency, chartRef }) => {
    const [stageWise, setStageWise] = useState(false);
    const [barMode, setBarMode] = useState(false);
    const svgRef = useRef(null);

    const summary = useMemo(() => computeAllSummaries(results), [results]);
    const pt = summary.pillar_totals;
    const pw = summary.pillar_wise;

    const pillarOk = [pt.eco, pt.env, pt.social].every((v) => v >= 0);
    const nestedOk = Object.values(pw).every((s) => [s.eco, s.env, s.social].every((v) => v >= 0));

    const sumPt = (pt.eco + pt.env + pt.social) || 1;
    const ratioEntries = PILLAR_LIST.map(([name, key, color]) => [
        name, (pt[key] / sumPt) * 100, shortSuffix(pt[key], currency), color,
    ]);

    const donutItems = PILLAR_LIST.map(([name, key, color]) => [name, pt[key], color]).filter(([, v]) => v > 0);
    const nestedData = STAGE_LIST.map(([label, key]) => ({
        stage: label,
        pillars: PILLAR_LIST.map(([pName, pKey, pColor]) => [pName, pw[key]?.[pKey] || 0, pColor]),
    })).filter((e) => e.pillars.some(([, v]) => v > 0));
    const pillarBarItems = PILLAR_LIST.map(([name, key, color]) => [name, pt[key], color]).filter(([, v]) => v !== 0);
    const stackedGroups = PILLAR_LIST.map(([pName, pKey]) => ({
        label: pName,
        values: Object.fromEntries(STAGE_LIST.map(([sLabel, sKey]) => [sLabel, pw[sKey]?.[pKey] || 0])),
    }));

    let chart;
    if (!pillarOk) {
        chart = <SimpleBars items={pillarBarItems} currency={currency} svgRef={svgRef} />;
    } else if (barMode && stageWise) {
        chart = <StackedBars groups={stackedGroups} segments={STAGE_LIST.map(([l, , c]) => [l, c])} currency={currency} svgRef={svgRef} legendTitle="Life Cycle Stages" />;
    } else if (barMode) {
        chart = <SimpleBars items={pillarBarItems} currency={currency} svgRef={svgRef} />;
    } else if (stageWise && nestedOk) {
        chart = <NestedDonut data={nestedData} currency={currency} svgRef={svgRef} />;
    } else {
        chart = <SimpleDonut items={donutItems} currency={currency} svgRef={svgRef} />;
    }

    return (
        <div ref={chartRef} style={{ border: `1.5px solid ${SURFACE_MID}`, borderRadius: 14, padding: '20px 24px', margin: '14px 0' }}>
            <div className="d-flex flex-column flex-lg-row" style={{ gap: 24 }}>
                <div className="d-flex flex-column justify-content-center" style={{ flex: '0 0 auto', width: '100%', maxWidth: 350, gap: 14, margin: '0 auto' }}>
                    <h5 className="text-center fw-bold m-0" style={{ color: TEXT, letterSpacing: 0.5 }}>Across 3 Pillars of Sustainability</h5>
                    <RatioBox entries={ratioEntries} />
                    {pillarOk && (
                        <div className="form-check d-flex justify-content-center gap-2">
                            <input className="form-check-input" type="checkbox" id="cb-stagewise" checked={stageWise} disabled={!nestedOk} onChange={(e) => setStageWise(e.target.checked)} />
                            <label className="form-check-label" htmlFor="cb-stagewise" style={{ color: TEXT_2, fontSize: '0.88rem' }}>Include stage-wise break-up</label>
                        </div>
                    )}
                    {pillarOk && !nestedOk && (
                        <div className="text-center fst-italic" style={{ color: TEXT_2, fontSize: '0.75rem' }}>
                            * Stage breakdown unavailable- negative values in stage data.
                        </div>
                    )}
                    {pillarOk && (
                        <div className="form-check d-flex justify-content-center gap-2">
                            <input className="form-check-input" type="checkbox" id="cb-barmode" checked={barMode} onChange={(e) => setBarMode(e.target.checked)} />
                            <label className="form-check-label" htmlFor="cb-barmode" style={{ color: TEXT_2, fontSize: '0.88rem' }}>Change to bar chart</label>
                        </div>
                    )}
                </div>
                <ChartBox svgRef={svgRef} fileName="lcc_pillars.png">{chart}</ChartBox>
            </div>
            {!pillarOk && (
                <div className="text-center fst-italic mt-2" style={{ color: TEXT_2, fontSize: '0.75rem' }}>
                    * Negative cost values detected- pie chart unavailable, showing bar chart instead.
                </div>
            )}
        </div>
    );
};

// ─────────────────────────────────────────────────────────────────────────
// Card 2 — "Across 3 Stages" (desktop AggregateChartWidget)
// ─────────────────────────────────────────────────────────────────────────

const AggregateCard = ({ results, currency, chartRef }) => {
    const [pillarWise, setPillarWise] = useState(false);
    const svgRef = useRef(null);

    const summary = useMemo(() => computeAllSummaries(results), [results]);
    const st = summary.stagewise;
    const pw = summary.pillar_wise;

    const sumStages = STAGE_LIST.reduce((s, [, key]) => s + Math.abs(st[key] || 0), 0) || 1;
    const ratioEntries = STAGE_LIST.map(([name, key, color]) => [
        name, ((st[key] || 0) / sumStages) * 100, shortSuffix(st[key] || 0, currency), color,
    ]);

    const stageItems = STAGE_LIST.map(([label, key, color]) => [label, st[key] || 0, color]).filter(([, v]) => v !== 0);
    const stackedGroups = STAGE_LIST.map(([sLabel, sKey]) => ({
        label: sLabel,
        values: Object.fromEntries(PILLAR_LIST.map(([pName, pKey]) => [pName, pw[sKey]?.[pKey] || 0])),
    })).filter((g) => Object.values(g.values).some((v) => v !== 0));

    return (
        <div ref={chartRef} style={{ border: `1.5px solid ${SURFACE_MID}`, borderRadius: 14, padding: '20px 24px', margin: '14px 0' }}>
            <div className="d-flex flex-column flex-lg-row" style={{ gap: 24 }}>
                <div className="d-flex flex-column justify-content-center" style={{ flex: '0 0 auto', width: '100%', maxWidth: 350, gap: 14, margin: '0 auto' }}>
                    <h5 className="text-center fw-bold m-0" style={{ color: TEXT, letterSpacing: 0.5 }}>Across 3 Stages</h5>
                    <RatioBox entries={ratioEntries} />
                    <div className="form-check d-flex justify-content-center gap-2">
                        <input className="form-check-input" type="checkbox" id="cb-pillarwise" checked={pillarWise} onChange={(e) => setPillarWise(e.target.checked)} />
                        <label className="form-check-label" htmlFor="cb-pillarwise" style={{ color: TEXT_2, fontSize: '0.88rem' }}>Show pillar wise</label>
                    </div>
                </div>
                <ChartBox svgRef={svgRef} fileName="lcc_stages.png">
                    {pillarWise
                        ? <StackedBars groups={stackedGroups} segments={PILLAR_LIST.map(([l, , c]) => [l, c])} currency={currency} svgRef={svgRef} legendTitle="Pillars" />
                        : <SimpleBars items={stageItems} currency={currency} svgRef={svgRef} legendTitle="Life Cycle Stages" />}
                </ChartBox>
            </div>
        </div>
    );
};

// ─────────────────────────────────────────────────────────────────────────
// Consolidated stage summary table (desktop LCCDetailsTable)
// ─────────────────────────────────────────────────────────────────────────

const DARK_ON_CHIP = '#1e1e28';

const DetailsTable = ({ results, currency }) => {
    const rows = [];
    const grand = [0, 0, 0, 0];
    let reconVals = null;

    for (const [stageLabel, resultKey, catKeys] of STAGE_DEFS) {
        const totals = stageTotals(results, resultKey, catKeys);
        if (!Object.keys(totals).length || !results?.[resultKey] || !Object.keys(results[resultKey]).length) continue;
        let vals = [totals.Economic || 0, totals.Environmental || 0, totals.Social || 0];
        vals.push(vals[0] + vals[1] + vals[2]);
        if (resultKey === 'reconstruction') { reconVals = vals; continue; }
        if (resultKey === 'end_of_life' && reconVals) vals = vals.map((v, i) => v + reconVals[i]);
        rows.push([stageLabel, resultKey, vals]);
        vals.forEach((v, i) => { grand[i] += v; });
    }

    const headerCell = (label, bg) => (
        <th
            className="text-center"
            style={{
                backgroundColor: bg || SURFACE,
                color: bg ? DARK_ON_CHIP : TEXT,
                border: `1px solid ${SURFACE_MID}`,
                fontSize: '0.85rem',
                padding: '10px 12px',
                whiteSpace: 'pre-line',
            }}
        >
            {label}
        </th>
    );

    const numCell = (v, bold = false, bg = null) => (
        <td
            className="text-end"
            style={{
                border: `1px solid ${SURFACE_MID}`,
                color: bg ? DARK_ON_CHIP : TEXT,
                backgroundColor: bg || 'transparent',
                fontWeight: bold ? 700 : 600,
                fontSize: '0.85rem',
                padding: '10px 12px',
            }}
        >
            {fmtCurrency(v, currency, { decimals: 2 })}
        </td>
    );

    return (
        <div className="table-responsive" style={{ border: `1px solid ${SURFACE_MID}`, borderRadius: 8 }}>
            <table className="m-0" style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                    <tr>
                        {headerCell('Stage')}
                        {headerCell(`Economic\n(${currency})`, LC.eco_color)}
                        {headerCell(`Environmental\n(${currency})`, LC.env_color)}
                        {headerCell(`Social\n(${currency})`, LC.soc_color)}
                        {headerCell(`Stage Total\n(${currency})`)}
                    </tr>
                </thead>
                <tbody>
                    {rows.map(([label, key, vals]) => (
                        <tr key={key}>
                            <td style={{
                                backgroundColor: STAGE_COLORS[key] || 'transparent',
                                color: DARK_ON_CHIP,
                                fontWeight: 600,
                                border: `1px solid ${SURFACE_MID}`,
                                fontSize: '0.85rem',
                                padding: '10px 12px',
                            }}>
                                {label}
                            </td>
                            {vals.map((v, i) => <Fragment key={i}>{numCell(v)}</Fragment>)}
                        </tr>
                    ))}
                    <tr>
                        <td style={{ backgroundColor: SURFACE_MID, color: TEXT, fontWeight: 700, border: `1px solid ${SURFACE_MID}`, fontSize: '0.85rem', padding: '10px 12px' }}>Total</td>
                        {grand.map((v, i) => <Fragment key={i}>{numCell(v, true, null)}</Fragment>)}
                    </tr>
                </tbody>
            </table>
        </div>
    );
};

// ─────────────────────────────────────────────────────────────────────────
// Itemized breakdown (desktop LCCBreakdownTable)
// ─────────────────────────────────────────────────────────────────────────

const PASTELS = Object.fromEntries(STAGE_META.map(([sk, , , pastel, tick]) => [sk, { pastel, tick }]));

const BreakdownTable = ({ results, currency }) => {
    // Build rows exactly like desktop `_build`: reconstruction folded into
    // the End-of-Life block with a "Reconstruction | " prefix.
    const blocks = [];
    let bufferedRecon = null;
    const pillarOrder = { economic: 0, environmental: 1, social: 2 };

    for (const stageDef of BREAKDOWN_STAGES) {
        const stageData = results?.[stageDef.result_key] || {};
        if (stageDef.optional && (typeof stageData.economic !== 'object' || stageData.economic === null)) continue;

        let stageRows = [];
        for (const [cat, key, label] of stageDef.rows) {
            const raw = stageData?.[cat]?.[key];
            if (raw !== undefined && raw !== null) {
                const val = CREDIT_KEYS.has(key) ? -Number(raw) : Number(raw);
                stageRows.push([cat, label, val]);
            }
        }
        if (!stageRows.length) continue;
        if (stageDef.optional && stageRows.every(([, , v]) => v === 0)) continue;
        stageRows.sort((a, b) => (pillarOrder[a[0]] ?? 9) - (pillarOrder[b[0]] ?? 9));

        if (stageDef.result_key === 'reconstruction') {
            bufferedRecon = stageRows;
        } else if (stageDef.result_key === 'end_of_life') {
            const merged = [
                ...(bufferedRecon || []).map(([cat, label, v]) => [cat, `Reconstruction | ${label}`, v]),
                ...stageRows,
            ];
            blocks.push({ key: stageDef.result_key, label: stageDef.label, rows: merged });
        } else {
            blocks.push({ key: stageDef.result_key, label: stageDef.label, rows: stageRows });
        }
    }

    const maxVal = Math.max(1, ...blocks.flatMap((b) => b.rows.map(([, , v]) => Math.abs(v))));

    // Bar geometry: a zero line 15% into the bar column; positives grow
    // right, negatives grow left (desktop draws credits leftward).
    const BAR_ZERO = 15;
    const bar = (v, cat) => {
        const w = (Math.abs(v) / maxVal) * (v >= 0 ? 100 - BAR_ZERO : BAR_ZERO);
        return (
            <div style={{ position: 'relative', height: 12, width: '100%' }}>
                <div style={{
                    position: 'absolute',
                    left: v >= 0 ? `${BAR_ZERO}%` : `${BAR_ZERO - w}%`,
                    width: `${Math.max(w, Math.abs(v) > 0 ? 0.6 : 0)}%`,
                    top: 0, bottom: 0,
                    backgroundColor: PILLAR_COLORS[cat] || '#999',
                    borderRadius: 2,
                }} />
            </div>
        );
    };

    return (
        <div>
            <div className="d-flex gap-4 mb-2">
                {PILLAR_LIST.map(([name, , color]) => (
                    <span key={name} className="d-flex align-items-center gap-2" style={{ color: TEXT, fontSize: '0.85rem' }}>
                        <span style={{ width: 12, height: 12, backgroundColor: color, display: 'inline-block' }} />
                        {name}
                    </span>
                ))}
            </div>
            <div style={{ border: `1px solid ${SURFACE_MID}`, borderRadius: 8, overflow: 'hidden' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                        <tr>
                            {['Stage', 'Cost Item', `Value (${currency})`, 'Relative Cost'].map((h, i) => (
                                <th key={h} className={i >= 2 ? 'text-end' : ''} style={{
                                    backgroundColor: SURFACE,
                                    color: TEXT,
                                    border: `1px solid ${SURFACE_MID}`,
                                    fontSize: '0.85rem',
                                    padding: '10px 12px',
                                    width: i === 0 ? 56 : i === 1 ? '32%' : i === 2 ? '18%' : undefined,
                                    textAlign: i === 3 ? 'left' : undefined,
                                }}>{h}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {blocks.map((block) => block.rows.map(([cat, label, v], ri) => (
                            <tr key={`${block.key}-${ri}`} style={{ backgroundColor: PASTELS[block.key]?.pastel || '#eee' }}>
                                {ri === 0 && (
                                    <td rowSpan={block.rows.length} style={{
                                        border: `1px solid ${SURFACE_MID}`,
                                        width: 56,
                                        position: 'relative',
                                        backgroundColor: PASTELS[block.key]?.pastel || '#eee',
                                    }}>
                                        <div style={{
                                            writingMode: 'vertical-rl',
                                            transform: 'rotate(180deg)',
                                            margin: '0 auto',
                                            color: PASTELS[block.key]?.tick || DARK_ON_CHIP,
                                            fontWeight: 700,
                                            fontSize: '0.8rem',
                                            whiteSpace: 'nowrap',
                                        }}>
                                            {block.label}
                                        </div>
                                    </td>
                                )}
                                <td style={{ border: `1px solid ${SURFACE_MID}`, color: DARK_ON_CHIP, fontSize: '0.85rem', padding: '8px 12px' }}>{label}</td>
                                <td className="text-end" style={{ border: `1px solid ${SURFACE_MID}`, color: DARK_ON_CHIP, fontWeight: 600, fontSize: '0.85rem', padding: '8px 12px', whiteSpace: 'nowrap' }}>
                                    {fmtCurrency(v, currency, { decimals: 2 })}
                                </td>
                                <td style={{ border: `1px solid ${SURFACE_MID}`, padding: '8px 12px' }}>{bar(v, cat)}</td>
                            </tr>
                        )))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

// ─────────────────────────────────────────────────────────────────────────
// Page
// ─────────────────────────────────────────────────────────────────────────

const ResultsView = ({
    results,
    currency,
    analysisPeriod,
    yearOfConstruction,
    pieChartRef,
    barChartRef,
}) => {
    const summary = useMemo(() => computeAllSummaries(results || {}), [results]);
    const stagewise = summary.stagewise;
    const pt = summary.pillar_totals;
    const grandTotal = (stagewise.initial || 0) + (stagewise.use || 0) + (stagewise.end_of_life || 0);

    return (
        <div>
            {/* Summary (desktop LCCSummaryCards) */}
            <SectionHeading>Summary</SectionHeading>
            <div className="d-flex flex-column" style={{ gap: 12 }}>
                <TotalCard total={grandTotal} currency={currency} analysisPeriod={analysisPeriod} yearOfConstruction={yearOfConstruction} />
                <div className="d-flex flex-column flex-md-row" style={{ gap: 12 }}>
                    {PILLAR_LIST.map(([title, key, accent]) => (
                        <KpiCard key={title} title={title} value={pt[key] || 0} accent={accent} currency={currency} />
                    ))}
                </div>
                <div className="d-flex flex-column flex-md-row" style={{ gap: 12 }}>
                    {STAGE_LIST.map(([title, key, accent]) => (
                        <KpiCard key={title} title={title} value={stagewise[key] || 0} accent={accent} currency={currency} />
                    ))}
                </div>
            </div>

            <Divider />

            {/* Distribution of LCC */}
            <SectionHeading>Distribution of LCC</SectionHeading>
            <SectionDescription>
                These charts illustrate the distribution of the total life cycle cost. The
                Sustainability Matrix disaggregates costs across the Economic, Environmental,
                and Social Pillars. The aggregation chart compares the relative weight of three
                life cycle phases: Initial Construction, the combined Use/Maintenance/Reconstruction
                stage, and the final End-of-Life phase.
            </SectionDescription>
            <PieCard results={results} currency={currency} chartRef={pieChartRef} />
            <AggregateCard results={results} currency={currency} chartRef={barChartRef} />

            <Divider />

            {/* Consolidated stage summary */}
            <SectionHeading>Consolidated stage summary</SectionHeading>
            <SectionDescription>
                A consolidated presentation of costs across the three pillars (economic, social,
                and environmental) for each life cycle stage. This table facilitates the
                identification of phases that bear the most substantial burden.
            </SectionDescription>
            <DetailsTable results={results} currency={currency} />

            <Divider />

            <BreakdownTable results={results} currency={currency} />
        </div>
    );
};

export default ResultsView;
