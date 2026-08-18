"""
gui/components/utils/display_format.py

Global numeric display formatting for 3psLCCA.
Change DECIMAL_PLACES to propagate to every formatted value in the app.
"""

DECIMAL_PLACES: int = 2

# ── Unit tables ───────────────────────────────────────────────────────────────

_INDIA_UNITS = [
    #  threshold       divisor        full        short
    (1_00_00_000,  1_00_00_000,   "crore",    "Cr"),  # 10^7
    (1_00_000,     1_00_000,      "lakh",     "L"),   # 10^5
    (1_000,        1_000,         "thousand", "K"),   # 10^3
]

_WESTERN_UNITS = [
    #  threshold       divisor            full        short
    (100_000_000_000, 1_000_000_000_000, "trillion", "T"),
    (100_000_000,  1_000_000_000,  "billion",   "B"),  # trigger at 0.1 B
    (100_000,      1_000_000,      "million",   "M"),  # trigger at 0.1 M
    (1_000,        1_000,          "thousand",  "K"),  # 10^3
]

_UNIT_DIVISORS = {name: div for _, div, name, _ in _INDIA_UNITS + _WESTERN_UNITS}
_UNIT_DIVISORS.update({short.lower(): div for _, div, _, short in _INDIA_UNITS + _WESTERN_UNITS})

# ── Private helpers ───────────────────────────────────────────────────────────

def _to_float(val):
    """Return (float, None) on success or (None, fallback_str) on failure."""
    if val is None:
        return None, "-"
    try:
        return float(val), None
    except (TypeError, ValueError):
        return None, str(val)


def _fmt_suffix(n: float, units: list, use_short: bool = False) -> str:
    """Divide n by the first matching threshold and return 'value suffix'."""
    sign = "-" if n < 0 else ""
    abs_n = abs(n)
    for threshold, divisor, full_suffix, short_suffix in units:
        if abs_n >= threshold:
            value = round(abs_n / divisor, DECIMAL_PLACES)
            if float(value).is_integer():
                v_str = str(int(value))
            else:
                v_str = f"{value:.{DECIMAL_PLACES}f}"
            suffix = short_suffix if use_short else full_suffix
            sep = "" if use_short else " "
            return f"{sign}{v_str}{sep}{suffix}"
    return f"{sign}{abs_n:g}" if abs_n else "0"


def _fmt_inr_comma(v: float, d: int) -> str:
    """Format a non-negative float with Indian digit grouping: 12,34,567.89"""
    integer, _, decimal = f"{v:.{d}f}".partition(".")
    if len(integer) <= 3:
        return f"{integer}.{decimal}" if decimal else integer
    last3, rest = integer[-3:], integer[:-3]
    groups = []
    while len(rest) > 2:
        groups.append(rest[-2:])
        rest = rest[:-2]
    if rest:
        groups.append(rest)
    grouped = ",".join(reversed(groups)) + "," + last3
    return f"{grouped}.{decimal}" if decimal else grouped

# ── Public formatters ─────────────────────────────────────────────────────────

def get_scaled_value(n, unit: str) -> float:
    """Returns the numeric value scaled to the requested unit (e.g. 'crore', 'M', 'L')."""
    f, err = _to_float(n)
    if err is not None:
        return 0.0
    divisor = _UNIT_DIVISORS.get(unit.lower(), 1)
    return f / divisor


def fmt(val) -> str:
    """Plain decimal.  1234.5 → '1234.50'"""
    f, err = _to_float(val)
    return f"{f:.{DECIMAL_PLACES}f}" if err is None else err


def fmt_comma(val) -> str:
    """Western comma-separated decimal.  12345.6 → '12,345.60'"""
    f, err = _to_float(val)
    return f"{f:,.{DECIMAL_PLACES}f}" if err is None else err


def fmt_pct(val) -> str:
    """Percentage - always 1 decimal place.  75.3 → '75.3'"""
    f, err = _to_float(val)
    return f"{f:.1f}" if err is None else err


def fmt_short_india(n, use_short_suffix=False) -> str:
    """India suffix mode.  1_00_00_000 → '1 crore',  50_00_000 → '50 lakh'"""
    f, err = _to_float(n)
    return _fmt_suffix(f, _INDIA_UNITS, use_short=use_short_suffix) if err is None else err


def fmt_short(n, use_short_suffix=False) -> str:
    """Western suffix mode.  1_000_000 → '1 million',  500_000 → '500 thousand'"""
    f, err = _to_float(n)
    return _fmt_suffix(f, _WESTERN_UNITS, use_short=use_short_suffix) if err is None else err


def fmt_unit(n, unit: str) -> str:
    """Express n in an explicit unit.  fmt_unit(15_000_000, 'crore') → '1.50 crore'"""
    f, err = _to_float(n)
    if err is not None:
        return err
    divisor = _UNIT_DIVISORS.get(unit.lower(), 1)
    sign = "-" if f < 0 else ""
    value = round(abs(f) / divisor, DECIMAL_PLACES)
    if float(value).is_integer():
        v_str = str(int(value))
    else:
        v_str = f"{value:.{DECIMAL_PLACES}f}"
    return f"{sign}{v_str} {unit}"


def fmt_currency(val, currency="INR", decimals=None, style="comma", use_short_suffix=False) -> str:
    """Format a value as currency.

    style  "comma"  → grouped digits only    '12,34,567.00'
           "short"  → suffix only            '1 crore'
           "both"   → both                   '12,34,567.00 (1 crore)'
    """
    f, err = _to_float(val)
    if err is not None:
        return err

    d = DECIMAL_PLACES if decimals is None else decimals
    sign = "-" if f < 0 else ""
    abs_v = abs(f)

    SKIP_ME = True
    if currency == "INR" and not SKIP_ME:
        comma_str = sign + _fmt_inr_comma(abs_v, d)
        short_str = fmt_short_india(f, use_short_suffix=use_short_suffix)
    else:
        comma_str = f"{sign}{abs_v:,.{d}f}"
        short_str = fmt_short(f, use_short_suffix=use_short_suffix)

    if style == "comma":
        return comma_str
    if style == "short":
        return short_str
    return f"{comma_str} ({short_str})"


# ── Tests ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _PASS = "\033[32mPASS\033[0m"
    _FAIL = "\033[31mFAIL\033[0m"
    _errors = 0

    def check(label, got, expected):
        global _errors
        if got == expected:
            print(f"  {_PASS}  {label}")
        else:
            print(f"  {_FAIL}  {label}")
            print(f"         got      : {got!r}")
            print(f"         expected : {expected!r}")
            _errors += 1

    # fmt
    print("fmt")
    check("integer",        fmt(1234),       "1234.00")
    check("float",          fmt(1234.5),     "1234.50")
    check("string number",  fmt("99.9"),     "99.90")
    check("bad input",      fmt("abc"),      "abc")

    # fmt_comma
    print("fmt_comma")
    check("small",          fmt_comma(999),        "999.00")
    check("thousands",      fmt_comma(12345.6),    "12,345.60")
    check("millions",       fmt_comma(1234567),    "1,234,567.00")

    # fmt_pct
    print("fmt_pct")
    check("normal",         fmt_pct(75.3),   "75.3")
    check("rounding",       fmt_pct(75.36),  "75.4")
    check("zero",           fmt_pct(0),      "0.0")

    # fmt_short_india
    print("fmt_short_india")
    check("1 crore",        fmt_short_india(1_00_00_000),     "1 crore")
    check("1.5 crore",      fmt_short_india(1_50_00_000),     "1.50 crore")
    check("100 crore",      fmt_short_india(1_00_00_00_000),  "100 crore")
    check("50 lakh",        fmt_short_india(50_00_000),       "50 lakh")
    check("1 lakh",         fmt_short_india(1_00_000),        "1 lakh")
    check("below lakh",     fmt_short_india(75_000),          "75 thousand")
    check("zero",           fmt_short_india(0),               "0")
    check("negative crore", fmt_short_india(-2_00_00_000),    "-2 crore")

    # fmt_short
    print("fmt_short")
    check("1 billion",      fmt_short(1_000_000_000),  "1 billion")
    check("101 million",    fmt_short(101_000_000),    "0.10 billion")
    check("1 million",      fmt_short(1_000_000),      "1 million")
    check("500 thousand",   fmt_short(500_000),        "0.50 million")
    check("1.5 million",    fmt_short(1_500_000),      "1.50 million")
    check("below thousand", fmt_short(42),             "42")
    check("zero",           fmt_short(0),              "0")
    check("negative",       fmt_short(-2_000_000),     "-2 million")

    # fmt_unit
    print("fmt_unit")
    check("crore",          fmt_unit(1_50_00_000,  "crore"),   "1.50 crore")
    check("lakh",           fmt_unit(7_50_000,     "lakh"),    "7.50 lakh")
    check("million",        fmt_unit(2_500_000,    "million"), "2.50 million")
    check("unknown unit",   fmt_unit(5_000,        "xyz"),     "5000 xyz")

    # fmt_currency INR (SKIP_ME=True → Western mode)
    print("fmt_currency - INR")
    check("comma",          fmt_currency(12_34_567,    style="comma"),  "1,234,567.00")
    check("short",          fmt_currency(1_00_00_000,  style="short"),  "10 million")
    check("both",           fmt_currency(1_00_00_000,  style="both"),   "10,000,000.00 (10 million)")
    check("negative both",  fmt_currency(-50_00_000,   style="both"),   "-5,000,000.00 (-5 million)")
    check("below lakh",     fmt_currency(75_000,       style="comma"),  "75,000.00")

    # fmt_currency non-INR
    print("fmt_currency - USD")
    check("comma",          fmt_currency(1_234_567, currency="USD", style="comma"),  "1,234,567.00")
    check("short",          fmt_currency(1_000_000, currency="USD", style="short"),  "1 million")
    check("both",           fmt_currency(1_000_000, currency="USD", style="both"),   "1,000,000.00 (1 million)")

    print()
    if _errors:
        print(f"{_errors} test(s) FAILED")
        raise SystemExit(1)
    else:
        print("All tests passed.")
