"""
gui/api/pages/financial_data.py

Registers the "financial_data" chunk with the API.
"""

from three_ps_lcca_gui.gui.components.financial_data.main import (
    FINANCIAL_FIELDS,
    FINANCIAL_WARN_RULES,
    FinancialData,
)

from ..registry import register_chunk

register_chunk(
    "financial_data",
    page_name="Financial Data",
    widget_cls=FinancialData,
    field_defs=FINANCIAL_FIELDS,
    warn_rules=FINANCIAL_WARN_RULES,
)
