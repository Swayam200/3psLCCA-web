"""
gui/components/outputs/helper_functions/ratio_helper.py

Helpers for calculating and formatting sustainability/life cycle ratios.
"""

def format_ratio_string(values: list, colors: list, sep_color: str, na_color: str) -> str:
    """
    Format a ratio string (e.g., '+1.0 : -0.5 : +2.3').
    - values: list of float values to normalize
    - colors: list of hex colors for the values
    - sep_color: color for the ':' separator
    - na_color: color for 'N/A' text
    """
    pos_vals = [v for v in values if v > 0]
    neg_vals = [v for v in values if v < 0]
    
    divisor = None
    if pos_vals:
        divisor = min(pos_vals)
    elif neg_vals:
        divisor = abs(max(neg_vals))

    if divisor and divisor != 0:
        normalized = [v / divisor for v in values]
        parts = []
        for val, color in zip(normalized, colors):
            parts.append(f"<b style='color:{color}'>{val:+.1f}</b>")
        
        sep = f" <span style='color:{sep_color}'>:</span> "
        return sep.join(parts)
    
    return f"<span style='color:{na_color}'>N/A</span>"
