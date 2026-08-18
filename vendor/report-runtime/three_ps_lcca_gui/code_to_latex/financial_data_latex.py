from ..gui.components.financial_data.main import FINANCIAL_FIELDS
from ..gui.project_controller import ProjectController
from .common_code import fields_to_latex

CHUNK = "financial_data"


def financial_data_to_latex(controller: ProjectController) -> str:
    data = controller.get_chunk(CHUNK)
    return fields_to_latex(FINANCIAL_FIELDS, data, "Financial Data Summary", "tab:financial_data")
