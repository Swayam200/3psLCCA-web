from ..gui.components.maintenance.main import MAINTENANCE_FIELDS
from ..gui.project_controller import ProjectController
from .common_code import fields_to_latex

CHUNK = "maintenance_data"


def maintenance_data_to_latex(controller: ProjectController) -> str:
    data = controller.get_chunk(CHUNK)
    return fields_to_latex(MAINTENANCE_FIELDS, data, "Maintenance Data Summary", "tab:maintenance_data")
