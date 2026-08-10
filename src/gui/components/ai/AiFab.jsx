/**
 * The floating assistant: a launcher built from the 3psLCCA logo, anchored
 * bottom-right on every project page, opening a corner sheet that hosts the
 * conversation (docs/ai-integration-plan.md §3.5).
 *
 * Loaded ONLY via dynamic import gated on VITE_AI_ENABLED (see
 * ProjectLayout.jsx) — this file and everything it imports stays out of
 * flag-off bundles.
 *
 * The logo's three circles are the state display:
 *   idle      — gentle breathing pulse
 *   hover     — the circles separate slightly, the logo "opens"
 *   thinking  — the mark orbits its own center (the spinner IS the brand)
 *   answered  — one ring pulse + a badge dot tinted by the tier that answered
 * All pure CSS/SVG; `prefers-reduced-motion` turns every animation off.
 */
import { useEffect, useRef, useState } from 'react';
import AiLogoMark from './AiLogoMark.jsx';
import AiConversation from './AiConversation.jsx';
import useAiAssistant from './useAiAssistant.js';
import { onAssistantOpen } from './assistantBus.js';
import { chipsForPage } from './pageChips.js';
import { tierColor, TIER_COLORS } from './routePills.js';

const FAB_CSS = `
.aifab-btn {
    position: fixed; right: 22px; bottom: 22px; z-index: 1040;
    width: 56px; height: 56px; border-radius: 50%; padding: 0;
    border: 1px solid var(--app-border-mid);
    background: var(--app-bg-card);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18);
    display: flex; align-items: center; justify-content: center;
    cursor: pointer;
    transition: transform 0.18s ease, box-shadow 0.18s ease;
}
.aifab-btn:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0, 0, 0, 0.22); }
.aifab-btn:focus-visible { outline: 2px solid var(--app-primary-accent); outline-offset: 2px; }
.aifab-mark-wrap { display: inline-flex; animation: aifab-breathe 4s ease-in-out infinite; }
.aifab-mark circle { transition: transform 0.25s ease; }
.aifab-btn:hover .aifab-c-orange { transform: translate(-4px, 0); }
.aifab-btn:hover .aifab-c-green { transform: translate(2px, -3.5px); }
.aifab-btn:hover .aifab-c-purple { transform: translate(2px, 3.5px); }
.aifab-btn.aifab--thinking .aifab-mark { animation: aifab-orbit 1.1s linear infinite; transform-origin: 50% 50%; }
.aifab-btn.aifab--unread { animation: aifab-ping 0.9s cubic-bezier(0, 0, 0.2, 1) 1; }
.aifab-badge {
    position: absolute; top: 3px; right: 3px; width: 12px; height: 12px;
    border-radius: 50%; border: 2px solid var(--app-bg-card);
}
.aifab-hidden { display: none; }

.aifab-sheet {
    position: fixed; right: 20px; bottom: 90px; z-index: 1041;
    width: min(400px, calc(100vw - 32px));
    max-height: min(72vh, 640px);
    display: flex; flex-direction: column;
    background: var(--app-bg-card);
    border: 1px solid var(--app-border-mid);
    border-radius: 14px;
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.28);
    transform-origin: 100% 100%;
    transition: transform 0.2s cubic-bezier(0.3, 1.4, 0.5, 1), opacity 0.16s ease;
}
.aifab-sheet--closed { opacity: 0; transform: scale(0.86) translateY(10px); pointer-events: none; }
.aifab-sheet--open { opacity: 1; transform: scale(1) translateY(0); }
.aifab-sheet-body { overflow-y: auto; padding: 0 16px 14px; }
@media (max-width: 575.98px) {
    .aifab-sheet { right: 0; left: 0; bottom: 0; width: auto; border-radius: 14px 14px 0 0; max-height: 78vh; }
}

@keyframes aifab-breathe { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.06); } }
@keyframes aifab-orbit { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
@keyframes aifab-ping {
    0% { box-shadow: 0 0 0 0 rgba(158, 158, 255, 0.55), 0 4px 16px rgba(0, 0, 0, 0.18); }
    100% { box-shadow: 0 0 0 16px rgba(158, 158, 255, 0), 0 4px 16px rgba(0, 0, 0, 0.18); }
}

@media (prefers-reduced-motion: reduce) {
    .aifab-mark-wrap, .aifab-btn.aifab--unread, .aifab-btn.aifab--thinking .aifab-mark { animation: none; }
    .aifab-mark circle, .aifab-btn, .aifab-sheet { transition: none; }
}
`;

export default function AiFab({ activeNode }) {
    const assistant = useAiAssistant();
    const [open, setOpen] = useState(false);
    const [unread, setUnread] = useState(false);
    const [modalOpen, setModalOpen] = useState(false);
    const btnRef = useRef(null);
    const sheetRef = useRef(null);
    // Event handlers registered once (bus, body observer) read the latest
    // state/callbacks through refs, synced after every render.
    const openRef = useRef(open);
    const openSheetRef = useRef(() => {});
    const refreshStatusRef = useRef(() => {});

    const openSheet = () => { setOpen(true); setUnread(false); assistant.refreshStatus(); };
    useEffect(() => {
        openRef.current = open;
        openSheetRef.current = openSheet;
        refreshStatusRef.current = assistant.refreshStatus;
    });

    // Results-page cue (and any future affordance) asks us to open.
    useEffect(() => onAssistantOpen(() => openSheetRef.current()), []);

    // Hide while any Bootstrap modal is open (they toggle body.modal-open);
    // re-read prefs when one closes — Settings may have changed them.
    useEffect(() => {
        const update = () => {
            const isOpen = document.body.classList.contains('modal-open');
            setModalOpen((was) => {
                if (was && !isOpen) refreshStatusRef.current();
                return isOpen;
            });
        };
        const observer = new MutationObserver(update);
        observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
        update();
        return () => observer.disconnect();
    }, []);

    // Esc and outside-click close the sheet.
    useEffect(() => {
        if (!open) return undefined;
        const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
        const onPointer = (e) => {
            if (sheetRef.current?.contains(e.target) || btnRef.current?.contains(e.target)) return;
            setOpen(false);
        };
        document.addEventListener('keydown', onKey);
        document.addEventListener('pointerdown', onPointer);
        return () => {
            document.removeEventListener('keydown', onKey);
            document.removeEventListener('pointerdown', onPointer);
        };
    }, [open]);

    // An answer arriving while the sheet is closed earns the badge.
    const { outcome } = assistant;
    useEffect(() => {
        if (outcome && !openRef.current) setUnread(true);
    }, [outcome]);

    if (!assistant.enabled) return null;

    const { status, busy } = assistant;
    const badge = unread ? (tierColor(outcome?.route) || TIER_COLORS.encoder) : null;
    const hiddenClass = modalOpen ? ' aifab-hidden' : '';

    return (
        <>
            <style>{FAB_CSS}</style>

            <div
                ref={sheetRef}
                className={`aifab-sheet ${open ? 'aifab-sheet--open' : 'aifab-sheet--closed'}${hiddenClass}`}
                role="dialog"
                aria-label="AI assistant"
                aria-hidden={!open}
                data-testid="ai-sheet"
            >
                <div className="d-flex align-items-center justify-content-between px-3 py-2">
                    <span className="fw-bold" style={{ color: 'var(--app-text-primary)', fontSize: '0.95rem' }}>
                        AI Assistant
                        <span
                            className="ms-2 fw-normal"
                            style={{ fontSize: '0.75rem', color: 'var(--app-text-secondary)' }}
                        >
                            read-only · {status.degraded ? 'offline rules (no key)'
                                : status.mode === 'cascade' ? 'local cascade'
                                    : status.modeLabel.toLowerCase()}
                        </span>
                    </span>
                    <button
                        type="button"
                        onClick={() => setOpen(false)}
                        aria-label="Close assistant"
                        className="border-0 bg-transparent"
                        style={{ color: 'var(--app-text-secondary)', fontSize: '1.1rem', lineHeight: 1, cursor: 'pointer' }}
                    >
                        ×
                    </button>
                </div>
                <div className="aifab-sheet-body">
                    <AiConversation assistant={assistant} chips={chipsForPage(activeNode)} />
                </div>
            </div>

            <button
                ref={btnRef}
                type="button"
                onClick={() => (open ? setOpen(false) : openSheet())}
                aria-label={open ? 'Close AI assistant' : 'Open AI assistant'}
                aria-expanded={open}
                className={`aifab-btn${busy ? ' aifab--thinking' : ''}${unread && !open ? ' aifab--unread' : ''}${hiddenClass}`}
                data-testid="ai-fab"
            >
                <span className="aifab-mark-wrap"><AiLogoMark size={32} /></span>
                {badge && !open && <span className="aifab-badge" style={{ background: badge }} />}
            </button>
        </>
    );
}
