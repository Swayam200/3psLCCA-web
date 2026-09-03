import katex from 'katex';
import 'katex/dist/katex.min.css';

/**
 * Display-mode LaTeX equation rendered with KaTeX (no MathJax, no images).
 * Falls back to the raw TeX in a <code> block if the expression fails to
 * parse, so a typo can never blank the appendix.
 */
const Equation = ({ tex, inline = false }) => {
    let html;
    try {
        html = katex.renderToString(tex, {
            displayMode: !inline,
            throwOnError: true,
            strict: 'ignore',
        });
    } catch {
        return <code className="eq-fallback">{tex}</code>;
    }
    return inline
        ? <span className="eq-inline" dangerouslySetInnerHTML={{ __html: html }} />
        : <div className="eq" dangerouslySetInnerHTML={{ __html: html }} />;
};

export default Equation;
