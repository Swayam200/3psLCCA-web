/**
 * Paginate the report with Paged.js.
 *
 * Browsers only create pages at print time and give CSS no way to number
 * them. Paged.js lays the report out into real A4 page boxes in the DOM
 * (so page numbers, running headers and the contents list's page numbers
 * resolve), and the browser then prints those boxes 1:1.
 *
 * Everything (Paged.js itself, ~300 KB, and the stylesheets as text) loads
 * lazily the first time a page preview is requested.
 */

let queue = Promise.resolve();
let handlersRegistered = false;

/**
 * Print-time sheet sizes. Paged.js prints every page box on one sheet size
 * (its own `@page { size }`, appended to <head> after all other styles), so
 * the landscape appendix box would be cut to a portrait sheet. Chromium
 * honours per-box named pages, but only from a rule that comes after
 * Paged.js's — hence a stylesheet appended once pagination is done. The
 * box heights are also pinned: Paged.js prints them at 100% of the
 * (portrait) initial page, which spills a landscape box onto a blank page.
 */
const PRINT_SHEETS_ATTR = 'data-lcca-print-sheets';
const PRINT_SHEETS_CSS = `
@media print {
    @page landscape-sheet { size: A4 landscape; margin: 0; }
    .pagedjs_landscape-page_page { page: landscape-sheet; }
    .pagedjs_page {
        width: var(--pagedjs-pagebox-width) !important;
        height: var(--pagedjs-pagebox-height) !important;
        min-height: 0 !important;
        max-height: none !important;
    }
    .pagedjs_page .pagedjs_sheet {
        height: var(--pagedjs-pagebox-height) !important;
        min-height: 0 !important;
        max-height: none !important;
    }
}`;

const installPrintSheets = () => {
    document.querySelectorAll(`style[${PRINT_SHEETS_ATTR}]`).forEach((node) => node.remove());
    const style = document.createElement('style');
    style.setAttribute(PRINT_SHEETS_ATTR, '');
    style.textContent = PRINT_SHEETS_CSS;
    document.head.appendChild(style);
};

/**
 * Page numbering done by hand, after layout.
 *
 * Paged.js numbers pages with CSS counters: `counter-increment: page` on
 * every page box and `counter-reset: page N` on the boxes where the report
 * restarts numbering (contents → i, first body page → 1). Current Chromium
 * scopes such a reset to that one page box, so the next page carried on
 * from the old count (…, i, iii, 1, 4, 5, …) and target-counter() in the
 * contents list — which Paged.js evaluates by simulating those counters —
 * showed 0. Setting an explicit `counter-reset: page N` on every page box
 * is what the margin boxes' counter(page) actually honours, and the
 * contents list gets the same numbers written into it directly.
 */
const definePageNumbers = (Handler) => class PageNumbers extends Handler {
    afterRendered(pages) {
        const numbers = new Map();
        let number = 0;
        pages.forEach(({ element }) => {
            const reset = element.querySelector('[data-counter-page-reset]:not([data-split-from])');
            number = reset ? (parseInt(reset.dataset.counterPageReset, 10) || 1) : number + 1;
            element.style.counterIncrement = 'none';
            element.style.counterReset = `page ${number}`;
            element.dataset.reportPage = String(number);
            numbers.set(element, number);
        });

        const area = pages[0]?.element.parentElement;
        if (!area) return;
        area.querySelectorAll('.toc li .pg a[href^="#"]').forEach((link) => {
            const id = decodeURIComponent(link.getAttribute('href').slice(1));
            const target = area.querySelector(`#${CSS.escape(id)}`);
            const pageBox = target?.closest('.pagedjs_page');
            link.textContent = pageBox ? String(numbers.get(pageBox)) : '';
        });
    }
};

const run = async ({ html, container }) => {
    // report.paged.css is imported as raw text on purpose: it carries the
    // @page / string-set rules that only Paged.js understands, and must
    // reach it untouched by the CSS build pipeline.
    const [pagedjs, reportCss, pagedCss, katexCss] = await Promise.all([
        import('pagedjs'),
        import('./report.css?inline'),
        import('./report.paged.css?raw'),
        import('katex/dist/katex.min.css?inline'),
    ]);
    const { Previewer, Handler, registerHandlers } = pagedjs;

    if (!handlersRegistered) {
        registerHandlers(definePageNumbers(Handler));
        handlersRegistered = true;
    }

    // Fonts change line breaks; measure only once they are in.
    if (document.fonts?.ready) await document.fonts.ready;

    // A previous run leaves its generated stylesheet in <head>; drop it so
    // rules do not accumulate across re-paginations.
    document.querySelectorAll('style[data-pagedjs-inserted-styles]').forEach((node) => node.remove());
    container.innerHTML = '';

    const previewer = new Previewer();
    const flow = await previewer.preview(
        html,
        [
            { 'katex.css': katexCss.default },
            { 'report.css': reportCss.default },
            { 'report.paged.css': pagedCss.default },
        ],
        container,
    );
    installPrintSheets();
    return { total: flow.total };
};

/**
 * Remove what pagination added to <head>. Paged.js applies the report's
 * @media print rules on screen; left in place they would restyle the
 * continuous view after the user leaves the page preview.
 */
export const teardown = () => {
    document.querySelectorAll(`style[data-pagedjs-inserted-styles], style[${PRINT_SHEETS_ATTR}]`).forEach((node) => node.remove());
};

/**
 * @param {{ html: string, container: HTMLElement }} args
 *   html — the report article's outerHTML; container — where pages render.
 * @returns {Promise<{ total: number }>} page count
 */
export const paginate = (args) => {
    const job = queue.then(() => run(args));
    queue = job.catch(() => {});
    return job;
};
