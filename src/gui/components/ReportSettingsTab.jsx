/**
 * Settings → Reports: choose which report the Results page offers.
 * Changes apply immediately (they are stored per browser).
 */
import { Form } from 'react-bootstrap';
import { useReportPreferences } from '../hooks/useReportPreferences.js';
import { REPORT_HTML, REPORT_LATEX, effectivePrimaryReport, deviceMemoryGb, isLowMemoryDevice } from '../../utils/reportPreferences.js';

const ReportSettingsTab = ({ theme }) => {
    const [prefs, update] = useReportPreferences();
    const latexPrimary = effectivePrimaryReport(prefs) === REPORT_LATEX;
    const lowMemory = isLowMemoryDevice();
    const memoryGb = deviceMemoryGb();
    const muted = { fontSize: '13px', color: theme.textSecondary };

    return (
        <div style={{ border: `1px solid ${theme.border}`, padding: '20px', borderRadius: '4px', backgroundColor: theme.bgCard }}>
            <p style={{ ...muted, marginBottom: '16px' }}>
                Two ways to produce the project report. Both contain the same sections, tables and numbers.
            </p>

            <div className="mb-3">
                <div className="fw-bold">Standard report <span style={{ ...muted, fontWeight: 400 }}>(recommended, always available)</span></div>
                <div style={muted}>
                    Opens in the browser as numbered A4 pages within a few seconds; save it as PDF from the browser. Nothing to download; works on any laptop.
                </div>
            </div>

            <div className="mb-3">
                <div className="fw-bold">Desktop-identical PDF (LaTeX)</div>
                <div style={muted}>
                    Runs the desktop application’s own typesetting inside the browser, so the PDF matches the desktop program page for
                    page. Downloads about 60 MB the first time, takes 10–20 seconds per report and needs a capable computer
                    (8 GB of memory or more).
                </div>
                {lowMemory && (
                    <div className="mt-1" style={{ fontSize: '13px', color: '#b45309' }} data-testid="settings-low-memory">
                        This computer reports {memoryGb} GB of memory — the desktop PDF may be very slow or fail here.
                    </div>
                )}
            </div>

            <Form.Check
                type="switch"
                id="settings-desktop-pdf-enabled"
                className="mb-2"
                label="Show the desktop-identical PDF option (under “Advanced” on the Results page)"
                checked={prefs.desktopPdfEnabled}
                onChange={(event) => update({ desktopPdfEnabled: event.target.checked })}
                data-testid="settings-desktop-pdf-enabled"
            />

            <fieldset disabled={!prefs.desktopPdfEnabled} className="mb-2">
                <div className="fw-bold mb-1" style={{ fontSize: '13px' }}>Main report button on the Results page</div>
                <Form.Check
                    type="radio"
                    name="settings-primary-report"
                    id="settings-primary-html"
                    label="Standard report"
                    checked={!latexPrimary}
                    onChange={() => update({ primaryReport: REPORT_HTML })}
                />
                <Form.Check
                    type="radio"
                    name="settings-primary-report"
                    id="settings-primary-latex"
                    label="Desktop-identical PDF (the standard report stays one click away)"
                    checked={latexPrimary}
                    onChange={() => update({ primaryReport: REPORT_LATEX })}
                    data-testid="settings-primary-latex"
                />
            </fieldset>

            <div style={{ fontSize: '11px', color: theme.textSecondary, marginTop: '16px' }}>
                Report choices apply immediately and are remembered on this computer.
            </div>
        </div>
    );
};

export default ReportSettingsTab;
