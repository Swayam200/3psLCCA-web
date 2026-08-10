/**
 * The 3psLCCA logo, rebuilt as vectors so it can animate.
 *
 * The shipped logo (public/logo-3pslcca.svg) is a raster: three overlapping
 * circles — orange, green, purple, one per pillar — with the region where all
 * three meet punched out. Geometry and colors here were measured from that
 * bitmap: centers 120° apart at distance 23 from the centroid, radius 28
 * (viewBox 104), draw order green → orange → purple, and the punched center
 * expressed as a mask of three r=28 arcs between the pairwise intersection
 * points nearest the centroid.
 *
 * Animation hooks are class names only (styles live in AiFab.jsx):
 *   .aifab-c-orange / -green / -purple  — the circles (hover separation)
 *   .aifab-mark                          — the whole mark (orbit spin)
 */
import { useId } from 'react';
import { LOGO_COLORS } from './routePills.js';

export default function AiLogoMark({ size = 30 }) {
    const maskId = useId();
    return (
        <svg
            className="aifab-mark"
            width={size}
            height={size}
            viewBox="0 0 104 104"
            aria-hidden="true"
            focusable="false"
        >
            <mask id={maskId}>
                <rect width="104" height="104" fill="#fff" />
                {/* The punched center: arcs of the orange, purple, green circles. */}
                <path
                    d="M 56.1 59.1 A 28 28 0 0 0 56.1 44.9 A 28 28 0 0 0 43.8 52 A 28 28 0 0 0 56.1 59.1 Z"
                    fill="#000"
                />
            </mask>
            <g mask={`url(#${maskId})`}>
                <circle className="aifab-c-green" cx="63.5" cy="32.1" r="28" fill={LOGO_COLORS.green} />
                <circle className="aifab-c-orange" cx="29" cy="52" r="28" fill={LOGO_COLORS.orange} />
                <circle className="aifab-c-purple" cx="63.5" cy="71.9" r="28" fill={LOGO_COLORS.purple} />
            </g>
        </svg>
    );
}
