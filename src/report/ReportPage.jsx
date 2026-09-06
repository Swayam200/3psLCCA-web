/**
 * HTML report page — renders the report document (reportDocument.js) as a
 * printable, LaTeX-styled article.
 *
 * Two views of the same document:
 *   • continuous — one scrolling page, instant;
 *   • page preview — Paged.js lays the article out into real A4 pages
 *     (page numbers, running headers, numbered contents), and "Print" hands
 *     exactly those pages to the browser's print engine (Save as PDF).
 */
import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import ReportSectionModal from '../gui/components/outputs/ReportSectionModal.jsx';
import { buildReportDocument } from './reportDocument.js';
import { EMDASH, reportFileStem } from './reportFormat.js';
import {
    APPENDIX_A, APPENDIX_B, APPENDIX_B_GLOSSARY, APP_LOGO, CONSTRUCTION_LEGEND, DISCLAIMER,
    FRAMEWORK_FIGURE, INTRODUCTION, PREPARED_USING, REPORT_TITLE, SUMMARY_LEAD,
} from './reportContent.js';
import { PillarBarsFigure, PillarDonutFigure, StageBarsFigure } from './ReportCharts.jsx';
import { paginate, teardown } from './pagedPreview.js';
import Equation from './Equation.jsx';
import './report.css';
import './reportShell.css';

const FIGURE_COMPONENTS = {
    pillar_donut: PillarDonutFigure,
    stage_bars: StageBarsFigure,
    pillar_bars: PillarBarsFigure,
};

const base = () => {
    const b = (typeof import.meta !== 'undefined' && import.meta.env?.BASE_URL) || '/';
    return b.endsWith('/') ? b : `${b}/`;
};
const asset = (path) => `${base()}${path}`;

/* ── Generic building blocks ─────────────────────────────────────────────── */

const Caption = ({ kind, no, text }) => (
    <figcaption><b>{kind} {no}.</b> {text}</figcaption>
);

const Notes = ({ notes }) => (notes ? <p className="note"><b>{notes.label}:</b> {notes.text}</p> : null);

/** desktop fields_to_latex: two-column table with bold group rows. */
const FieldsTable = ({ tableNo, caption, rows, notes }) => (
    <>
        <figure className="table" id={`table-${tableNo}`}>
            <Caption kind="Table" no={tableNo} text={caption} />
            <table className="kv">
                <tbody>
                    {rows.map((row, i) => (row.group
                        ? <tr key={i} className={`group${i ? ' sep' : ''}`}><td colSpan={2}>{row.group}</td></tr>
                        : <tr key={i}><td>{row.label}</td><td>{row.value}</td></tr>))}
                </tbody>
            </table>
        </figure>
        <Notes notes={notes} />
    </>
);

/** longtable_sections: header row + bold section rows + data rows. */
const SectionedTable = ({ tableNo, caption, headers, sections, renderRow, compact = true }) => (
    <figure className="table long" id={`table-${tableNo}`}>
        <Caption kind="Table" no={tableNo} text={caption} />
        <table className={compact ? 'compact' : ''}>
            <thead><tr>{headers.map((h, i) => <th key={i} className={h.align || ''}>{h.label ?? h}</th>)}</tr></thead>
            <tbody>
                {sections.map((section, si) => (
                    <Fragment key={si}>
                        <tr className={`group${si ? ' sep' : ''}`}><td colSpan={headers.length}>{section.header}</td></tr>
                        {section.rows.map((row, ri) => <tr key={ri}>{renderRow(row)}</tr>)}
                    </Fragment>
                ))}
            </tbody>
        </table>
    </figure>
);

const num = (v, key) => <td key={key} className="num">{v}</td>;
const ctr = (v, key) => <td key={key} className="ctr">{v}</td>;

/* ── Sections ────────────────────────────────────────────────────────────── */

const TitlePage = ({ page, currency }) => (
    <section className="title-page">
        {/* Source of the running header; must sit inside the first page's
            content or Paged.js gives it a page of its own. */}
        <span className="running-title">{page.projectName}</span>
        <div className="tri-bar-vertical" />
        <div className="logos">
            {page.agencyLogo
                ? <img className="agency" src={page.agencyLogo} alt="Agency logo" />
                : <span className="logo-placeholder">[Agency Logo]</span>}
            <img className="app" src={asset(APP_LOGO)} alt="3psLCCA" />
        </div>
        <h1>{REPORT_TITLE}</h1>
        <div className="tri-bar" />
        <div className="infocard">
            <div className="sec-head">Project information</div>
            <table className="info">
                <tbody>
                    <tr><td>Project name:</td><td>{page.projectName}</td></tr>
                    <tr><td>Project code:</td><td>{page.projectCode}</td></tr>
                    <tr><td>Project description:</td><td>{page.description}</td></tr>
                    <tr><td>Currency:</td><td>{currency}</td></tr>
                    <tr><td>Prepared using:</td><td>{PREPARED_USING.label} (<a href={PREPARED_USING.url}>{PREPARED_USING.display}</a>)</td></tr>
                </tbody>
            </table>
        </div>
        <div className="signatures">
            {[['Evaluated by', page.evaluatedBy], ['Reviewed by', page.reviewedBy]].map(([head, who]) => (
                <div key={head}>
                    <div className="sig-head">{head}</div>
                    <table className="info">
                        <tbody>
                            <tr><td>Name:</td><td>{who.name}</td></tr>
                            <tr><td>Organization:</td><td>{who.organization}</td></tr>
                            <tr><td>Address:</td><td>{who.address}</td></tr>
                            <tr><td>Email:</td><td>{who.email}</td></tr>
                            <tr><td>Phone:</td><td>{who.phone}</td></tr>
                        </tbody>
                    </table>
                    <div className="signature-line">Signature</div>
                </div>
            ))}
        </div>
        <div className="footer">
            <div>
                <div className="brand">3psLCCA</div>
                <div className="brand">Osdag, IIT Bombay</div>
                <a href={PREPARED_USING.url}>{PREPARED_USING.display}</a>
            </div>
            <div className="disclaimer">{DISCLAIMER}</div>
        </div>
    </section>
);

/** Contents entry: title link, dotted leader, page number (resolved by Paged.js). */
const TocItem = ({ href, level, children }) => (
    <li className={`l${level}`}>
        <a href={href}>{children}</a>
        <span className="dots" />
        <span className="pg"><a href={href} aria-hidden="true" /></span>
    </li>
);

const Toc = ({ entries, tables, figures, runningTitle }) => (
    <section className="toc">
        {runningTitle && <span className="running-title">{runningTitle}</span>}
        <h2>Contents</h2>
        <ol>
            {entries.map((e) => (
                <TocItem key={e.id} href={`#${e.id}`} level={e.level}>{e.number ? `${e.number} ` : ''}{e.title}</TocItem>
            ))}
        </ol>
        {tables.length > 0 && (
            <>
                <h3>List of Tables</h3>
                <ol>{tables.map((t) => <TocItem key={t.no} href={`#table-${t.no}`} level={2}>Table {t.no}. {t.caption}</TocItem>)}</ol>
            </>
        )}
        {figures.length > 0 && (
            <>
                <h3>List of Figures</h3>
                <ol>{figures.map((f) => <TocItem key={f.no} href={`#figure-${f.no}`} level={2}>Figure {f.no}. {f.caption}</TocItem>)}</ol>
            </>
        )}
    </section>
);

const ConstructionSection = ({ section }) => (
    <>
        {section.tables.map((table) => (
            <Fragment key={table.chunkId}>
                <SectionedTable
                    tableNo={table.tableNo}
                    caption={table.caption}
                    headers={['Material', { label: 'Quantity', align: 'num' }, { label: 'Unit', align: 'ctr' }, { label: 'Rate/Unit', align: 'num' }, { label: 'Rate Source', align: 'ctr' }, { label: `Total (${table.currency})`, align: 'num' }]}
                    sections={table.sections}
                    renderRow={(r) => [
                        <td key="m">{r.material}{r.mark && <sup className="src-mark">{r.mark}</sup>}</td>,
                        num(r.quantity, 'q'), ctr(r.unit, 'u'), num(r.rate, 'r'), ctr(r.source ?? '—', 's'), num(r.total, 't'),
                    ]}
                />
                <p className="caption-note">
                    All rates and totals in {table.currency}.{' '}
                    {CONSTRUCTION_LEGEND.map(([mark, meaning]) => <span key={mark}><sup className="src-mark">{mark}</sup> {meaning};&nbsp; </span>)}
                </p>
            </Fragment>
        ))}
        {section.tables.length === 0 && <p className="empty">No construction data entered.</p>}
    </>
);

const GlobalTraffic = ({ s }) => (
    <>
        <p>
            For this project, the road user cost incurred during the construction phase has been assessed on a per-day basis.
            The total road user cost per day, accounting for delays, detours, and associated user inconveniences, is{' '}
            <b>{s.costText} {s.currency}/day</b>.{s.source ? ` This estimate is based on ${s.source}.` : ' Source not mentioned.'}{s.comments ? ` ${s.comments}` : ''}
        </p>
        <p><b>Road User Cost per Day:</b> <b>{s.costText} {s.currency}/day</b></p>
        <p><b>Source:</b> {s.source || 'Not mentioned'}</p>
        {s.comments && <p><b>Comments:</b> {s.comments}</p>}
    </>
);

const SimpleRowsTable = ({ tableNo, caption, headers, rows, totalRow }) => (
    <figure className="table" id={`table-${tableNo}`}>
        <Caption kind="Table" no={tableNo} text={caption} />
        <table>
            <thead><tr>{headers.map((h, i) => <th key={i} className={i ? 'num' : ''}>{h}</th>)}</tr></thead>
            <tbody>
                {rows.map((r, i) => <tr key={i}>{r.map((c, j) => (j ? num(c, j) : <td key={j}>{c}</td>))}</tr>)}
                {totalRow && <tr className="total">{totalRow.map((c, j) => (j ? num(c, j) : <td key={j}>{c}</td>))}</tr>}
            </tbody>
        </table>
    </figure>
);

const SccSection = ({ s }) => (
    <>
        <p className="intro">{s.intro}</p>
        {s.kind === 'scc-ricke' ? (
            <>
                <FieldsTable tableNo={s.tableNo} caption={s.caption} rows={s.rows} />
                <p>The applied Social Cost of Carbon is <b>{s.applied} {s.currency}/kgCO₂e</b>. For further reference, see <a href={s.explorerUrl}>Country-level SCC Explorer</a>.</p>
            </>
        ) : (
            <p>The Social Cost of Carbon (SCC) is entered manually as <b>{s.value} {s.currency}/kgCO₂e</b>. Source: {s.source || 'Source not mentioned'}.{s.comments ? ` ${s.comments}` : ''}</p>
        )}
    </>
);

const MaterialSection = ({ s }) => (
    <>
        <p className="intro">{s.intro}</p>
        {s.included.length > 0 && (
            <SectionedTable
                tableNo={s.incNo} caption="Materials Included in Carbon Emissions Calculation"
                headers={['Material', { label: 'Quantity', align: 'num' }, { label: 'Unit', align: 'ctr' }, { label: 'Conversion Factor', align: 'num' }, { label: 'Emission Factor', align: 'num' }, { label: 'Emission Factor Unit', align: 'ctr' }, { label: 'Total (kgCO₂e)', align: 'num' }]}
                sections={s.included}
                renderRow={(r) => [<td key="m">{r.material}</td>, num(r.quantity, 'q'), ctr(r.unit, 'u'), num(r.cf, 'c'), num(r.ef, 'e'), ctr(r.efUnit || EMDASH, 'eu'), num(r.total, 't')]}
            />
        )}
        {s.excluded.length > 0 && (
            <SectionedTable
                tableNo={s.excNo} caption="Materials Excluded from Carbon Emissions Calculation"
                headers={['Material', { label: 'Exclusion Reason', align: 'num' }]}
                sections={s.excluded}
                renderRow={(r) => [<td key="m">{r.material}</td>, num(r.reason, 'r')]}
            />
        )}
        {!s.included.length && !s.excluded.length && <p className="empty">No material emission data entered.</p>}
        <Notes notes={s.notes} />
    </>
);

const TransportSection = ({ s }) => (
    <>
        <p className="intro">{s.intro}</p>
        {s.deliveries.length === 0 && <p className="empty">No transport deliveries recorded.</p>}
        {s.deliveries.length > 0 && (
            <figure className="table" id={`table-${s.summaryNo}`}>
                <Caption kind="Table" no={s.summaryNo} text="Transport Emissions — Summary by Vehicle" />
                <table className="compact">
                    <thead><tr><th>Delivery</th><th>Vehicle</th><th>From-To</th><th className="num">Distance (km)</th><th className="num">Capacity (t)</th><th className="num">Gross Wt (t)</th><th className="num">Emission Factor</th><th className="num">Total Emissions (kgCO₂e)</th></tr></thead>
                    <tbody>
                        {s.deliveries.map((d) => (
                            <tr key={d.index}><td>{d.summary.delivery}</td><td>{d.summary.vehicle}</td><td>{d.summary.origin}</td>{num(d.summary.distance, 'd')}{num(d.summary.capacity, 'c')}{num(d.summary.gross, 'g')}{num(d.summary.ef, 'e')}{num(d.summary.total, 't')}</tr>
                        ))}
                    </tbody>
                </table>
            </figure>
        )}
        {s.deliveries.map((d) => (
            <figure className="table long" key={d.index} id={`table-${d.tableNo}`}>
                <Caption kind="Table" no={d.tableNo} text={d.caption} />
                <table className="compact">
                    <thead><tr><th>Material</th><th>Category</th><th className="num">(kg) Conversion Factor</th><th className="num">Quantity (kg)</th><th className="num">Trips</th><th className="num">Emissions (kgCO₂e)</th></tr></thead>
                    <tbody>
                        {d.rows.map((r, i) => <tr key={i}><td>{r.material}</td><td>{r.category}</td>{num(r.cf, 'c')}{num(r.qtyKg, 'q')}{num(r.trips, 't')}{num(r.emissions, 'e')}</tr>)}
                    </tbody>
                </table>
            </figure>
        ))}
        <Notes notes={s.notes} />
    </>
);

const MachinerySection = ({ s }) => (
    <>
        <p className="intro">{s.intro}</p>
        {s.mode === 'lumpsum' ? (
            <>
                <p>Machinery and equipment emissions have been entered as a lump sum. The total on-site carbon emissions amount to <b>{s.total} kgCO₂e</b>, comprising contributions from electricity consumption and fuel usage as detailed below.</p>
                <SimpleRowsTable tableNo={s.tableNo} caption={s.caption} headers={['Source', 'Consumption / Day', 'Days', 'Emission Factor (kgCO₂e/unit)', 'Emissions (kgCO₂e)']}
                    rows={s.rows.map((r) => [r.source, r.consumption, r.days, r.ef, r.emissions])} />
            </>
        ) : (
            <figure className="table long" id={`table-${s.tableNo}`}>
                <Caption kind="Table" no={s.tableNo} text={s.caption} />
                <table className="compact wide">
                    <thead><tr><th>Equipment Name</th><th>Energy Source</th><th className="num">Fuel / Power Rating</th><th className="num">Avg Hrs / Day</th><th className="num">No. of Days</th><th className="num">Emission Factor (kgCO₂e/unit)</th><th className="num">Consumption</th><th className="num">Emissions (kgCO₂e)</th></tr></thead>
                    <tbody>
                        {s.rows.map((r, i) => <tr key={i}><td>{r.name}</td><td>{r.source}</td>{num(r.rate, 'r')}{num(r.hrs, 'h')}{num(r.days, 'd')}{num(r.ef, 'e')}{num(r.consumption, 'c')}{num(r.emissions, 'm')}</tr>)}
                    </tbody>
                </table>
            </figure>
        )}
        <Notes notes={s.notes} />
    </>
);

const RecyclingSection = ({ s }) => (
    <>
        {s.included.length > 0 && (
            <SectionedTable
                tableNo={s.incNo} caption="Materials Included in Recyclability Calculation"
                headers={['Material', { label: 'Recyclability %', align: 'num' }, { label: 'Recyclable Quantity', align: 'num' }, { label: 'Unit', align: 'ctr' }, { label: `Scrap Rate (${s.currency})`, align: 'num' }, { label: `Recovered Value (${s.currency})`, align: 'num' }]}
                sections={s.included}
                renderRow={(r) => [<td key="m">{r.material}</td>, num(r.pct, 'p'), num(r.recQty, 'q'), ctr(r.unit, 'u'), num(r.scrap, 's'), num(r.recovered, 'v')]}
            />
        )}
        {s.excluded.length > 0 && (
            <SectionedTable
                tableNo={s.excNo} caption="Materials Excluded from Recyclability Calculation"
                headers={['Material', { label: 'Reason', align: 'num' }]}
                sections={s.excluded}
                renderRow={(r) => [<td key="m">{r.material}</td>, num(r.reason, 'r')]}
            />
        )}
        {!s.included.length && !s.excluded.length && <p className="empty">No recycling data entered.</p>}
        <Notes notes={s.notes} />
    </>
);

const ResultsSection = ({ r }) => {
    if (!r || r.empty) return <p className="empty">No calculated LCCA results available. Run the calculation on the Results page and reopen the report.</p>;
    return (
        <>
            <p className="intro">{r.intro}</p>
            <figure className="table long" id={`table-${r.tableNo}`}>
                <Caption kind="Table" no={r.tableNo} text={r.caption} />
                <table className="compact">
                    <thead><tr><th>Description</th><th className="num">Present Value ({r.currency})</th></tr></thead>
                    <tbody>
                        {r.table.blocks.map((block, bi) => (
                            <Fragment key={bi}>
                                <tr className={`group${bi ? ' sep' : ''}`}><td colSpan={2}>{block.title}</td></tr>
                                {block.items.map((item, ii) => (item.subgroup
                                    ? <tr key={ii} className="subgroup"><td colSpan={2}>{item.subgroup}</td></tr>
                                    : <tr key={ii} className="item"><td>{item.label}</td>{num(item.value, 'v')}</tr>))}
                                <tr className="total"><td>Stage Total — {block.title}</td>{num(block.total, 't')}</tr>
                            </Fragment>
                        ))}
                        <tr className="grand"><td>Total life cycle cost</td>{num(r.table.grandTotal, 'g')}</tr>
                    </tbody>
                </table>
            </figure>
            <p>{r.figuresIntro}</p>
            {r.figures.map((f) => {
                const Chart = FIGURE_COMPONENTS[f.key];
                return (
                    <figure className="fig" key={f.key} id={`figure-${f.figureNo}`}>
                        <div className="chart"><Chart results={r.rawResults} currency={r.currency} /></div>
                        <Caption kind="Figure" no={f.figureNo} text={f.caption} />
                    </figure>
                );
            })}
        </>
    );
};

const SummarySection = ({ summary }) => (
    <>
        <p>{SUMMARY_LEAD}</p>
        <p>
            The most contributing stage of the life cycle is <b>{summary?.stageLabel || '________'}</b> contributing to around <b>{summary?.stagePct ? `${summary.stagePct}%` : '____%'}</b> of the total life cycle cost.
        </p>
        <p>
            The most contributing pillar is <b>{summary?.pillarLabel || '________'}</b> contributing to around <b>{summary?.pillarPct ? `${summary.pillarPct}%` : '____%'}</b> of the total life cycle cost.
        </p>
    </>
);

const AppendixA = () => (
    <section className="appendix page-break" id="appendix-a">
        <h2>{APPENDIX_A.title}</h2>
        <p>{APPENDIX_A.intro}</p>
        <ul>
            {APPENDIX_A.items.map((item, i) => (
                <li key={i}>
                    {item.bold ? (
                        <>{item.text.split(item.bold)[0]}<b>{item.bold}</b>{item.text.split(item.bold)[1]}</>
                    ) : item.text}
                    {item.children && <ul>{item.children.map((c, j) => <li key={j}>{c}</li>)}</ul>}
                </li>
            ))}
        </ul>
    </section>
);

/** Groups consecutive `li` blocks into one list; everything else renders in order. */
const AppendixB = () => {
    const out = [];
    let listBuffer = [];
    const flush = () => {
        if (listBuffer.length) {
            out.push(<ul key={`ul-${out.length}`}>{listBuffer.map((b, i) => <li key={i}>{b.text}</li>)}</ul>);
            listBuffer = [];
        }
    };
    APPENDIX_B.blocks.forEach((block, i) => {
        if (block.type === 'li') {
            listBuffer.push(block);
            return;
        }
        // An equation directly after a bullet belongs to that bullet: keep the
        // list open so the equation appears under its item.
        if (block.type === 'eq' && listBuffer.length) {
            const last = listBuffer[listBuffer.length - 1];
            out.push(<ul key={`ul-${i}`}>{listBuffer.slice(0, -1).map((b, j) => <li key={j}>{b.text}</li>)}<li>{last.text}<Equation tex={block.tex} /></li></ul>);
            listBuffer = [];
            return;
        }
        flush();
        switch (block.type) {
            case 'h3': out.push(<h3 key={i}>{block.text}</h3>); break;
            case 'h4': out.push(<h4 key={i}>{block.text}</h4>); break;
            case 'p': out.push(<p key={i}>{block.bold ? <b>{block.text}</b> : block.text}</p>); break;
            case 'eq': out.push(<Equation key={i} tex={block.tex} />); break;
            case 'note': out.push(<p key={i} className="eq-note">{block.text}</p>); break;
            case 'warn': out.push(<p key={i} className="eq-warn">{block.text}</p>); break;
            case 'table':
                out.push(
                    <figure className="table" key={i}>
                        <figcaption><i>{block.caption}</i></figcaption>
                        <table className="grid compact">
                            <tbody>
                                {block.rows.map(([label, tex], ri) => (
                                    <tr key={ri}><td style={{ width: '22%' }}>{label}</td><td><Equation tex={tex} inline /></td></tr>
                                ))}
                            </tbody>
                        </table>
                    </figure>,
                );
                break;
            default: break;
        }
    });
    flush();
    return (
        <section className="appendix page-break" id="appendix-b">
            <h2>{APPENDIX_B.title}</h2>
            <p>{APPENDIX_B.intro}</p>
            <ul className="glossary">
                {APPENDIX_B_GLOSSARY.map(([sym, meaning], i) => <li key={i}><Equation tex={sym} inline /> = {meaning}</li>)}
            </ul>
            {out}
        </section>
    );
};

const AppendixC = ({ a }) => (
    <section className="appendix landscape-page" id="appendix-c">
        <h2>{a.title}</h2>
        <figure className="table long">
            <figcaption><b>Table C-1.</b> WPI Adjustment Factors — Combined. All values in {a.currency}.</figcaption>
            <div style={{ overflowX: 'auto' }}>
                <table className="tiny">
                    <thead><tr>{a.wpi.columns.map((c, i) => <th key={i} className={i ? 'num' : ''}>{c}</th>)}</tr></thead>
                    <tbody>
                        {a.wpi.sections.map((s, si) => (
                            <Fragment key={si}>
                                <tr className={`group${si ? ' sep' : ''}`}><td colSpan={a.wpi.columns.length}>{s.header}</td></tr>
                                {s.rows.map((r, ri) => <tr key={ri}>{r.map((c, ci) => (ci ? num(c, ci) : <td key={ci}>{c}</td>))}</tr>)}
                            </Fragment>
                        ))}
                    </tbody>
                </table>
            </div>
        </figure>
    </section>
);

/* ── Section dispatcher ──────────────────────────────────────────────────── */

const InputSection = ({ s }) => {
    switch (s.kind) {
        case 'fields': return <><p className="intro">{s.intro}</p><FieldsTable {...s} /></>;
        case 'construction': return <ConstructionSection section={s} />;
        case 'global-traffic': return <GlobalTraffic s={s} />;
        case 'adt': return <><p className="intro">{s.intro}</p><SimpleRowsTable tableNo={s.tableNo} caption={s.caption} headers={['Vehicle Type', 'Vehicles / Day', 'Accident (% of vehicles)', 'PWR']} rows={s.rows} /></>;
        case 'diversion': return <><p className="intro">{s.intro}</p><SimpleRowsTable tableNo={s.tableNo} caption={s.caption} headers={['Vehicle Type', 'Vehicles / Day', 'Factor (kg/veh-km)', 'Emissions (kg/day)']} rows={s.rows} totalRow={['Total Daily Emissions', '', '', s.total]} /><Notes notes={s.notes} /></>;
        case 'diversion-direct': return <><p>The total traffic diversion emissions, entered directly, amount to <b>{s.total} kgCO₂e/day</b>.{s.source ? ` This estimate is based on ${s.source}.` : ' Source not mentioned.'}{s.comments ? ` ${s.comments}` : ''}</p><Notes notes={s.notes} /></>;
        case 'peak': return <><p className="intro">{s.intro}</p><SimpleRowsTable tableNo={s.tableNo} caption={s.caption} headers={['Hour', 'Traffic Proportion (%)']} rows={s.rows} /></>;
        case 'scc-ricke': case 'scc-custom': return <SccSection s={s} />;
        case 'material': return <MaterialSection s={s} />;
        case 'transport': return <TransportSection s={s} />;
        case 'machinery': return <MachinerySection s={s} />;
        case 'recycling': return <RecyclingSection s={s} />;
        default: return null;
    }
};

/** Section numbering: 1 Introduction · 2 Input data (2.x, 2.x.y) · 3 Results · 4 Summary. */
const numberSections = (doc) => {
    const toc = [];
    let n = 0;
    const numbered = { intro: null, input: null, results: null, summary: null };
    if (doc.introduction) { n += 1; numbered.intro = String(n); toc.push({ id: 'introduction', number: numbered.intro, title: 'Introduction to Life Cycle Cost Assessment', level: 1 }); }
    if (doc.inputSections.length) {
        n += 1; numbered.input = String(n);
        toc.push({ id: 'input-data', number: numbered.input, title: 'Input data', level: 1 });
        doc.inputSections.forEach((s, i) => {
            const sub = `${n}.${i + 1}`;
            toc.push({ id: s.id, number: sub, title: s.title, level: 2 });
            if (s.kind === 'group') {
                s.children.forEach((c, j) => toc.push({ id: c.id, number: `${sub}.${j + 1}`, title: c.title, level: 3 }));
            }
        });
    }
    if (doc.results) { n += 1; numbered.results = String(n); toc.push({ id: 'lcca-results', number: numbered.results, title: 'LCCA results', level: 1 }); }
    n += 1; numbered.summary = String(n); toc.push({ id: 'summary', number: numbered.summary, title: 'Summary and conclusions', level: 1 });
    doc.appendices.forEach((a) => toc.push({ id: a.id, number: '', title: a.kind === 'appendix-a' ? APPENDIX_A.title : a.kind === 'appendix-b' ? APPENDIX_B.title : a.title, level: 1 }));
    return { toc, numbered };
};

const initialPaged = () => {
    try {
        return new URLSearchParams(window.location.search).get('paged') !== '0';
    } catch {
        return true;
    }
};

/* ── Page ────────────────────────────────────────────────────────────────── */

const ReportPage = ({ projectId, projectData }) => {
    const [selections, setSelections] = useState({});
    const [showSections, setShowSections] = useState(false);
    const [paged, setPaged] = useState(initialPaged);
    const [pagedState, setPagedState] = useState({ status: 'idle', total: 0, ms: 0 });
    const sourceRef = useRef(null);
    const pagesRef = useRef(null);

    const results = projectData?.outputs_data?.results || null;
    const currency = projectData?.general_info?.project_currency || projectData?.currency || 'INR';

    const doc = useMemo(
        () => buildReportDocument(projectData, { results, currency, selections }),
        [projectData, results, currency, selections],
    );
    const { toc, numbered } = useMemo(() => numberSections(doc), [doc]);

    // Chrome/Edge use the document title as the default "Save as PDF" file name.
    useEffect(() => {
        const previous = document.title;
        document.title = reportFileStem(doc.meta.projectName);
        return () => { document.title = previous; };
    }, [doc.meta.projectName]);

    // Page preview: lay the (already rendered) article out into A4 pages.
    useEffect(() => {
        if (!paged || !sourceRef.current || !pagesRef.current) return undefined;
        let cancelled = false;
        setPagedState({ status: 'working', total: 0, ms: 0 });
        const started = performance.now();
        const clone = sourceRef.current.cloneNode(true);
        clone.classList.remove('source');
        paginate({ html: clone.outerHTML, container: pagesRef.current })
            .then(({ total }) => { if (!cancelled) setPagedState({ status: 'ready', total, ms: Math.round(performance.now() - started) }); })
            .catch((error) => { if (!cancelled) setPagedState({ status: 'error', total: 0, ms: 0, error: error?.message || String(error) }); });
        return () => { cancelled = true; teardown(); };
    }, [paged, doc]);

    const inputNumber = (i) => `${numbered.input}.${i + 1}`;
    const firstMainId = doc.introduction ? 'introduction' : doc.inputSections.length ? 'input-data' : doc.results ? 'lcca-results' : 'summary';
    const mainClass = (id, extra = '') => `${extra}${id === firstMainId ? ' main-start' : ''}`.trim();

    return (
        <div className={`lcca-report-shell${paged ? ' is-paged' : ''}`} data-paged-ready={paged && pagedState.status === 'ready' ? 'true' : 'false'}>
            <div className="lcca-report-toolbar">
                <Link className="btn-like" to={`/project/${projectId}/Results`}>← Back to Results</Link>
                <button type="button" onClick={() => setShowSections(true)}>Sections…</button>
                {paged ? (
                    <>
                        <button type="button" onClick={() => setPaged(false)}>Continuous view</button>
                        <span className="hint">
                            {pagedState.status === 'working' && 'Laying out pages…'}
                            {pagedState.status === 'ready' && `${pagedState.total} pages · laid out in ${(pagedState.ms / 1000).toFixed(1)} s`}
                            {pagedState.status === 'error' && `Page layout failed: ${pagedState.error}`}
                        </span>
                        <span className="spacer" />
                        <span className="hint">Choose “Save as PDF” in the print dialog</span>
                        <button type="button" className="primary" disabled={pagedState.status !== 'ready'} onClick={() => window.print()}>Print / Save as PDF</button>
                    </>
                ) : (
                    <>
                        <span className="hint">
                            {doc.meta.hasResults ? `${doc.tables.length} tables · ${doc.figures.length} figures` : 'No calculation results yet — input sections only'}
                        </span>
                        <span className="spacer" />
                        <button type="button" className="primary" onClick={() => setPaged(true)}>Page preview / Print</button>
                    </>
                )}
            </div>

            <ReportSectionModal show={showSections} onHide={() => setShowSections(false)} onConfirm={(next) => { setSelections(next); setShowSections(false); }} />

            {paged && (
                <div className="lcca-paged">
                    {pagedState.status !== 'ready' && (
                        <div className="lcca-paged-status">
                            {pagedState.status === 'error' ? `Page layout failed: ${pagedState.error}` : 'Laying out pages…'}
                        </div>
                    )}
                    <div ref={pagesRef} />
                </div>
            )}

            <article ref={sourceRef} className="lcca-report source" data-testid="lcca-html-report">
                {doc.titlePage && <TitlePage page={doc.titlePage} currency={doc.meta.currency} />}

                <Toc entries={toc} tables={doc.tables} figures={doc.figures} runningTitle={doc.titlePage ? null : doc.meta.projectName} />

                {doc.introduction && (
                    <section id="introduction" className={mainClass('introduction')}>
                        <h2><span className="num">{numbered.intro}</span>Introduction to Life Cycle Cost Assessment</h2>
                        <p>{INTRODUCTION}</p>
                        <figure className="fig" id={`figure-${doc.introduction.figureNo}`}>
                            <img src={asset(FRAMEWORK_FIGURE.src)} alt={FRAMEWORK_FIGURE.caption} />
                            <Caption kind="Figure" no={doc.introduction.figureNo} text={FRAMEWORK_FIGURE.caption} />
                        </figure>
                    </section>
                )}

                {doc.inputSections.length > 0 && (
                    <section id="input-data" className={mainClass('input-data', 'page-break')}>
                        <h2><span className="num">{numbered.input}</span>Input data</h2>
                        {doc.inputSections.map((s, i) => (
                            <section key={s.id} id={s.id}>
                                <h3><span className="num">{inputNumber(i)}</span>{s.title}</h3>
                                {s.kind === 'group'
                                    ? s.children.map((c, j) => (
                                        <section key={c.id} id={c.id}>
                                            <h4><span className="num">{inputNumber(i)}.{j + 1}</span>{c.title}</h4>
                                            <InputSection s={c} />
                                        </section>
                                    ))
                                    : <InputSection s={s} />}
                            </section>
                        ))}
                    </section>
                )}

                {doc.results && (
                    <section id="lcca-results" className={mainClass('lcca-results', 'page-break')}>
                        <h2><span className="num">{numbered.results}</span>LCCA results</h2>
                        <h3><span className="num">{numbered.results}.1</span>Life cycle cost results</h3>
                        <ResultsSection r={doc.results} />
                    </section>
                )}

                <section id="summary" className={mainClass('summary', 'page-break')}>
                    <h2><span className="num">{numbered.summary}</span>Summary and conclusions</h2>
                    <SummarySection summary={doc.summary} />
                </section>

                {doc.appendices.map((a) => {
                    if (a.kind === 'appendix-a') return <AppendixA key={a.id} />;
                    if (a.kind === 'appendix-b') return <AppendixB key={a.id} />;
                    if (a.kind === 'appendix-c') return <AppendixC key={a.id} a={a} />;
                    return null;
                })}
            </article>
        </div>
    );
};

export default ReportPage;
