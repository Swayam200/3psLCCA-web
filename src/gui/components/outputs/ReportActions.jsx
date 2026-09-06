/**
 * Report buttons on the Results page.
 *
 * Primary: the standard report (instant web page → print to PDF). Under
 * "Advanced" (collapsed by default): the desktop-identical LaTeX PDF, which
 * is off until the user enables it — here or in Settings → Reports — and can
 * then also be made the primary button. An ⓘ popover explains the choice in
 * plain language.
 */
import { useState } from 'react';
import { Button, Collapse, Form, OverlayTrigger, Popover } from 'react-bootstrap';
import { FaChevronDown, FaChevronRight, FaInfoCircle } from 'react-icons/fa';
import { useReportPreferences } from '../../hooks/useReportPreferences.js';
import { REPORT_LATEX, effectivePrimaryReport, deviceMemoryGb, isLowMemoryDevice } from '../../../utils/reportPreferences.js';

const REPORT_INFO = {
    title: 'Which report should I use?',
    standard: 'Standard report (recommended): opens in the browser as numbered A4 pages within a few seconds, ready to read on screen or save as PDF. Nothing to download; works on any laptop.',
    desktop: 'Desktop-identical PDF: runs the desktop application’s own LaTeX typesetting inside the browser. The layout matches the desktop program page for page, but it downloads about 60 MB the first time, takes 10–20 seconds per report and needs a capable computer (8 GB of memory or more).',
    same: 'Both reports contain the same sections, tables and numbers. Only the typesetting differs.',
};

const InfoPopover = (
    <Popover id="report-info-popover" style={{ maxWidth: 380 }}>
        <Popover.Header as="h6">{REPORT_INFO.title}</Popover.Header>
        <Popover.Body style={{ fontSize: '0.85rem' }}>
            <p className="mb-2"><b>Standard report</b> — {REPORT_INFO.standard.replace(/^Standard report \(recommended\): /, '')}</p>
            <p className="mb-2"><b>Desktop-identical PDF</b> — {REPORT_INFO.desktop.replace(/^Desktop-identical PDF: /, '')}</p>
            <p className="mb-0">{REPORT_INFO.same}</p>
        </Popover.Body>
    </Popover>
);

const primaryStyle = { backgroundColor: 'var(--app-primary-accent)', border: 'none', color: '#1e1e28', fontWeight: 600 };
const outlineStyle = { borderColor: 'var(--app-primary-accent)', color: 'var(--app-primary-accent)', fontWeight: 600 };

const ReportActions = ({ onViewReport, onGenerateDesktopPdf, isGeneratingPdf }) => {
    const [prefs, update] = useReportPreferences();
    const [advancedOpen, setAdvancedOpen] = useState(false);
    const latexPrimary = effectivePrimaryReport(prefs) === REPORT_LATEX;
    const lowMemory = isLowMemoryDevice();
    const memoryGb = deviceMemoryGb();

    const desktopButton = (variant) => (
        <Button
            variant={variant}
            onClick={onGenerateDesktopPdf}
            disabled={isGeneratingPdf}
            style={{ ...(variant === 'outline-primary' ? outlineStyle : primaryStyle), opacity: isGeneratingPdf ? 0.6 : 1 }}
            data-testid="generate-latex-report"
        >
            {isGeneratingPdf
                ? <><span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" /> Generating…</>
                : 'Generate desktop-identical PDF'}
        </Button>
    );

    const standardButton = (variant) => (
        <Button
            variant={variant}
            onClick={onViewReport}
            style={variant === 'outline-primary' ? outlineStyle : primaryStyle}
            data-testid="view-html-report"
        >
            View Report
        </Button>
    );

    return (
        <div className="mb-4" data-testid="report-actions">
            <div className="d-flex flex-wrap gap-2 align-items-center">
                {latexPrimary ? desktopButton('primary') : standardButton('primary')}
                {latexPrimary && standardButton('outline-primary')}
                <OverlayTrigger trigger={['click', 'focus']} placement="right" overlay={InfoPopover} rootClose>
                    <button
                        type="button"
                        className="btn btn-link p-1"
                        aria-label="About the report options"
                        title="About the report options"
                        style={{ color: 'var(--app-text-secondary)', lineHeight: 1 }}
                        data-testid="report-info"
                    >
                        <FaInfoCircle size={18} />
                    </button>
                </OverlayTrigger>
            </div>

            <button
                type="button"
                className="btn btn-link p-0 mt-2 d-inline-flex align-items-center gap-1"
                onClick={() => setAdvancedOpen((open) => !open)}
                aria-expanded={advancedOpen}
                aria-controls="report-advanced"
                style={{ color: 'var(--app-text-secondary)', fontSize: '0.85rem', textDecoration: 'none' }}
                data-testid="report-advanced-toggle"
            >
                {advancedOpen ? <FaChevronDown size={11} /> : <FaChevronRight size={11} />} Advanced
            </button>

            <Collapse in={advancedOpen}>
                <div id="report-advanced">
                    <div
                        className="mt-2 p-3 rounded"
                        style={{ border: '1px solid var(--app-border-mid)', backgroundColor: 'var(--app-bg-card)', maxWidth: 640, fontSize: '0.88rem' }}
                    >
                        <div className="fw-bold mb-1" style={{ color: 'var(--app-text-primary)' }}>Desktop-identical PDF (LaTeX)</div>
                        <div className="mb-2" style={{ color: 'var(--app-text-secondary)' }}>
                            Same numbers as the standard report, typeset exactly like the desktop program. First use downloads about 60 MB;
                            each report takes 10–20 s and a lot of memory.
                        </div>
                        {lowMemory && (
                            <div className="mb-2" style={{ color: 'var(--bs-warning, #b45309)' }} data-testid="report-low-memory">
                                This computer reports {memoryGb} GB of memory. The desktop PDF may be very slow or fail here; the standard report is recommended.
                            </div>
                        )}
                        <Form.Check
                            type="switch"
                            id="report-desktop-pdf-enabled"
                            label="Enable the desktop-identical PDF"
                            checked={prefs.desktopPdfEnabled}
                            onChange={(event) => update({ desktopPdfEnabled: event.target.checked })}
                            data-testid="report-desktop-pdf-enabled"
                        />
                        <Form.Check
                            type="switch"
                            id="report-desktop-pdf-primary"
                            className="mb-2"
                            label="Make it the main report button"
                            checked={latexPrimary}
                            disabled={!prefs.desktopPdfEnabled}
                            onChange={(event) => update({ primaryReport: event.target.checked ? REPORT_LATEX : 'html' })}
                            data-testid="report-desktop-pdf-primary"
                        />
                        {prefs.desktopPdfEnabled && !latexPrimary && desktopButton('outline-primary')}
                        <div className="mt-2" style={{ color: 'var(--app-text-secondary)', fontSize: '0.8rem' }}>
                            These choices are remembered on this computer; they are also in Settings → Reports.
                        </div>
                    </div>
                </div>
            </Collapse>
        </div>
    );
};

export default ReportActions;
